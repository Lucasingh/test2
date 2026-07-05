
"""
数据库迁移脚本 - 添加 user_id 字段支持用户数据隔离
"""
import logging
from sqlalchemy import text
from database import db, Base, Paper, CrawlHistory, Favorite

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    print("=== 数据库迁移 - 添加 user_id 字段 ===")
    
    try:
        # 检查并添加 Paper.user_id 字段
        print("1. 检查 Paper 表...")
        with db.get_session() as session:
            # 尝试查询，如果失败则说明表结构需要更新
            try:
                session.query(Paper.user_id).first()
                print("   Paper.user_id 字段已存在")
            except Exception as e:
                print(f"   需要添加 user_id 字段")
                # 这里需要手动执行SQL来添加字段
                connection = db.engine.connect()
                try:
                    connection.execute(text("ALTER TABLE papers ADD COLUMN user_id INT DEFAULT 1"))
                    connection.execute(text("ALTER TABLE papers ADD INDEX ix_papers_user_id (user_id)"))
                    connection.commit()
                    print("   ✅ Paper.user_id 字段添加成功")
                finally:
                    connection.close()
        
        # 检查并添加 CrawlHistory.user_id 字段
        print("2. 检查 CrawlHistory 表...")
        with db.get_session() as session:
            try:
                session.query(CrawlHistory.user_id).first()
                print("   CrawlHistory.user_id 字段已存在")
            except Exception as e:
                print(f"   需要添加 user_id 字段")
                connection = db.engine.connect()
                try:
                    connection.execute(text("ALTER TABLE crawl_history ADD COLUMN user_id INT DEFAULT 1"))
                    connection.execute(text("ALTER TABLE crawl_history ADD INDEX ix_crawl_history_user_id (user_id)"))
                    connection.commit()
                    print("   ✅ CrawlHistory.user_id 字段添加成功")
                finally:
                    connection.close()
        
        # 检查并添加 Favorite.user_id 字段
        print("3. 检查 Favorite 表...")
        with db.get_session() as session:
            try:
                session.query(Favorite.user_id).first()
                print("   Favorite.user_id 字段已存在")
            except Exception as e:
                print(f"   需要添加 user_id 字段")
                connection = db.engine.connect()
                try:
                    connection.execute(text("ALTER TABLE favorites ADD COLUMN user_id INT DEFAULT 1"))
                    connection.execute(text("ALTER TABLE favorites ADD INDEX ix_favorites_user_id (user_id)"))
                    connection.commit()
                    print("   ✅ Favorite.user_id 字段添加成功")
                finally:
                    connection.close()
        
        # 更新现有数据的 user_id 为默认值 1
        print("4. 更新现有数据的 user_id...")
        connection = db.engine.connect()
        try:
            connection.execute(text("UPDATE papers SET user_id = 1 WHERE user_id IS NULL"))
            connection.execute(text("UPDATE crawl_history SET user_id = 1 WHERE user_id IS NULL"))
            connection.execute(text("UPDATE favorites SET user_id = 1 WHERE user_id IS NULL"))
            connection.commit()
            print("   ✅ 现有数据已更新")
        finally:
            connection.close()
        
        print("\n✅ 数据库迁移完成！")
        return True
        
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}")
        print(f"❌ 数据库迁移失败: {e}")
        return False

if __name__ == "__main__":
    success = migrate_database()
    exit(0 if success else 1)
