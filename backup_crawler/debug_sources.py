"""
数据源调试脚本
"""
import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

session = requests.Session()

print("=" * 80)
print("🔍 B站API调试")
print("=" * 80)

try:
    url = "https://api.bilibili.com/x/web-interface/search/all/v2?keyword=前沿科技"
    response = session.get(url, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")
    
    data = response.json()
    print(f"\n响应结构:")
    print(f"  code: {data.get('code')}")
    print(f"  message: {data.get('message')}")
    
    result = data.get('result', {})
    print(f"\nresult keys: {list(result.keys())}")
    
    video = result.get('video', {})
    print(f"\nvideo keys: {list(video.keys())}")
    
    if video:
        print(f"video result: {video.get('result', 'N/A')[:3]}...")
    
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 80)
print("🔍 科学网首页调试")
print("=" * 80)

try:
    url = "https://www.sciencenet.cn"
    response = session.get(url, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")
    
    if response.encoding == 'ISO-8859-1':
        response.encoding = 'utf-8'
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    print(f"\n页面标题: {soup.title.string if soup.title else '无'}")
    
    print("\n查找新闻列表:")
    selectors = [
        ('div', {'class': 'news-item'}),
        ('div', {'class': 'list-item'}),
        ('li', {'class': 'list-group-item'}),
        ('div', {'class': 'content'}),
    ]
    
    for tag, attrs in selectors:
        items = soup.find_all(tag, attrs)[:5]
        if items:
            print(f"\n通过 {tag}.{attrs} 找到 {len(items)} 个元素:")
            for i, item in enumerate(items, 1):
                text = item.get_text(strip=True)[:80]
                print(f"  {i}. {text}...")
    
    print("\n查找所有带href的a标签:")
    links = soup.find_all('a', href=True)[:10]
    for link in links:
        text = link.get_text(strip=True)[:40]
        href = link['href'][:60]
        if text and len(text) > 5:
            print(f"  {text}... -> {href}")
    
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 80)
print("🔍 知乎首页调试")
print("=" * 80)

try:
    url = "https://www.zhihu.com"
    response = session.get(url, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")
    
    if response.encoding == 'ISO-8859-1':
        response.encoding = 'utf-8'
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    print(f"\n页面标题: {soup.title.string if soup.title else '无'}")
    
    print("\n查找内容:")
    selectors = [
        ('div', {'class': True}),
        ('h1', {}),
        ('h2', {}),
        ('h3', {}),
    ]
    
    for tag, attrs in selectors:
        items = soup.find_all(tag, attrs)[:3]
        if items:
            print(f"\n通过 {tag}.{attrs} 找到 {len(items)} 个元素:")
            for i, item in enumerate(items, 1):
                text = item.get_text(strip=True)[:60]
                print(f"  {i}. {text}...")
    
except Exception as e:
    print(f"错误: {e}")