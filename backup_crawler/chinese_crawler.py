"""
中国学术期刊爬虫模块
支持：国家自然科学基金委、科学网、科技导报等
搜索关键词：machine learning
"""
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
import re

class ChineseJournalsCrawler:
    """中国学术期刊爬虫"""
    
    def __init__(self, max_results: int = 20, search_query: str = ""):
        self.max_results = max_results
        self.search_query = search_query or "machine learning"
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
    
    def crawl_nsfc(self):
        """采集国家自然科学基金委"""
        results = []
        url = "https://www.nsfc.gov.cn"
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                if response.encoding == 'ISO-8859-1':
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.content, 'html.parser')
                articles = soup.find_all('a', href=True)
                
                for link in articles[:self.max_results // 2]:
                    text = link.get_text(strip=True)
                    href = link['href']
                    
                    if not text or len(text) < 8:
                        continue
                    
                    if not (href.endswith('.html') or '/article/' in href):
                        continue
                    
                    full_link = href if href.startswith('http') else url + href
                    
                    # 尝试提取日期
                    date_str = ''
                    date_pattern = re.search(r'(\d{4}-\d{2}-\d{2})', text)
                    if not date_pattern:
                        date_pattern = re.search(r'(\d{4}/\d{2}/\d{2})', text)
                    if date_pattern:
                        date_str = date_pattern.group(1)
                    
                    pub_date = date.today()
                    if date_str:
                        try:
                            pub_date = datetime.strptime(date_str.replace('/', '-'), '%Y-%m-%d').date()
                        except:
                            pass
                    
                    results.append({
                        'source_type': 'NSFC',
                        'title': text,
                        'abstract': '',
                        'url': full_link,
                        'published_date': pub_date,
                        'signal_type': 'news',
                        'field': '自然科学'
                    })
                    
        except Exception as e:
            print(f"NSFC采集失败: {e}")
        
        return results
    
    def crawl_sciencenet(self):
        """采集科学网"""
        results = []
        url = "https://www.sciencenet.cn"
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                if response.encoding == 'ISO-8859-1':
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 查找新闻列表
                news_items = soup.find_all('div', class_='news-item')
                if not news_items:
                    news_items = soup.find_all('li', class_='list-group-item')
                
                for item in news_items[:self.max_results // 2]:
                    title_elem = item.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    href = title_elem['href']
                    
                    if not title or len(title) < 8:
                        continue
                    
                    full_link = href if href.startswith('http') else url + href
                    
                    results.append({
                        'source_type': 'Sciencenet',
                        'title': title,
                        'abstract': '',
                        'url': full_link,
                        'published_date': date.today(),
                        'signal_type': 'news',
                        'field': '综合科技'
                    })
                    
        except Exception as e:
            print(f"Sciencenet采集失败: {e}")
        
        return results
    
    def crawl_kjdb(self):
        """采集科技导报"""
        results = []
        url = "http://www.kjdb.org"
        
        try:
            response = self.session.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                if response.encoding == 'ISO-8859-1':
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                articles = soup.find_all('a', href=True)
                for link in articles[:self.max_results // 3]:
                    text = link.get_text(strip=True)
                    href = link['href']
                    
                    if not text or len(text) < 10:
                        continue
                    
                    if not (href.endswith('.html') or 'article' in href.lower()):
                        continue
                    
                    full_link = href if href.startswith('http') else url + href
                    
                    results.append({
                        'source_type': 'KJDB',
                        'title': text,
                        'abstract': '',
                        'url': full_link,
                        'published_date': date.today(),
                        'signal_type': 'news',
                        'field': '科技导报'
                    })
                    
        except Exception as e:
            print(f"科技导报采集失败: {e}")
        
        return results
    
    def crawl(self):
        """执行采集"""
        results = []
        
        # 采集各个网站
        results.extend(self.crawl_nsfc())
        results.extend(self.crawl_sciencenet())
        results.extend(self.crawl_kjdb())
        
        # 去重并限制数量
        seen = set()
        unique_results = []
        for r in results:
            key = r['title'] + r['url']
            if key not in seen and len(unique_results) < self.max_results:
                seen.add(key)
                unique_results.append(r)
        
        self.close()
        return unique_results
    
    def close(self):
        """关闭会话"""
        self.session.close()

# 测试
if __name__ == "__main__":
    print("🔍 测试中国学术期刊爬虫")
    print("搜索关键词:", "machine learning")
    print("=" * 60)
    
    crawler = ChineseJournalsCrawler(max_results=15)
    results = crawler.crawl()
    
    print(f"\n成功获取 {len(results)} 条数据")
    for i, result in enumerate(results[:10], 1):
        print(f"\n--- 第 {i} 条 ---")
        print(f"来源: {result['source_type']}")
        print(f"标题: {result['title'][:60]}...")
        print(f"链接: {result['url'][:80]}")
        print(f"日期: {result['published_date']}")
        print(f"领域: {result['field']}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
