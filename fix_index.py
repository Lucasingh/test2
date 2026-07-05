
"""
修复数据库索引问题：移除 content_hash 的唯一索引
"""
from sqlalchemy import text
from database import db

print("=== 修复数据库索引 ===")
try:
    connection = db.engine.connect()
    try:
        print("删除 papers 表的唯一索引...")
        connection.execute(text("DROP INDEX ix_papers_content_hash ON papers"))
        print("创建普通索引...")
        connection.execute(text("CREATE INDEX ix_papers_content_hash ON papers (content_hash)"))
        connection.commit()
        print("\n✅ 索引修复完成！")
    except Exception as e:
        print(f"⚠️ 索引可能已不存在: {e}")
        connection.rollback()
    finally:
        connection.close()
except Exception as e:
    print(f"❌ 修复失败: {e}")
