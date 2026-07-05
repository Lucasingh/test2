"""
新数据源集成测试
"""
from crawler import CrawlerManager

print("=" * 80)
print("🧪 新数据源集成测试")
print("=" * 80)

# 测试新增数据源
new_sources = [
    "kepuchina", "cdstm", "cccst", "zgcforum", "kjdb", "cstm",
    "nature", "mittr", "techcrunch"
]

print("\n测试1: 不带关键词过滤，只测试可访问性")
print("-" * 80)
manager = CrawlerManager(
    max_workers=3,
    search_query="",
    enabled_sources=new_sources,
    max_results_per_source=5
)

print(f"初始化完成，采集器数量: {len(manager.crawlers)}")
for crawler in manager.crawlers:
    print(f"  • {crawler.source_name}")

results = manager.crawl_all()

total = 0
for source_name, data in results.items():
    count = data['count']
    total += count
    print(f"{source_name}: {count} 条")
    if data['papers']:
        for paper in data['papers'][:1]:
            title = paper.get('title', '')[:50]
            print(f"  - {title}...")

print(f"\n✅ 测试1总计: {total} 条数据")
manager.close()

print("\n" + "=" * 80)
print("测试2: 带关键词'人工智能'过滤")
print("-" * 80)

manager2 = CrawlerManager(
    max_workers=3,
    search_query="人工智能",
    enabled_sources=new_sources,
    max_results_per_source=5
)

results2 = manager2.crawl_all()

total2 = 0
for source_name, data in results2.items():
    count = data['count']
    total2 += count
    print(f"{source_name}: {count} 条")

print(f"\n✅ 测试2总计: {total2} 条数据")
manager2.close()