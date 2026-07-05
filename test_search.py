from database import db

# 测试搜索 "helloworld"
print("测试搜索 'helloworld':")
papers = db.get_papers(user_id=1, keyword="helloworld", limit=5)
print(f"找到 {len(papers)} 条结果")
for i, p in enumerate(papers):
    print(f"{i+1}. {p['title'][:60]}...")

print("\n测试搜索 'machine learning':")
papers = db.get_papers(user_id=1, keyword="machine learning", limit=5)
print(f"找到 {len(papers)} 条结果")
for i, p in enumerate(papers):
    print(f"{i+1}. {p['title'][:60]}...")

print("\n测试搜索 'forest':")
papers = db.get_papers(user_id=1, keyword="forest", limit=5)
print(f"找到 {len(papers)} 条结果")
for i, p in enumerate(papers):
    print(f"{i+1}. {p['title'][:60]}...")