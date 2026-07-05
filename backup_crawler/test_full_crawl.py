"""
测试完整采集流程
"""
from crawler import ChineseJournalsCrawler
from database import DatabaseManager

# 创建爬虫
crawler = ChineseJournalsCrawler(max_results=10)
print("正在采集...")
results = crawler.crawl()
print(f"采集完成，获取到 {len(results)} 条数据")

# 检查数据格式
if results:
    print("\n第一条数据格式:")
    for key, value in results[0].items():
        print(f"  {key}: {type(value).__name__} = {str(value)[:50]}...")

# 尝试插入数据库
db = DatabaseManager()
if results:
    print("\n正在插入数据库...")
    added, duplicates = db.add_papers(results)
    print(f"插入完成: 新增 {added} 条, 重复 {duplicates} 条")
    
    # 检查数据库中数据数量
    count = db.get_paper_count()
    print(f"数据库中现有 {count} 条数据")
