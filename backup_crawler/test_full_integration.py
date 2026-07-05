"""
完整集成测试 - 模拟主程序调用
"""
from crawler import CrawlerManager
from config import CONFIG

print("=" * 80)
print("🧪 完整集成测试 - 使用配置中的默认启用数据源")
print("=" * 80)

# 使用配置中启用的数据源（排除可能超时的 arXiv）
enabled_sources = []
for source_name, config in CONFIG['sources'].items():
    if config.get('enabled', True):
        enabled_sources.append(source_name)

print(f"\n启用数据源: {enabled_sources}")

manager = CrawlerManager(
    max_workers=4,
    search_query="前沿科技",
    enabled_sources=enabled_sources,
    max_results_per_source=5
)

print(f"\n初始化完成，采集器数量: {len(manager.crawlers)}")
for crawler in manager.crawlers:
    print(f"  • {crawler.source_name}")

print("\n开始采集...")
results = manager.crawl_all()

print("\n" + "=" * 80)
print("📊 采集结果")
print("=" * 80)

total = 0
for source_name, data in results.items():
    count = data['count']
    total += count
    print(f"{source_name}: {count} 条")

print(f"\n✅ 总计: {total} 条数据")

manager.close()