
"""
测试单点登录功能
"""
import sys
import logging
from datetime import datetime, timedelta
from database import db, UserSession
from auth import auth_manager
from sqlalchemy import func

# 设置DEBUG日志级别
logging.basicConfig(level=logging.DEBUG)

def debug_sessions():
    """打印所有会话状态"""
    with db.get_session() as session:
        sessions = session.query(UserSession).all()
        print(f"\n--- 当前数据库中的会话 (共{len(sessions)}个) ---")
        for s in sessions:
            print(f"  会话ID: {s.id}, 用户ID: {s.user_id}, 是否激活: {s.is_active}, Token: {s.token[:20]}...")

def test_session_management():
    print("=== 测试单点登录功能 ===\n")
    
    # 先清空所有会话
    with db.get_session() as session:
        session.query(UserSession).delete()
    print("已清空所有会话\n")
    
    # 获取admin用户
    user = auth_manager.authenticate('admin', 'admin123')
    if not user:
        print("❌ 无法获取admin用户")
        return False
    print(f"✅ 获取用户成功: {user.username} (id={user.id})\n")
    
    # 测试1: 创建第一个会话
    print("测试1: 创建第一个会话")
    token1 = auth_manager.create_token(user)
    print(f"   Token1: {token1[:50]}...")
    
    debug_sessions()
    
    # 验证token1
    valid1 = db.validate_session(token1)
    print(f"\n   Token1验证: {'✅ 有效' if valid1 else '❌ 无效'} (user_id={valid1})\n")
    
    # 测试2: 创建第二个会话（应该使第一个失效）
    print("测试2: 创建第二个会话（应该使第一个失效）")
    token2 = auth_manager.create_token(user)
    print(f"   Token2: {token2[:50]}...")
    
    debug_sessions()
    
    # 验证token1（应该失效）
    valid1_after = db.validate_session(token1)
    print(f"\n   Token1验证: {'✅ 有效' if valid1_after else '❌ 无效'} (user_id={valid1_after})")
    
    # 验证token2（应该有效）
    valid2 = db.validate_session(token2)
    print(f"   Token2验证: {'✅ 有效' if valid2 else '❌ 无效'} (user_id={valid2})")
    
    # 直接查询数据库检查token2的状态
    print("\n--- 直接查询token2的状态 ---")
    with db.get_session() as session:
        session_obj = session.query(UserSession).filter(UserSession.token == token2).first()
        if session_obj:
            print(f"  会话ID: {session_obj.id}")
            print(f"  用户ID: {session_obj.user_id}")
            print(f"  是否激活: {session_obj.is_active}")
            print(f"  过期时间: {session_obj.expires_at}")
            print(f"  当前时间: {datetime.now()}")
            print(f"  过期比较: {session_obj.expires_at} > {datetime.now()} = {session_obj.expires_at > datetime.now()}")
            print(f"  完整token: {session_obj.token}")
            print(f"  传入token: {token2}")
            print(f"  token匹配: {session_obj.token == token2}")
    
    # 测试3: 验证auth_manager的verify_token
    print("测试3: 通过AuthManager验证token")
    payload1 = auth_manager.verify_token(token1)
    print(f"   Token1验证: {'✅ 有效' if payload1 else '❌ 无效'}")
    
    payload2 = auth_manager.verify_token(token2)
    print(f"   Token2验证: {'✅ 有效' if payload2 else '❌ 无效'}\n")
    
    # 总结
    print("=== 测试总结 ===")
    if not valid1_after and valid2:
        print("✅ 单点登录功能正常！创建新会话后旧会话被正确失效。")
        return True
    else:
        print("❌ 单点登录功能异常！")
        return False

if __name__ == "__main__":
    success = test_session_management()
    sys.exit(0 if success else 1)
