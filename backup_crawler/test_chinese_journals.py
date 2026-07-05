"""
中国学术期刊爬虫测试脚本 - 改进版
测试网站：《中国科学》《科学通报》《中国科学院院刊》《国家自然科学基金委》
搜索关键词：machine learning
"""
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime

def test_chinese_journals():
    """测试中国学术期刊网站"""
    print("=" * 70)
    print("测试: 中国学术期刊网站")
    print("搜索关键词: machine learning")
    print("=" * 70)
    
    sites = [
        {
            'name': '中国科学期刊网',
            'url': 'https://www.scichina.com',
            'search_url': 'https://www.scichina.com/search?keyword={keyword}'
        },
        {
            'name': '国家自然科学基金委',
            'url': 'https://www.nsfc.gov.cn',
            'search_url': 'https://www.nsfc.gov.cn/nsfc/cen/xmzn/search.jsp?keyword={keyword}'
        },
        {
            'name': '中国科学院院刊',
            'url': 'http://www.bulletin.cas.cn',  # 尝试HTTP协议
            'search_url': None
        },
        {
            'name': '中国科学报',
            'url': 'https://www.sciencenet.cn',
            'search_url': 'https://www.sciencenet.cn/search/?q={keyword}'
        },
        {
            'name': '科技导报',
            'url': 'http://www.kjdb.org',
            'search_url': None
        }
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    session = requests.Session()
    
    for site in sites:
        print(f"\n--- {site['name']} ---")
        print(f"网址: {site['url']}")
        
        try:
            # 访问首页
            response = session.get(site['url'], headers=headers, timeout=30)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                # 处理编码
                if response.encoding == 'ISO-8859-1':
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.content, 'html.parser')
                page_title = soup.title.string if soup.title else '无标题'
                print(f"页面标题: {page_title}")
                
                # 尝试搜索
                if site['search_url']:
                    search_url = site['search_url'].format(keyword='machine+learning')
                    print(f"搜索URL: {search_url}")
                    
                    try:
                        search_response = session.get(search_url, headers=headers, timeout=30)
                        print(f"搜索状态码: {search_response.status_code}")
                        
                        if search_response.status_code == 200:
                            search_soup = BeautifulSoup(search_response.content, 'html.parser')
                            
                            # 尝试多种方式查找文章列表
                            articles = []
                            selectors = [
                                ('div', {'class': True}),
                                ('li', {'class': True}),
                                ('article', {}),
                                ('div', {'id': True})
                            ]
                            
                            for tag, attrs in selectors:
                                items = search_soup.find_all(tag, attrs)[:20]
                                for item in items:
                                    text = item.get_text(strip=True)
                                    if text and len(text) > 10:
                                        articles.append(item)
                            
                            print(f"找到 {len(articles)} 条相关内容")
                            if articles:
                                for i, article in enumerate(articles[:3], 1):
                                    title = article.get_text(strip=True)[:60]
                                    link_elem = article.find('a', href=True)
                                    link = link_elem['href'] if link_elem else ''
                                    print(f"\n{i}. {title}...")
                                    if link:
                                        if not link.startswith('http'):
                                            link = site['url'] + link
                                        print(f"   链接: {link[:80]}")
                                
                    except Exception as e:
                        print(f"搜索失败: {e}")
                
                # 直接从首页查找新闻
                articles = soup.find_all('a', href=True)
                print(f"\n首页链接数: {len(articles)}")
                count = 0
                for link in articles:
                    text = link.get_text(strip=True)
                    href = link['href']
                    if text and len(text) > 8 and (href.endswith('.html') or '/article/' in href):
                        full_link = href if href.startswith('http') else site['url'] + href
                        print(f"{count+1}. {text[:50]}...")
                        print(f"   {full_link[:60]}")
                        count += 1
                        if count >= 3:
                            break
                
            else:
                print(f"访问失败，状态码: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("❌ 连接超时")
        except requests.exceptions.ConnectionError:
            print("❌ 连接失败")
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    session.close()

if __name__ == "__main__":
    print("🔍 中国学术期刊爬虫测试")
    test_chinese_journals()
    print("\n" + "=" * 70)
    print("测试完成！")
