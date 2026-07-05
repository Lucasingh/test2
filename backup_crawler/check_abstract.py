from database import db

# 获取包含 "forest" 的数据的完整摘要
papers = db.get_papers(user_id=1, keyword="forest", limit=5)
for i, p in enumerate(papers):
    print(f"文章 {i+1}:")
    print(f"标题: {p['title']}")
    print(f"完整摘要: {p['abstract']}")
    print(f"摘要中是否包含 'forest': {'forest' in p['abstract'].lower()}")
    print()