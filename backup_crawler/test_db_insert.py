"""
测试数据库插入
"""
from database import DatabaseManager
from datetime import date

# 创建数据库管理器
db = DatabaseManager()

# 创建测试数据
test_data = {
    'source_type': 'NSFC',
    'title': '测试论文标题 - Machine Learning Research',
    'abstract': '这是一篇关于机器学习的测试论文摘要',
    'url': 'https://www.example.com/test',
    'published_date': date.today(),
    'signal_type': 'news',
    'field': '人工智能',
    'theme_bucket': 'AI'
}

# 尝试插入
result = db.add_paper(test_data)
print(f"插入结果: {'成功' if result else '失败/重复'}")

# 检查数据库中数据数量
count = db.get_paper_count()
print(f"数据库中现有 {count} 条数据")
