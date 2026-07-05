from database import db

# 搜索包含 "forest" 的数据
papers = db.get_papers(user_id=1, keyword="forest", limit=10)
print("搜索 'forest' 的结果:")
for i, p in enumerate(papers):
    print(f"{i+1}. {p['title'][:80]}...")
    print(f"   来源: {p['source_type']}, 主题: {p['theme_bucket']}")
    print(f"   摘要: {p['abstract'][:100]}...")
    print()