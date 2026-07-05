"""
测试中国期刊爬虫
"""
from crawler import ChineseJournalsCrawler

# 创建爬虫
crawler = ChineseJournalsCrawler(max_results=10)

# 执行采集
results = crawler.crawl()

# 打印结果
print(f"获取到 {len(results)} 条数据")
for i, r in enumerate(results, 1):
    print(f"\n--- 第 {i} 条 ---")
    print(f"来源: {r['source_type']}")
    print(f"标题: {r['title'][:50]}...")
    print(f"链接: {r['url'][:60]}")
    print(f"日期: {r['published_date']}")
