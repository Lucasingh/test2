"""
重新分类所有现有论文
"""
from database import db
from processor import ThemeClassifier

print("开始重新分类所有论文...")

result = db.batch_reclassify_papers(user_id=1)

print(f"\n重新分类完成！")
print(f"更新了 {result['updated']} 条记录")
