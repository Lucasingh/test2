
"""
更新现有数据的 user_id 字段
"""
from sqlalchemy import text
from database import db

print("=== 更新现有数据的 user_id ===")
try:
    connection = db.engine.connect()
    try:
        print("更新 papers 表...")
        connection.execute(text("UPDATE papers SET user_id = 1 WHERE user_id IS NULL"))
        print("更新 crawl_history 表...")
        connection.execute(text("UPDATE crawl_history SET user_id = 1 WHERE user_id IS NULL"))
        print("更新 favorites 表...")
        connection.execute(text("UPDATE favorites SET user_id = 1 WHERE user_id IS NULL"))
        connection.commit()
        print("\n✅ 数据更新完成！")
    finally:
        connection.close()
except Exception as e:
    print(f"❌ 更新失败: {e}")
