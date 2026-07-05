from database import db

papers = db.get_papers(user_id=1, limit=10)
print("现有数据:")
for i, p in enumerate(papers):
    print(f"{i+1}. {p['title'][:60]}...")
    print(f"   来源: {p['source_type']}, 主题: {p['theme_bucket']}")
    print()