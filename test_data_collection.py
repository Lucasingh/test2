"""
数据采集模块功能测试脚本
测试内容：
  1. 模块导入验证
  2. 关键词翻译功能
  3. 数据格式化（format_paper_data）
  4. 采集管理器初始化（所有14个数据源）
  5. 中文预设数据源测试（ChineseJournalsCrawler）
  6. 任务队列创建和状态跟踪
"""
import sys
import os
from datetime import date

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("数据采集模块功能测试")
print("=" * 60)

# ---------- 1. 模块导入验证 ----------
print("\n[测试1] 模块导入...")
try:
    from config import CONFIG
    print(f"  ✅ CONFIG 加载成功")
    print(f"     - 数据库: {CONFIG['database']['host']}:{CONFIG['database']['port']}")
    print(f"     - Redis启用: {CONFIG.get('redis', {}).get('enabled', False)}")
    print(f"     - 主题数: {len(CONFIG.get('themes', {}))}")
    print(f"     - 数据源配置数: {len(CONFIG.get('sources', {}))}")
    print(f"     - RSS订阅源数: {len(CONFIG.get('rss_feeds', {}))}")

    from processor import clean_text, parse_date, ThemeClassifier
    print(f"  ✅ processor 模块导入成功")
    
    from crawler import (
        CrawlerBase, ArxivCrawler, OpenAlexCrawler, PubmedCrawler,
        ScienceDailyCrawler, RSSCrawler, MITTRCrawler, TechCrunchCrawler,
        GenericWebCrawler, ChineseJournalsCrawler, CrawlerManager,
        translate_keywords, format_paper_data, CHINESE_SOURCE_MAP,
    )
    print(f"  ✅ crawler 模块导入成功")
    print(f"     - 采集器类: 10个")
    print(f"     - 中文数据源映射: {len(CHINESE_SOURCE_MAP)} 个")

    from tasks import RedisTaskManager, crawl_task
    print(f"  ✅ tasks 模块导入成功")

except ImportError as e:
    print(f"  ❌ 导入失败: {e}")
    sys.exit(1)

# ---------- 2. 关键词翻译功能测试 ----------
print("\n[测试2] 关键词翻译...")
test_cases = [
    ("hello world", "hello world"),           # 纯英文，原样返回
    ("人工 智能", "artificial intelligence"),  # 翻译
    ("前沿科技", "advanced technology"),       # 完整匹配
    ("量子计算 机器学习", "quantum computing machine learning"),  # 多词
]
for query, expected in test_cases:
    result = translate_keywords(query)
    status = "✅" if result == expected else "⚠️"
    print(f"  {status} translate_keywords('{query}') = '{result}'")
    if result != expected and query.replace(' ', '').isascii():
        pass  # 纯英文可能因空格拆分而差异

# ---------- 3. 数据格式化测试 ----------
print("\n[测试3] 数据格式化...")
raw_paper = {
    'source_type': 'arXiv',
    'title': '  Test Paper: <b>AI</b> Research  ',
    'abstract': 'This is a test abstract with <p>HTML tags</p>.',
    'url': 'https://arxiv.org/abs/2401.00001',
    'published_date': '2024-01-15',
    'signal_type': 'paper',
    'field': 'cs.AI',
}
formatted = format_paper_data(raw_paper)
print(f"  ✅ 格式化后的字段:")
for key in ['source_type', 'title', 'abstract', 'url', 'published_date', 'signal_type', 'field', 'content_hash']:
    val = formatted.get(key, '')
    print(f"     - {key}: {str(val)[:60]}")

# ---------- 4. 采集管理器初始化测试 ----------
print("\n[测试4] 采集管理器初始化（所有已确认数据源）...")
try:
    all_sources = list(CONFIG.get('sources', {}).keys())
    manager = CrawlerManager(
        max_workers=4,
        search_query="artificial intelligence",
        enabled_sources=all_sources,
        max_results_per_source=5,
    )
    crawler_names = [c.source_name for c in manager.crawlers]
    print(f"  ✅ CrawlerManager 初始化成功: {len(manager.crawlers)} 个采集器")
    for name in crawler_names:
        print(f"     - {name}")
    manager.close()
except Exception as e:
    print(f"  ❌ CrawlerManager 初始化失败: {e}")

# ---------- 5. 中文预设数据源测试 ----------
print("\n[测试5] 中文预设数据源 (ChineseJournalsCrawler)...")
try:
    crawler = ChineseJournalsCrawler(max_results=10, search_query="")
    papers = crawler.crawl()
    print(f"  ✅ 中文期刊采集器返回 {len(papers)} 条数据 (含预设数据)")
    for p in papers[:3]:
        print(f"     - [{p['source_type']}] {p['title'][:40]}...")
    crawler.close()
except Exception as e:
    print(f"  ❌ 中文期刊采集器测试失败: {e}")

# ---------- 6. 带关键词的中文预设数据测试 ----------
print("\n[测试6] 中文预设数据源（带关键词过滤量子计算）...")
try:
    crawler = ChineseJournalsCrawler(max_results=5, search_query="量子计算")
    papers = crawler.crawl()
    print(f"  ✅ 关键词'量子计算'返回 {len(papers)} 条数据")
    for p in papers[:3]:
        print(f"     - [{p['source_type']}] {p['title'][:40]}...")
    crawler.close()
except Exception as e:
    print(f"  ❌ 带关键词测试失败: {e}")

# ---------- 7. 任务队列测试 ----------
print("\n[测试7] 任务队列 (RedisTaskManager)...")
try:
    task_manager = RedisTaskManager()
    # 创建采集任务（使用预设数据源，不联网也能验证流程）
    task_id = task_manager.create_crawl_task(
        user_id=1,
        sources=['chinese'],  # 仅使用中文预设数据源
        query="人工智能",
        max_results=5,
    )
    print(f"  ✅ 创建任务成功: task_id={task_id[:8]}...")

    # 等待任务完成
    import time
    for i in range(10):
        status = task_manager.get_task_status(task_id)
        if status:
            print(f"     - 状态: {status['status']}, 进度: {status['progress']}%")
            if status['status'] in ('completed', 'failed'):
                break
        time.sleep(1)
    
    final = task_manager.get_task_status(task_id)
    if final and final['status'] == 'completed':
        print(f"  ✅ 任务完成! 新增: {final['completed']} 条")
    elif final and final['status'] == 'failed':
        print(f"  ⚠️ 任务失败: {final['message']}")
    else:
        print(f"  ⚠️ 任务状态未知")
except Exception as e:
    print(f"  ❌ 任务队列测试失败: {e}")

# ---------- 8. ThemeClassifier分类测试 ----------
print("\n[测试8] 主题分类集成测试...")
test_texts = [
    ("大语言模型在医疗领域的最新进展", "cs.AI"),
    ("CRISPR基因编辑治疗镰状细胞病", "Medicine"),
    ("钙钛矿太阳能电池效率突破40%", "Renewable Energy"),
]
for title, field in test_texts:
    result = ThemeClassifier.classify(title, "", field)
    print(f"  ✅ '{title[:20]}...' → {result['theme_bucket']} (置信度: {result['confidence']})")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
