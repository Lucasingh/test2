"""
测试数据库删除功能
"""
from database import DatabaseManager

# 创建数据库管理器
db = DatabaseManager()

# 获取当前数据数量
count_before = db.get_paper_count()
print(f"删除前数据数量: {count_before}")

# 执行删除
deleted_count = db.delete_all_papers()
print(f"删除的数据数量: {deleted_count}")

# 获取删除后数据数量
count_after = db.get_paper_count()
print(f"删除后数据数量: {count_after}")

print("\n删除操作" + ("成功！" if count_after == 0 else "失败！"))
