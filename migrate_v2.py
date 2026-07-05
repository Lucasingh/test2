"""
数据库迁移脚本 - 2026-06-20
为现有数据库添加主题分类增强字段
"""
import logging
import sys
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """执行数据库迁移"""
    from database import db
    
    try:
        logger.info("开始数据库迁移...")
        
        with db.engine.connect() as conn:
            new_columns = [
                ("theme_confidence", "FLOAT DEFAULT 0"),
                ("matched_keywords", "TEXT"),
                ("core_matched_keywords", "TEXT"),
                ("subject_tags", "TEXT"),
                ("is_manual_reviewed", "BOOLEAN DEFAULT FALSE"),
                ("manual_theme", "VARCHAR(50)"),
                ("review_note", "TEXT"),
                ("textbook_matches", "TEXT"),
            ]
            
            for col_name, col_def in new_columns:
                try:
                    result = conn.execute(text(f"SHOW COLUMNS FROM papers LIKE '{col_name}'"))
                    row = result.fetchone()
                    if row:
                        logger.info(f"列 {col_name} 已存在，跳过")
                    else:
                        conn.execute(text(f"ALTER TABLE papers ADD COLUMN {col_name} {col_def}"))
                        logger.info(f"✓ 已添加列: {col_name}")
                except Exception as e:
                    logger.warning(f"添加列 {col_name} 时出错: {e}")
            
            try:
                conn.execute(text("""
                    CREATE INDEX idx_papers_manual_reviewed 
                    ON papers(is_manual_reviewed)
                """))
                logger.info("✓ 已添加索引: idx_papers_manual_reviewed")
            except Exception as e:
                if "Duplicate key name" in str(e) or "already exists" in str(e):
                    logger.info("索引 idx_papers_manual_reviewed 已存在，跳过")
                else:
                    logger.warning(f"创建索引时出错: {e}")
            
            conn.commit()
        
        logger.info("数据库迁移完成！")
        return True
        
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}")
        return False

def reclassify_all_papers():
    """重新分类所有论文"""
    from processor import ThemeClassifier
    from database import db
    
    try:
        logger.info("开始重新分类所有论文...")
        
        result = db.batch_reclassify_papers(user_id=1)
        logger.info(f"重新分类完成，更新了 {result['updated']} 条记录")
        return result
        
    except Exception as e:
        logger.error(f"重新分类失败: {e}")
        return {'updated': 0}

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移脚本 - 主题分类增强功能")
    print("=" * 60)
    
    success = migrate_database()
    
    if success:
        print("\n迁移成功！")
        
        answer = input("\n是否重新分类所有现有论文？(y/n): ")
        if answer.lower() == 'y':
            result = reclassify_all_papers()
            print(f"\n重新分类完成，更新了 {result['updated']} 条记录")
    else:
        print("\n迁移失败，请检查错误信息")
        sys.exit(1)
