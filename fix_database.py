"""修复数据库表的脚本"""
import sys
sys.path.insert(0, '.')

from database import db
from database import Base, UserSession
from sqlalchemy import text

def fix_database():
    print("开始修复数据库...")
    
    try:
        with db.get_session() as session:
            # 检查 user_sessions 表是否存在
            try:
                session.execute(text("SELECT 1 FROM user_sessions LIMIT 1"))
                print("user_sessions 表已存在，正在删除...")
                session.execute(text("DROP TABLE IF EXISTS user_sessions"))
                session.commit()
                print("user_sessions 表已删除")
            except:
                print("user_sessions 表不存在，跳过删除")
            
            # 检查 users 表是否存在
            try:
                session.execute(text("SELECT 1 FROM users LIMIT 1"))
                print("users 表已存在，正在删除...")
                session.execute(text("DROP TABLE IF EXISTS users"))
                session.commit()
                print("users 表已删除")
            except:
                print("users 表不存在，跳过删除")
        
        print("\n正在重新创建表...")
        Base.metadata.create_all(db.engine, checkfirst=True)
        print("表创建完成！")
        
        print("\n✅ 数据库修复成功！")
        print("\n现在可以重启应用测试单点登录功能了。")
        
    except Exception as e:
        print(f"\n❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_database()
