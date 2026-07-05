"""
数据源接入测试脚本 - 前沿科技主题
测试用户提供的33个数据源，验证是否可以成功爬取文章资源

搜索主题：前沿科技（前沿技术、人工智能、量子计算、生命科学、新能源等）
"""
import requests
from bs4 import BeautifulSoup
from datetime import date, datetime
import re
import json
import time
import feedparser
from urllib.parse import urljoin, urlencode

class DataSourceTester:
    def __init__(self, search_topic="前沿科技", timeout=30):
        self.search_topic = search_topic
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        })
        
        self.data_sources = [
            {
                'name': '《中国科学》《科学通报》系列期刊',
                'url': 'https://www.scichina.com',
                'type': 'crawler',
                'search_url': 'https://www.scichina.com/search?keyword={keyword}',
                'tags': ['期刊', '中文']
            },
            {
                'name': '《中国科学院院刊》',
                'url': 'https://www.bulletin.cas.cn',
                'type': 'crawler',
                'search_url': None,
                'tags': ['期刊', '中文']
            },
            {
                'name': '《中国基础科学》《科技导报》',
                'url': 'http://www.kjdb.org',
                'type': 'crawler',
                'search_url': None,
                'tags': ['期刊', '中文']
            },
            {
                'name': '国家自然科学基金委',
                'url': 'https://www.nsfc.gov.cn',
                'type': 'crawler',
                'search_url': 'https://www.nsfc.gov.cn/nsfc/cen/xmzn/search.jsp?keyword={keyword}',
                'tags': ['官方', '中文']
            },
            {
                'name': '科普中国',
                'url': 'https://www.kepuchina.cn',
                'type': 'crawler',
                'search_url': 'https://www.kepuchina.cn/search?q={keyword}',
                'tags': ['科普', '中文']
            },
            {
                'name': '中国科普博览',
                'url': 'https://www.kepu.net.cn',
                'type': 'crawler',
                'search_url': None,
                'tags': ['科普', '中文']
            },
            {
                'name': '中国数字科技馆',
                'url': 'https://www.cdstm.cn',
                'type': 'crawler',
                'search_url': None,
                'tags': ['科普', '中文']
            },
            {
                'name': '果壳网',
                'url': 'https://www.guokr.com',
                'type': 'crawler',
                'search_url': 'https://www.guokr.com/search?q={keyword}',
                'tags': ['科普', '中文']
            },
            {
                'name': '知乎科学',
                'url': 'https://www.zhihu.com',
                'type': 'crawler',
                'search_url': 'https://www.zhihu.com/search?q={keyword}&type=content',
                'tags': ['社区', '中文']
            },
            {
                'name': '国家科技传播中心',
                'url': 'http://www.cccst.org.cn',
                'type': 'crawler',
                'search_url': None,
                'tags': ['官方', '中文']
            },
            {
                'name': '中国科学技术馆',
                'url': 'https://cstm.cdstm.cn',
                'type': 'crawler',
                'search_url': None,
                'tags': ['官方', '中文']
            },
            {
                'name': 'B站科普分区',
                'url': 'https://www.bilibili.com',
                'type': 'api',
                'search_url': 'https://api.bilibili.com/x/web-interface/search/type?keyword={keyword}&search_type=video&page=1&pagesize=10',
                'tags': ['视频', '中文']
            },
            {
                'name': '南方周末',
                'url': 'https://www.infzm.com',
                'type': 'crawler',
                'search_url': 'https://www.infzm.com/search?query={keyword}',
                'tags': ['媒体', '中文']
            },
            {
                'name': '中关村论坛',
                'url': 'https://www.zgcforum.com',
                'type': 'crawler',
                'search_url': None,
                'tags': ['官方', '中文']
            },
            {
                'name': 'Nature',
                'url': 'https://www.nature.com',
                'type': 'crawler',
                'search_url': 'https://www.nature.com/search?q={keyword}',
                'tags': ['期刊', '英文']
            },
            {
                'name': 'Science',
                'url': 'https://www.science.org',
                'type': 'crawler',
                'search_url': 'https://www.science.org/action/doSearch?field=All&text={keyword}',
                'tags': ['期刊', '英文']
            },
            {
                'name': 'Cell',
                'url': 'https://www.cell.com',
                'type': 'crawler',
                'search_url': 'https://www.cell.com/search?query={keyword}',
                'tags': ['期刊', '英文']
            },
            {
                'name': 'arXiv',
                'url': 'https://arxiv.org',
                'type': 'api',
                'search_url': 'https://export.arxiv.org/api/query?search_query={keyword}&start=0&max_results=10',
                'tags': ['预印本', '英文']
            },
            {
                'name': 'PubMed',
                'url': 'https://pubmed.ncbi.nlm.nih.gov',
                'type': 'api',
                'search_url': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={keyword}&retmax=10&retmode=json',
                'tags': ['论文', '英文']
            },
            {
                'name': 'ResearchGate',
                'url': 'https://www.researchgate.net',
                'type': 'crawler',
                'search_url': 'https://www.researchgate.net/search?q={keyword}',
                'tags': ['学术', '英文']
            },
            {
                'name': '诺贝尔奖官网',
                'url': 'https://www.nobelprize.org',
                'type': 'crawler',
                'search_url': 'https://www.nobelprize.org/search/?q={keyword}',
                'tags': ['官方', '英文']
            },
            {
                'name': 'Science X',
                'url': 'https://www.sciencex.com',
                'type': 'crawler',
                'search_url': 'https://www.sciencex.com/search?q={keyword}',
                'tags': ['媒体', '英文']
            },
            {
                'name': 'Phys.org',
                'url': 'https://phys.org',
                'type': 'crawler',
                'search_url': 'https://phys.org/search/?q={keyword}',
                'tags': ['媒体', '英文']
            },
            {
                'name': 'New Scientist',
                'url': 'https://www.newscientist.com',
                'type': 'crawler',
                'search_url': 'https://www.newscientist.com/search/?q={keyword}',
                'tags': ['媒体', '英文']
            },
            {
                'name': 'Science Daily',
                'url': 'https://www.sciencedaily.com',
                'type': 'rss',
                'search_url': 'https://www.sciencedaily.com/rss/top.xml',
                'tags': ['媒体', '英文']
            },
            {
                'name': '环球科学',
                'url': 'https://www.scientificamerican.com',
                'type': 'crawler',
                'search_url': 'https://www.scientificamerican.com/search/?q={keyword}',
                'tags': ['媒体', '中英']
            },
            {
                'name': '科学网',
                'url': 'https://www.sciencenet.cn',
                'type': 'crawler',
                'search_url': 'https://www.sciencenet.cn/search/?q={keyword}',
                'tags': ['媒体', '中文']
            },
            {
                'name': 'MIT Technology Review',
                'url': 'https://www.technologyreview.com',
                'type': 'rss',
                'search_url': 'https://www.technologyreview.com/feed/',
                'tags': ['媒体', '英文']
            },
            {
                'name': 'TechCrunch',
                'url': 'https://techcrunch.com',
                'type': 'rss',
                'search_url': 'https://techcrunch.com/feed/',
                'tags': ['媒体', '英文']
            },
            {
                'name': 'OpenAlex',
                'url': 'https://api.openalex.org',
                'type': 'api',
                'search_url': 'https://api.openalex.org/works?filter=title_and_abstract.search:{keyword}&per-page=10',
                'tags': ['学术', '英文']
            }
        ]
        
        self.search_keywords = [
            "前沿科技", "前沿技术", "advanced technology",
            "人工智能", "AI", "machine learning",
            "量子计算", "quantum computing",
            "生命科学", "life science",
            "新能源", "new energy",
            "材料科学", "materials science",
            "生物技术", "biotechnology"
        ]
    
    def test_all_sources(self):
        """测试所有数据源"""
        print("=" * 80)
        print(f"📡 数据源接入测试 - 搜索主题: {self.search_topic}")
        print(f"📊 测试数据源数量: {len(self.data_sources)}")
        print("=" * 80)
        
        results = []
        success_count = 0
        failed_count = 0
        
        for i, source in enumerate(self.data_sources, 1):
            print(f"\n{'=' * 80}")
            print(f"[{i}/{len(self.data_sources)}] {source['name']}")
            print(f"📍 网址: {source['url']}")
            print(f"🔧 类型: {source['type']}")
            print(f"🏷️ 标签: {', '.join(source['tags'])}")
            print("-" * 80)
            
            result = self.test_single_source(source)
            results.append(result)
            
            if result['success']:
                success_count += 1
                print(f"✅ 测试成功 - 获取到 {result['article_count']} 篇文章")
            else:
                failed_count += 1
                print(f"❌ 测试失败 - {result['error']}")
            
            time.sleep(1)
        
        print(f"\n{'=' * 80}")
        print("📈 测试结果汇总")
        print("=" * 80)
        print(f"✅ 成功: {success_count} / {len(self.data_sources)}")
        print(f"❌ 失败: {failed_count} / {len(self.data_sources)}")
        
        print("\n📋 成功数据源列表:")
        for r in results:
            if r['success']:
                print(f"  ✓ {r['name']} - {r['article_count']}篇文章")
        
        print("\n❌ 失败数据源列表:")
        for r in results:
            if not r['success']:
                print(f"  ✗ {r['name']} - {r['error']}")
        
        return results
    
    def test_single_source(self, source):
        """测试单个数据源"""
        result = {
            'name': source['name'],
            'url': source['url'],
            'type': source['type'],
            'success': False,
            'article_count': 0,
            'articles': [],
            'error': '',
            'response_time': 0
        }
        
        try:
            start_time = time.time()
            
            if source['type'] == 'api':
                articles = self._test_api(source)
            elif source['type'] == 'rss':
                articles = self._test_rss(source)
            else:
                articles = self._test_crawler(source)
            
            result['response_time'] = round(time.time() - start_time, 2)
            result['articles'] = articles
            result['article_count'] = len(articles)
            result['success'] = len(articles) > 0
            
            if articles:
                for article in articles[:3]:
                    title = article.get('title', '')[:50]
                    url = article.get('url', '')[:60]
                    print(f"  • {title}...")
                    if url:
                        print(f"    {url}")
            
        except Exception as e:
            result['error'] = str(e)[:100]
        
        return result
    
    def _test_api(self, source):
        """测试API类型数据源"""
        articles = []
        
        for keyword in self.search_keywords[:3]:
            try:
                encoded_keyword = keyword.replace(' ', '+')
                if source['search_url']:
                    url = source['search_url'].format(keyword=encoded_keyword)
                else:
                    url = source['url']
                
                print(f"🔍 尝试关键词: {keyword}")
                print(f"🌐 请求URL: {url}")
                
                response = self.session.get(url, timeout=self.timeout)
                print(f"📡 状态码: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        if source['name'] == 'arXiv':
                            articles.extend(self._parse_arxiv_api(data))
                        elif source['name'] == 'PubMed':
                            articles.extend(self._parse_pubmed_api(data))
                        elif source['name'] == 'OpenAlex':
                            articles.extend(self._parse_openalex_api(data))
                        elif source['name'] == 'B站科普分区':
                            articles.extend(self._parse_bilibili_api(data))
                        else:
                            articles.extend(self._parse_generic_api(data))
                            
                        if articles:
                            break
                            
                    except json.JSONDecodeError:
                        print(f"⚠️ 响应不是JSON格式，尝试XML/RSS解析")
                        if source['name'] == 'arXiv':
                            feed = feedparser.parse(response.content)
                            articles.extend(self._parse_arxiv_feed(feed))
                        else:
                            articles.extend(self._parse_html_response(response, source))
                        
            except Exception as e:
                print(f"⚠️ API请求失败: {e}")
                continue
        
        return articles[:10]
    
    def _test_rss(self, source):
        """测试RSS类型数据源"""
        articles = []
        
        try:
            url = source['search_url'] or source['url']
            print(f"🌐 RSS URL: {url}")
            
            response = self.session.get(url, timeout=self.timeout)
            print(f"📡 状态码: {response.status_code}")
            
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                
                if feed.entries:
                    for entry in feed.entries[:10]:
                        title = entry.get('title', '')
                        summary = entry.get('summary', '') or entry.get('description', '')
                        link = entry.get('link', '')
                        
                        if title and len(title) > 5:
                            articles.append({
                                'title': title,
                                'abstract': summary[:200],
                                'url': link,
                                'published_date': entry.get('published', date.today()),
                                'source_type': source['name']
                            })
                            
                    print(f"📰 RSS条目数: {len(feed.entries)}")
            
        except Exception as e:
            print(f"⚠️ RSS解析失败: {e}")
        
        return articles[:10]
    
    def _test_crawler(self, source):
        """测试爬虫类型数据源"""
        articles = []
        
        for keyword in self.search_keywords[:3]:
            try:
                if source['search_url']:
                    encoded_keyword = keyword.replace(' ', '%20')
                    url = source['search_url'].format(keyword=encoded_keyword)
                    print(f"🔍 尝试关键词: {keyword}")
                    print(f"🌐 搜索URL: {url}")
                else:
                    url = source['url']
                    print(f"🌐 访问URL: {url}")
                
                response = self.session.get(url, timeout=self.timeout)
                print(f"📡 状态码: {response.status_code}")
                
                if response.status_code == 200:
                    if response.encoding == 'ISO-8859-1':
                        response.encoding = 'utf-8'
                    
                    articles.extend(self._parse_html_response(response, source))
                    
                    if articles:
                        break
                        
            except Exception as e:
                print(f"⚠️ 请求失败: {e}")
                continue
        
        return articles[:10]
    
    def _parse_html_response(self, response, source):
        """解析HTML响应"""
        articles = []
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            selectors = [
                {'tag': 'article', 'attrs': {}},
                {'tag': 'div', 'attrs': {'class': True}},
                {'tag': 'li', 'attrs': {'class': True}},
                {'tag': 'h2', 'attrs': {}},
                {'tag': 'h3', 'attrs': {}},
                {'tag': 'a', 'attrs': {'href': True}}
            ]
            
            all_items = []
            for sel in selectors:
                items = soup.find_all(sel['tag'], sel['attrs'])[:30]
                all_items.extend(items)
            
            for item in all_items:
                text = item.get_text(strip=True)
                
                if not text or len(text) < 8:
                    continue
                
                if text in ['首页', '关于我们', '联系我们', '帮助中心', '网站地图', 'English']:
                    continue
                
                link_elem = item.find('a', href=True)
                if link_elem:
                    href = link_elem['href']
                else:
                    href = item.get('href', '')
                
                if not href:
                    continue
                
                if not (href.endswith('.html') or '/article/' in href or '/news/' in href or '/paper/' in href):
                    continue
                
                full_link = href if href.startswith('http') else urljoin(source['url'], href)
                
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
                
                articles.append({
                    'title': text[:200],
                    'abstract': '',
                    'url': full_link,
                    'published_date': pub_date,
                    'source_type': source['name'],
                    'field': source['tags'][0] if source['tags'] else '综合'
                })
            
            seen = set()
            unique_articles = []
            for a in articles:
                key = a['title'] + a['url']
                if key not in seen:
                    seen.add(key)
                    unique_articles.append(a)
            
            return unique_articles
        
        except Exception as e:
            print(f"⚠️ HTML解析失败: {e}")
            return []
    
    def _parse_arxiv_api(self, data):
        """解析arXiv API响应"""
        articles = []
        
        try:
            entries = data.get('feed', {}).get('entry', [])
            if isinstance(entries, dict):
                entries = [entries]
            
            for entry in entries[:10]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('id', '')
                
                articles.append({
                    'title': title,
                    'abstract': summary[:200],
                    'url': link,
                    'published_date': entry.get('published', date.today()),
                    'source_type': 'arXiv',
                    'field': '预印本'
                })
                
        except Exception as e:
            print(f"⚠️ arXiv解析失败: {e}")
        
        return articles
    
    def _parse_arxiv_feed(self, feed):
        """解析arXiv RSS/XML feed"""
        articles = []
        
        try:
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('id', '') or entry.get('link', '')
                
                articles.append({
                    'title': title,
                    'abstract': summary[:200],
                    'url': link,
                    'published_date': entry.get('published', date.today()),
                    'source_type': 'arXiv',
                    'field': '预印本'
                })
                
            print(f"📰 arXiv条目数: {len(feed.entries)}")
                
        except Exception as e:
            print(f"⚠️ arXiv Feed解析失败: {e}")
        
        return articles
    
    def _parse_pubmed_api(self, data):
        """解析PubMed API响应"""
        articles = []
        
        try:
            ids = data.get('esearchresult', {}).get('idlist', [])
            if ids:
                fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={','.join(ids[:10])}&retmode=json"
                response = self.session.get(fetch_url, timeout=self.timeout)
                fetch_data = response.json()
                
                for uid, article in fetch_data.get('result', {}).items():
                    if uid == 'uids':
                        continue
                    
                    articles.append({
                        'title': article.get('title', ''),
                        'abstract': '',
                        'url': f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                        'published_date': article.get('pubdate', date.today()),
                        'source_type': 'PubMed',
                        'field': '生命科学'
                    })
                    
        except Exception as e:
            print(f"⚠️ PubMed解析失败: {e}")
        
        return articles
    
    def _parse_openalex_api(self, data):
        """解析OpenAlex API响应"""
        articles = []
        
        try:
            results = data.get('results', [])
            
            for work in results[:10]:
                title = work.get('title', '') or 'Untitled'
                abstract = ''
                
                if work.get('abstract_inverted_index'):
                    idx = work['abstract_inverted_index']
                    max_pos = max(p for pos_list in idx.values() for p in pos_list)
                    words = [''] * (max_pos + 1)
                    for word, positions in idx.items():
                        for pos in positions:
                            if pos <= max_pos:
                                words[pos] = word
                    abstract = ' '.join(words)[:200]
                
                articles.append({
                    'title': title,
                    'abstract': abstract,
                    'url': work.get('doi', '') or work.get('id', ''),
                    'published_date': work.get('publication_date', date.today()),
                    'source_type': 'OpenAlex',
                    'field': work.get('primary_topic', {}).get('display_name', '') or '综合'
                })
                
        except Exception as e:
            print(f"⚠️ OpenAlex解析失败: {e}")
        
        return articles
    
    def _parse_bilibili_api(self, data):
        """解析B站API响应"""
        articles = []
        
        try:
            result = data.get('result', {})
            
            videos = result.get('list', [])
            if not videos:
                videos = result.get('video', {}).get('result', [])
            if not videos:
                videos = result.get('data', {}).get('list', [])
            
            for video in videos[:10]:
                bvid = video.get('bvid', '') or video.get('aid', '')
                if bvid:
                    articles.append({
                        'title': video.get('title', ''),
                        'abstract': video.get('desc', '')[:200],
                        'url': f"https://www.bilibili.com/video/{bvid}",
                        'published_date': date.today(),
                        'source_type': 'B站',
                        'field': '视频'
                    })
                
            print(f"📰 B站视频数: {len(videos)}")
                
        except Exception as e:
            print(f"⚠️ B站解析失败: {e}")
        
        return articles
    
    def _parse_generic_api(self, data):
        """通用API解析"""
        articles = []
        
        try:
            if isinstance(data, list):
                items = data[:10]
            elif isinstance(data, dict):
                items = data.get('results', [])[:10] or data.get('items', [])[:10] or data.get('data', [])[:10]
            else:
                return articles
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                title = item.get('title', '') or item.get('name', '') or item.get('headline', '')
                if not title or len(title) < 5:
                    continue
                
                articles.append({
                    'title': title,
                    'abstract': item.get('summary', '')[:200] or item.get('description', '')[:200],
                    'url': item.get('url', '') or item.get('link', '') or item.get('id', ''),
                    'published_date': item.get('published_date', '') or item.get('pub_date', '') or date.today(),
                    'source_type': 'API',
                    'field': '综合'
                })
                
        except Exception as e:
            print(f"⚠️ 通用API解析失败: {e}")
        
        return articles

if __name__ == "__main__":
    tester = DataSourceTester(search_topic="前沿科技")
    results = tester.test_all_sources()
    
    print("\n" + "=" * 80)
    print("💾 保存测试结果...")
    print("=" * 80)
    
    output_file = f"test_results_{date.today().strftime('%Y%m%d')}.json"
    
    def serialize_date(obj):
        if isinstance(obj, date):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=serialize_date)
    
    print(f"✅ 测试结果已保存到: {output_file}")
    
    print("\n" + "=" * 80)
    print("📝 测试报告")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"搜索主题: {tester.search_topic}")
    print(f"测试数据源: {len(results)}")
    
    success = sum(1 for r in results if r['success'])
    avg_response_time = sum(r.get('response_time', 0) for r in results) / len(results)
    total_articles = sum(r.get('article_count', 0) for r in results)
    
    print(f"\n📊 统计数据:")
    print(f"  - 成功数据源: {success}")
    print(f"  - 失败数据源: {len(results) - success}")
    print(f"  - 平均响应时间: {avg_response_time:.2f}秒")
    print(f"  - 总文章数: {total_articles}")
    
    print("\n✅ 推荐优先接入的数据源:")
    for r in results:
        if r['success'] and r['article_count'] >= 5:
            print(f"  🎯 {r['name']} - {r['article_count']}篇文章")
    
    print("\n⚠️ 需要特殊处理的数据源:")
    for r in results:
        if not r['success']:
            print(f"  ❓ {r['name']} - {r['error']}")