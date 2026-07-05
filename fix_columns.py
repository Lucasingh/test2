"""
快速修复数据库字段
"""
import sys
from sqlalchemy import text
from database import db

columns_to_add = [
    ("theme_confidence", "FLOAT DEFAULT 0"),
    ("matched_keywords", "TEXT"),
    ("core_matched_keywords", "TEXT"),
    ("subject_tags", "TEXT"),
    ("is_manual_reviewed", "TINYINT(1) DEFAULT 0"),
    ("manual_theme", "VARCHAR(50)"),
    ("review_note", "TEXT"),
    ("textbook_matches", "TEXT"),
]

with db.engine.connect() as conn:
    for col_name, col_def in columns_to_add:
        try:
            result = conn.execute(text(f"SHOW COLUMNS FROM papers LIKE '{col_name}'"))
            row = result.fetchone()
            if row:
                print(f"✓ 列 {col_name} 已存在")
            else:
                conn.execute(text(f"ALTER TABLE papers ADD COLUMN {col_name} {col_def}"))
                print(f"+ 已添加列: {col_name}")
                conn.commit()
        except Exception as e:
            print(f"✗ 处理列 {col_name} 时出错: {e}")
    
    try:
        conn.execute(text("CREATE INDEX idx_papers_manual_reviewed ON papers(is_manual_reviewed)"))
        print("+ 已添加索引: idx_papers_manual_reviewed")
        conn.commit()
    except Exception as e:
        if "Duplicate key name" in str(e):
            print("✓ 索引 idx_papers_manual_reviewed 已存在")
        else:
            print(f"✗ 创建索引时出错: {e}")

print("\n数据库字段检查完成！")
