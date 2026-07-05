
"""
测试用户数据隔离功能
"""
import sys
from datetime import date
from database import db
from auth import auth_manager

def test_user_isolation():
    print("=== 测试用户数据隔离功能 ===\n")
    
    # 创建测试用户
    print("1. 创建测试用户...")
    user1 = auth_manager.authenticate('admin', 'admin123')
    if not user1:
        print("❌ 无法获取admin用户")
        return False
    print(f"   ✅ 用户1: admin (ID={user1.id})")
    
    # 创建第二个测试用户
    if not auth_manager.authenticate('user2', 'password123'):
        auth_manager.create_user('user2', 'user2@example.com', 'password123', '测试用户2')
    user2 = auth_manager.authenticate('user2', 'password123')
    if not user2:
        print("❌ 无法创建或获取user2用户")
        return False
    print(f"   ✅ 用户2: user2 (ID={user2.id})\n")
    
    # 测试1: 用户1添加数据
    print("2. 用户1添加数据...")
    paper_data = {
        'source_type': 'test',
        'title': '测试论文 - 用户1专属',
        'abstract': '这是用户1的专属论文',
        'url': 'https://example.com/test1',
        'published_date': date(2024, 1, 1),
        'signal_type': 'paper',
        'theme_bucket': 'AI',
        'field': 'Test',
        'tags': 'test'
    }
    db.add_paper(paper_data, user1.id)
    print("   ✅ 用户1添加论文成功\n")
    
    # 测试2: 用户2添加数据
    print("3. 用户2添加数据...")
    paper_data2 = {
        'source_type': 'test',
        'title': '测试论文 - 用户2专属',
        'abstract': '这是用户2的专属论文',
        'url': 'https://example.com/test2',
        'published_date': date(2024, 1, 2),
        'signal_type': 'paper',
        'theme_bucket': 'AI',
        'field': 'Test',
        'tags': 'test'
    }
    db.add_paper(paper_data2, user2.id)
    print("   ✅ 用户2添加论文成功\n")
    
    # 测试3: 用户1查看自己的数据
    print("4. 用户1查看自己的数据...")
    papers1 = db.get_papers(user_id=user1.id)
    print(f"   用户1的数据数量: {len(papers1)}")
    for p in papers1:
        print(f"     - {p['title']}")
    print()
    
    # 测试4: 用户2查看自己的数据
    print("5. 用户2查看自己的数据...")
    papers2 = db.get_papers(user_id=user2.id)
    print(f"   用户2的数据数量: {len(papers2)}")
    for p in papers2:
        print(f"     - {p['title']}")
    print()
    
    # 测试5: 验证统计数据隔离
    print("6. 验证统计数据隔离...")
    stats1 = db.get_statistics(user1.id)
    stats2 = db.get_statistics(user2.id)
    print(f"   用户1统计: {stats1['total']} 条")
    print(f"   用户2统计: {stats2['total']} 条")
    print()
    
    # 清理测试数据
    print("7. 清理测试数据...")
    db.delete_all_papers(user1.id)
    db.delete_all_papers(user2.id)
    print("   ✅ 测试数据已清理\n")
    
    # 总结
    print("=== 测试总结 ===")
    # 用户2应该只能看到自己的数据（1条）
    # 用户1（admin）应该能看到所有历史数据（因为之前数据的user_id都设为1了）
    if len(papers2) == 1 and papers2[0]['title'] == '测试论文 - 用户2专属':
        print("✅ 用户数据隔离功能正常！")
        print(f"   - 用户1（admin）看到 {len(papers1)} 条数据（包括历史数据）")
        print(f"   - 用户2 看到 {len(papers2)} 条数据（仅自己添加的）")
        return True
    else:
        print("❌ 用户数据隔离功能异常！")
        return False

if __name__ == "__main__":
    success = test_user_isolation()
    sys.exit(0 if success else 1)
