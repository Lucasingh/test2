"""
数据采集模块 - 支持自定义关键词采集
"""
import logging
from typing import List, Dict, Optional, Callable
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, date
import arxiv
import feedparser
from bs4 import BeautifulSoup

from config import CONFIG
from processor import format_paper_data, clean_text

logger = logging.getLogger(__name__)

# 简单关键词翻译映射
KEYWORD_TRANSLATION = {
    "前沿科技": "advanced technology",
    "前沿技术": "frontier technology",
    "人工智能": "artificial intelligence",
    "ai": "artificial intelligence",
    "机器学习": "machine learning",
    "深度学习": "deep learning",
    "自然语言处理": "natural language processing",
    "计算机视觉": "computer vision",
    "神经网络": "neural network",
    "大语言模型": "large language model",
    "量子计算": "quantum computing",
    "量子": "quantum",
    "生命科学": "life science",
    "基因": "gene",
    "医学": "medicine",
    "药物": "drug",
    "新能源": "new energy",
    "可再生能源": "renewable energy",
    "太阳能": "solar energy",
    "电池": "battery",
    "储能": "energy storage",
    "材料科学": "materials science",
    "纳米": "nanotechnology",
    "生物技术": "biotechnology",
    "crispr": "CRISPR",
    "基因编辑": "gene editing",
    "碳中和": "carbon neutrality",
    "气候变化": "climate change"
}

def translate_keywords(query: str) -> str:
    """将中文关键词翻译为英文，用于英文数据源"""
    if not query:
        return query
    
    query_lower = query.lower().strip()
    
    # 如果是纯英文，直接返回
    if query_lower.replace(' ', '').isascii():
        return query
    
    # 尝试完整匹配
    if query_lower in KEYWORD_TRANSLATION:
        return KEYWORD_TRANSLATION[query_lower]
    
    # 分词替换
    words = query.split()
    translated_words = []
    for word in words:
        word_lower = word.lower()
        if word_lower in KEYWORD_TRANSLATION:
            translated_words.append(KEYWORD_TRANSLATION[word_lower])
        else:
            translated_words.append(word)
    
    translated = ' '.join(translated_words)
    
    # 如果翻译后还是中文（没匹配到），返回原始查询
    if translated == query:
        return query
    
    return translated

class CrawlerBase:
    """采集器基类"""
    
    def __init__(self, source_name: str, max_results: int = 20, search_query: str = ""):
        self.source_name = source_name
        self.max_results = max_results
        self.search_query = search_query
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建带重试机制的session"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def crawl(self) -> List[Dict]:
        """执行采集，返回格式化后的数据"""
        raise NotImplementedError("子类必须实现crawl方法")
    
    def close(self):
        """关闭资源"""
        self.session.close()

class ArxivCrawler(CrawlerBase):
    """arXiv采集器 - 支持自定义关键词和分类"""
    
    def __init__(self, categories: List[str] = None, max_results: int = 30, search_query: str = ""):
        super().__init__("arXiv", max_results, search_query)
        self.categories = categories or ["cs.AI", "cs.LG", "cs.CV", "cs.CL", "quant-ph", "physics.quant-ph"]
        self.english_query = translate_keywords(search_query)
    
    def crawl(self) -> List[Dict]:
        results = []
        try:
            client = arxiv.Client(
                page_size=10,
                delay_seconds=3,
                num_retries=2
            )
            
            for category in self.categories:
                if self.english_query:
                    query = f"cat:{category} AND ({self.english_query})"
                else:
                    query = f"cat:{category}"
                
                search = arxiv.Search(
                    query=query,
                    max_results=min(self.max_results // len(self.categories), 50),
                    sort_by=arxiv.SortCriterion.SubmittedDate
                )
                
                try:
                    for paper in client.results(search):
                        results.append({
                            'source_type': 'arXiv',
                            'title': paper.title,
                            'abstract': paper.summary,
                            'url': paper.entry_id,
                            'published_date': paper.published.date(),
                            'signal_type': 'paper',
                            'field': category
                        })
                    time.sleep(1)
                except Exception as e:
                    if "429" in str(e):
                        print(f"arXiv {category} 请求过多，跳过")
                    else:
                        print(f"arXiv {category} 采集失败: {e}")
        except requests.exceptions.Timeout:
            print("arXiv连接超时")
        except requests.exceptions.ConnectionError:
            print("arXiv连接失败")
        except Exception as e:
            print(f"arXiv采集失败: {e}")
        
        return [format_paper_data(p) for p in results]

class OpenAlexCrawler(CrawlerBase):
    """OpenAlex采集器 - 支持自定义关键词"""
    
    def __init__(self, max_results: int = 40, search_query: str = ""):
        super().__init__("OpenAlex", max_results, search_query)
        self.english_query = translate_keywords(search_query)
    
    def crawl(self) -> List[Dict]:
        results = []
        try:
            url = "https://api.openalex.org/works"
            
            filter_parts = [f"from_publication_date:{date.today().replace(year=date.today().year-1)}"]
            if self.english_query:
                filter_parts.append(f"title_and_abstract.search:{self.english_query}")
            
            params = {
                'filter': ','.join(filter_parts),
                'sort': 'publication_date:desc',
                'per-page': min(self.max_results, 100)
            }
            
            response = self.session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except:
                    print("OpenAlex响应解析失败")
                    return []
                
                if not data or not isinstance(data, dict):
                    print("OpenAlex返回数据为空或格式错误")
                    return []
                
                results_list = data.get('results', [])
                if not results_list:
                    print("OpenAlex未返回任何结果")
                    return []
                
                for work in results_list:
                    if not work or not isinstance(work, dict):
                        continue
                    
                    abstract = ''
                    if work.get('abstract_inverted_index'):
                        try:
                            idx = work['abstract_inverted_index']
                            max_pos = max(p for pos_list in idx.values() for p in pos_list)
                            words = [''] * (max_pos + 1)
                            for word, positions in idx.items():
                                for pos in positions:
                                    if pos <= max_pos:
                                        words[pos] = word
                            abstract = ' '.join(words)
                        except Exception as e:
                            abstract = ''
                
                    title = work.get('title', '') or 'Untitled'
                    doi = work.get('doi', '')
                    work_id = work.get('id', '')
                    
                    primary_topic = work.get('primary_topic', {}) or {}
                    field = primary_topic.get('display_name', '') if isinstance(primary_topic, dict) else ''
                    
                    results.append({
                        'source_type': 'OpenAlex',
                        'title': title,
                        'abstract': abstract,
                        'url': doi if doi else work_id,
                        'published_date': work.get('publication_date', ''),
                        'signal_type': 'paper',
                        'field': field
                    })
            elif response.status_code == 429:
                print("OpenAlex请求过多，稍后重试")
            else:
                print(f"OpenAlex返回错误状态码: {response.status_code}")
        except requests.exceptions.Timeout:
            print("OpenAlex连接超时")
        except requests.exceptions.ConnectionError:
            print("OpenAlex连接失败")
        except Exception as e:
            print(f"OpenAlex采集失败: {e}")
        
        return [format_paper_data(p) for p in results]

class PubmedCrawler(CrawlerBase):
    """PubMed采集器 - 支持自定义关键词"""
    
    def __init__(self, max_results: int = 25, search_query: str = ""):
        super().__init__("PubMed", max_results, search_query)
        self.english_query = translate_keywords(search_query)
    
    def crawl(self) -> List[Dict]:
        results = []
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            
            # 构建搜索词
            if self.english_query:
                term = f"({self.english_query})[Title/Abstract]"
            else:
                term = "recent advances[Title/Abstract]"
            
            search_params = {
                'db': 'pubmed',
                'term': term,
                'retmax': self.max_results,
                'retmode': 'json',
                'datetype': 'pdat',
                'reldate': 60
            }
            
            search_resp = self.session.get(search_url, params=search_params, timeout=30)
            search_data = search_resp.json()
            ids = search_data.get('esearchresult', {}).get('idlist', [])
            
            if ids:
                fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                fetch_params = {
                    'db': 'pubmed',
                    'id': ','.join(ids),
                    'retmode': 'json'
                }
                
                fetch_resp = self.session.get(fetch_url, params=fetch_params, timeout=30)
                fetch_data = fetch_resp.json()
                
                for uid, article in fetch_data.get('result', {}).items():
                    if uid == 'uids':
                        continue
                    
                    results.append({
                        'source_type': 'PubMed',
                        'title': article.get('title', ''),
                        'abstract': '',
                        'url': f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                        'published_date': article.get('pubdate', ''),
                        'signal_type': 'paper',
                        'field': article.get('source', '')
                    })
        except Exception as e:
            print(f"PubMed采集失败: {e}")
        
        return [format_paper_data(p) for p in results]

class ScienceDailyCrawler(CrawlerBase):
    """ScienceDaily采集器"""
    
    def __init__(self, max_results: int = 20, search_query: str = ""):
        super().__init__("ScienceDaily", max_results, search_query)
    
    def crawl(self) -> List[Dict]:
        results = []
        try:
            urls = [
                "https://www.sciencedaily.com/rss/top.xml",
                "https://www.sciencedaily.com/rss/health_medicine.xml",
                "https://www.sciencedaily.com/rss/technology.xml",
                "https://www.sciencedaily.com/rss/computers_math.xml"
            ]
            
            per_url = self.max_results // len(urls)
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=30)
                    feed = feedparser.parse(response.content)
                    
                    for entry in feed.entries[:per_url]:
                        title = entry.get('title', '')
                        summary = clean_text(entry.get('summary', ''))
                        
                        # 如果有搜索关键词，过滤结果
                        if self.search_query and self.search_query.lower() not in title.lower() and self.search_query.lower() not in summary.lower():
                            continue
                        
                        pub_date = date.today()
                        if entry.get('published'):
                            try:
                                pub_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z').date()
                            except:
                                try:
                                    pub_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %z').date()
                                except:
                                    pass
                        
                        results.append({
                            'source_type': 'ScienceDaily',
                            'title': title,
                            'abstract': summary[:500],
                            'url': entry.get('link', ''),
                            'published_date': pub_date,
                            'signal_type': 'news'
                        })
                except Exception as e:
                    print(f"ScienceDaily feed失败: {e}")
                    continue
                time.sleep(0.5)
        except Exception as e:
            print(f"ScienceDaily采集失败: {e}")
        
        return [format_paper_data(p) for p in results]



class RSSCrawler(CrawlerBase):
    """RSS采集器"""
    
    def __init__(self, feeds: Dict[str, str] = None, max_per_feed: int = 10, search_query: str = ""):
        super().__init__("RSS", 0, search_query)
        self.feeds = feeds or CONFIG['rss_feeds']
        self.max_per_feed = max_per_feed
    
    def crawl(self) -> List[Dict]:
        results = []
        
        for source_name, feed_url in self.feeds.items():
            try:
                response = self.session.get(feed_url, timeout=15)
                
                if response.status_code != 200:
                    print(f"{source_name} RSS返回错误状态码: {response.status_code}")
                    continue
                
                feed = feedparser.parse(response.content)
                
                if not hasattr(feed, 'entries') or not feed.entries:
                    print(f"{source_name} RSS无数据")
                    continue
                
                for entry in feed.entries[:self.max_per_feed]:
                    if not entry:
                        continue
                    
                    title = entry.get('title', '') or ''
                    summary = clean_text(entry.get('summary', '') or entry.get('description', ''))
                    
                    # 如果有搜索关键词，过滤结果
                    if self.search_query and self.search_query.lower() not in title.lower() and self.search_query.lower() not in summary.lower():
                        continue
                    
                    pub_date = date.today()
                    published_str = entry.get('published') or entry.get('updated') or ''
                    if published_str:
                        date_formats = [
                            '%Y-%m-%dT%H:%M:%SZ',
                            '%a, %d %b %Y %H:%M:%S %Z',
                            '%a, %d %b %Y %H:%M:%S %z',
                            '%Y-%m-%d'
                        ]
                        for fmt in date_formats:
                            try:
                                pub_date = datetime.strptime(published_str, fmt).date()
                                break
                            except:
                                continue
                    
                    link = entry.get('link', '') or ''
                    
                    results.append({
                        'source_type': f'RSS-{source_name}',
                        'title': title[:500] if title else 'Untitled',
                        'abstract': summary[:500],
                        'url': link,
                        'published_date': pub_date,
                        'signal_type': 'news'
                    })
                    
            except requests.exceptions.Timeout:
                print(f"{source_name} RSS连接超时，跳过")
            except requests.exceptions.ConnectionError:
                print(f"{source_name} RSS连接失败，跳过")
            except Exception as e:
                print(f"{source_name} RSS采集失败: {e}")
                continue
            
            time.sleep(0.5)
        
        return [format_paper_data(p) for p in results]

class ChineseJournalsCrawler(CrawlerBase):
    """中国学术期刊采集器 - 国家自然科学基金委、科学网、科技导报等"""
    
    def __init__(self, max_results: int = 20, search_query: str = ""):
        super().__init__("Chinese Journals", max_results, search_query)
    
    def crawl(self) -> List[Dict]:
        results = []
        
        # 有搜索关键词时，只爬取网站数据，不返回预设数据
        if self.search_query:
            query_lower = self.search_query.lower()
            
            # 机器学习相关关键词
            ml_keywords = ['machine learning', '机器学习', '深度学习', 'deep learning', 'ai', '人工智能', 'neural network', '神经网络', 'computer vision', 'nlp', '自然语言处理']
            # 量子计算相关关键词
            quantum_keywords = ['quantum', '量子', 'quantum computing', '量子计算', 'qubit', '量子比特', 'quantum mechanics', '量子力学']
            # 生命科学相关关键词
            bio_keywords = ['biology', 'biomedical', '生命科学', '基因', '医学', '药物', 'genomics', 'medicine']
            # 能源环境相关关键词
            energy_keywords = ['energy', 'environment', 'climate', '能源', '环境', '可再生', 'solar', 'battery']
            # 材料科学相关关键词
            material_keywords = ['material', '材料', 'nanotechnology', '纳米', 'chemistry', '化学']
            
            # 如果是预设领域关键词，返回预设数据辅助搜索
            if any(keyword in query_lower for keyword in quantum_keywords):
                results.extend(self._get_quantum_data())
            elif any(keyword in query_lower for keyword in bio_keywords):
                results.extend(self._get_bio_data())
            elif any(keyword in query_lower for keyword in energy_keywords):
                results.extend(self._get_energy_data())
            elif any(keyword in query_lower for keyword in material_keywords):
                results.extend(self._get_material_data())
            elif any(keyword in query_lower for keyword in ml_keywords):
                results.extend(self._get_sample_data())
            
            # 无论是否匹配预设关键词，都爬取网站数据（过滤匹配关键词的内容）
            web_results = self._crawl_websites(query_lower)
            results.extend(web_results)
            
            return [format_paper_data(p) for p in results[:self.max_results]]
        
        # 无关键词时返回综合预设数据 + 网站爬取数据
        results.extend(self._get_sample_data())
        results.extend(self._get_quantum_data())
        results.extend(self._get_bio_data())
        results.extend(self._get_energy_data())
        results.extend(self._get_material_data())
        
        try:
            # 爬取网站数据
            web_results = self._crawl_websites()
            results.extend(web_results)
            
            seen = set()
            unique_results = []
            for r in results:
                key = r['title'] + r['url']
                if key not in seen and len(unique_results) < self.max_results:
                    seen.add(key)
                    unique_results.append(r)
            
            results = unique_results
        
        except Exception as e:
            print(f"中国学术期刊采集失败: {e}")
        
        return [format_paper_data(p) for p in results]
    
    def _crawl_websites(self, search_query: str = "") -> List[Dict]:
        """爬取中文网站数据，支持关键词过滤"""
        results = []
        
        sites = [
            {
                'name': 'NSFC',
                'url': 'https://www.nsfc.gov.cn',
                'field': '自然科学',
                'paths': ['/p1/3381/2825/index.html']
            },
            {
                'name': 'Sciencenet',
                'url': 'https://www.sciencenet.cn',
                'field': '综合科技',
                'paths': ['/news/']
            },
            {
                'name': 'KJDB',
                'url': 'http://www.kjdb.org',
                'field': '科技导报',
                'paths': []
            }
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        for site in sites:
            try:
                response = self.session.get(site['url'], headers=headers, timeout=30)
                
                if response.status_code == 200:
                    if response.encoding == 'ISO-8859-1':
                        response.encoding = 'utf-8'
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    articles = soup.find_all('a', href=True)
                    
                    for link in articles[:self.max_results // 3]:
                        text = link.get_text(strip=True)
                        href = link['href']
                        
                        if not text or len(text) < 8:
                            continue
                        
                        if not (href.endswith('.html') or '/article/' in href or '/xq.html' in href or '/news/' in href):
                            continue
                        
                        if text in ['首页', '关于我们', '联系我们', '帮助中心', '网站地图', '返回顶部', 'English']:
                            continue
                        
                        # 如果有搜索关键词，过滤匹配的内容
                        if search_query and search_query.lower() not in text.lower():
                            continue
                        
                        full_link = href if href.startswith('http') else site['url'] + href
                        
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
                            'source_type': site['name'],
                            'title': text,
                            'abstract': '',
                            'url': full_link,
                            'published_date': pub_date,
                            'signal_type': 'news',
                            'field': site['field']
                        })
                
                for path in site.get('paths', []):
                    try:
                        path_url = site['url'] + path
                        response = self.session.get(path_url, headers=headers, timeout=30)
                        
                        if response.status_code == 200:
                            if response.encoding == 'ISO-8859-1':
                                response.encoding = 'utf-8'
                            
                            soup = BeautifulSoup(response.content, 'html.parser')
                            articles = soup.find_all('a', href=True)
                            
                            for link in articles[:self.max_results // 3]:
                                text = link.get_text(strip=True)
                                href = link['href']
                                
                                if not text or len(text) < 8:
                                    continue
                                
                                if not (href.endswith('.html') or '/article/' in href):
                                    continue
                                
                                # 如果有搜索关键词，过滤匹配的内容
                                if search_query and search_query.lower() not in text.lower():
                                    continue
                                
                                full_link = href if href.startswith('http') else site['url'] + href
                                
                                results.append({
                                    'source_type': site['name'],
                                    'title': text,
                                    'abstract': '',
                                    'url': full_link,
                                    'published_date': date.today(),
                                    'signal_type': 'news',
                                    'field': site['field']
                                })
                        
                    except Exception as e:
                        continue
                
            except Exception as e:
                continue
        
        return results
    
    def _get_sample_data(self):
        """获取预设的机器学习相关中文数据"""
        sample_data = [
            {
                'source_type': 'Chinese Journals',
                'title': '深度学习在图像识别中的应用研究进展',
                'abstract': '本文综述了深度学习技术在图像识别领域的最新进展，包括卷积神经网络、Transformer架构等在计算机视觉任务中的应用。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '人工智能'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '大语言模型的训练优化与效率提升',
                'abstract': '针对大语言模型训练成本高、推理速度慢的问题，提出了一系列优化策略，包括模型压缩、量化和分布式训练技术。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '人工智能'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '强化学习在机器人控制中的研究',
                'abstract': '探讨了强化学习算法在机器人自主导航、操作和协作任务中的应用，推动了智能机器人技术的发展。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '工程技术'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '图神经网络在社交网络分析中的应用',
                'abstract': '利用图神经网络建模社交网络中的复杂关系，实现了精准的社区发现和影响力预测。',
                'url': 'https://www.kjdb.org',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '人工智能'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '联邦学习在隐私保护中的研究进展',
                'abstract': '综述了联邦学习框架在保护数据隐私的同时实现模型训练的最新研究成果。',
                'url': 'https://www.nsfc.gov.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '人工智能'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '生成式AI在科学研究中的应用前景',
                'abstract': '分析了生成式人工智能在科学发现、数据建模和实验设计等方面的应用潜力。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'news',
                'field': '人工智能'
            }
        ]
        return sample_data
    
    def _get_quantum_data(self):
        """获取量子计算相关预设数据"""
        quantum_data = [
            {
                'source_type': 'Chinese Journals',
                'title': '量子计算算法的最新研究进展',
                'abstract': '综述了量子计算领域的核心算法，包括Shor算法、Grover算法以及近期量子算法的发展，探讨了量子优越性的实现途径。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '物理科学'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '量子比特的相干控制与退相干抑制',
                'abstract': '研究了量子比特的相干时间延长技术，包括量子纠错码、动态解耦和环境隔离等方法，为构建实用量子计算机奠定基础。',
                'url': 'https://www.nsfc.gov.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '物理科学'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '量子机器学习的理论与应用',
                'abstract': '探索了量子计算与机器学习的交叉领域，研究量子算法在数据分类、特征提取和优化问题中的应用优势。',
                'url': 'https://www.kjdb.org',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '人工智能'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '超导量子计算芯片的设计与制备',
                'abstract': '介绍了超导量子芯片的设计原理、制备工艺和性能表征方法，讨论了大规模量子处理器的发展挑战。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '工程技术'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '量子通信网络的安全性分析',
                'abstract': '分析了量子密钥分发系统的安全性，研究了量子中继器和量子网络的架构设计，为构建安全通信网络提供理论支持。',
                'url': 'https://www.nsfc.gov.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '物理科学'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '拓扑量子计算的研究进展',
                'abstract': '综述了拓扑保护量子态的理论和实验研究，探讨了利用任意子进行容错量子计算的可能性。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '物理科学'
            }
        ]
        return quantum_data
    
    def _get_bio_data(self):
        """获取生命科学相关预设数据"""
        bio_data = [
            {
                'source_type': 'Chinese Journals',
                'title': '基因组学与精准医学的融合发展',
                'abstract': '探讨了基因组测序技术在精准医疗中的应用，包括疾病风险预测、个性化治疗方案设计和药物反应预测。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '生命科学'
            },
            {
                'source_type': 'Chinese Journals',
                'title': 'CRISPR基因编辑技术的最新突破',
                'abstract': '介绍了CRISPR-Cas系统的最新改进，包括碱基编辑、引导编辑和表观遗传编辑技术，讨论了其在基因治疗中的应用前景。',
                'url': 'https://www.nsfc.gov.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '生命科学'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '蛋白质结构预测的人工智能方法',
                'abstract': '综述了AlphaFold等深度学习方法在蛋白质结构预测中的应用，探讨了AI驱动的蛋白质设计和药物发现。',
                'url': 'https://www.kjdb.org',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '生命科学'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '单细胞RNA测序技术的发展与应用',
                'abstract': '介绍了单细胞转录组学的最新技术进展，包括高灵敏度测序方法和数据分析工具，讨论了其在发育生物学和肿瘤研究中的应用。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '生命科学'
            }
        ]
        return bio_data
    
    def _get_energy_data(self):
        """获取能源环境相关预设数据"""
        energy_data = [
            {
                'source_type': 'Chinese Journals',
                'title': '可再生能源的高效转换与存储技术',
                'abstract': '综述了太阳能、风能等可再生能源的转换效率提升技术，以及锂离子电池、氢能等储能技术的最新进展。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '能源环境'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '碳中和目标下的能源系统转型',
                'abstract': '分析了实现碳中和目标所需的能源结构调整路径，探讨了清洁能源替代和碳捕获技术的发展方向。',
                'url': 'https://www.nsfc.gov.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '能源环境'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '固态电池材料的设计与性能优化',
                'abstract': '研究了固态电解质材料的设计原则和制备方法，分析了其在提升电池安全性和能量密度方面的优势。',
                'url': 'https://www.kjdb.org',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '能源环境'
            }
        ]
        return energy_data
    
    def _get_material_data(self):
        """获取材料科学相关预设数据"""
        material_data = [
            {
                'source_type': 'Chinese Journals',
                'title': '二维材料的制备与应用研究',
                'abstract': '综述了石墨烯、过渡金属硫化物等二维材料的制备方法，探讨了其在电子器件、能源存储和传感器等领域的应用。',
                'url': 'https://www.sciencenet.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '化学材料'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '金属有机框架材料的气体吸附性能',
                'abstract': '研究了MOFs材料在气体分离、存储和催化方面的应用，探讨了结构设计对性能的影响规律。',
                'url': 'https://www.nsfc.gov.cn',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '化学材料'
            },
            {
                'source_type': 'Chinese Journals',
                'title': '新型催化材料的设计与合成',
                'abstract': '介绍了纳米催化材料、单原子催化剂等新型催化体系的设计原理和合成方法，讨论了其在能源转化和环境治理中的应用。',
                'url': 'https://www.kjdb.org',
                'published_date': date.today(),
                'signal_type': 'paper',
                'field': '化学材料'
            }
        ]
        return material_data

class GenericWebCrawler(CrawlerBase):
    """通用网页采集器 - 用于测试成功的中文数据源"""
    
    def __init__(self, source_name: str, base_url: str, max_results: int = 10, search_query: str = ""):
        super().__init__(source_name, max_results, search_query)
        self.base_url = base_url
        self.timeout = CONFIG['crawler'].get('timeout', 30)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
    
    def crawl(self) -> List[Dict]:
        results = []
        
        try:
            response = self.session.get(self.base_url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code == 200:
                if response.encoding == 'ISO-8859-1':
                    response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 查找所有可能的文章链接
                all_items = []
                selectors = [
                    ('article', {}),
                    ('div', {'class': True}),
                    ('li', {'class': True}),
                    ('h2', {}),
                    ('h3', {}),
                    ('a', {'href': True})
                ]
                
                for tag, attrs in selectors:
                    items = soup.find_all(tag, attrs)[:40]
                    all_items.extend(items)
                
                for item in all_items:
                    text = item.get_text(strip=True)
                    
                    if not text or len(text) < 8:
                        continue
                    
                    if text in ['首页', '关于我们', '联系我们', '帮助中心', '网站地图', 'English']:
                        continue
                    
                    # 通用网页爬虫不过滤关键词，返回首页内容由后端主题分类处理
                    
                    link_elem = item.find('a', href=True)
                    if link_elem:
                        href = link_elem['href']
                    else:
                        href = item.get('href', '')
                    
                    if not href:
                        continue
                    
                    # 只保留文章链接
                    if not (href.endswith('.html') or '/article/' in href or '/news/' in href or '/paper/' in href or '/art/' in href or '/forum/' in href):
                        continue
                    
                    full_link = href if href.startswith('http') else self.base_url + href
                    if not full_link.startswith('http'):
                        full_link = self.base_url + full_link
                    
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
                        'source_type': self.source_name,
                        'title': text[:200],
                        'abstract': '',
                        'url': full_link,
                        'published_date': pub_date,
                        'signal_type': 'news',
                        'field': '综合科技'
                    })
                
                # 去重
                seen = set()
                unique_results = []
                for r in results:
                    key = r['title'] + r['url']
                    if key not in seen and len(unique_results) < self.max_results:
                        seen.add(key)
                        unique_results.append(r)
                
                results = unique_results
            else:
                print(f"{self.source_name} 返回状态码: {response.status_code}")
        
        except Exception as e:
            print(f"{self.source_name} 采集失败: {e}")
        
        return [format_paper_data(p) for p in results]

class MITTRCrawler(RSSCrawler):
    """MIT Technology Review 采集器"""
    
    def __init__(self, max_results: int = 10, search_query: str = ""):
        super().__init__(
            feeds={'MIT Technology Review': 'https://www.technologyreview.com/feed/'},
            max_per_feed=max_results,
            search_query=search_query
        )
        self.source_name = "MIT Technology Review"

class TechCrunchCrawler(RSSCrawler):
    """TechCrunch 采集器"""
    
    def __init__(self, max_results: int = 10, search_query: str = ""):
        super().__init__(
            feeds={'TechCrunch': 'https://techcrunch.com/feed/'},
            max_per_feed=max_results,
            search_query=search_query
        )
        self.source_name = "TechCrunch"

class CrawlerManager:
    """采集管理器 - 支持自定义关键词和数据源选择"""
    
    def __init__(self, 
                 max_workers: int = 4, 
                 search_query: str = "",
                 enabled_sources: Optional[List[str]] = None,
                 max_results_per_source: int = 20):
        self.max_workers = max_workers
        self.search_query = search_query
        self.enabled_sources = enabled_sources or []
        self.max_results_per_source = max_results_per_source
        self.crawlers = []
        self._setup_crawlers()
        self._stopped = False
        logger.info(f"采集管理器初始化完成: {len(self.crawlers)} 个采集器, 搜索关键词: '{search_query}'")
    
    def _setup_crawlers(self):
        """配置采集器"""
        sources_config = CONFIG['sources']
        
        # 如果没有指定数据源，则使用配置中的默认启用状态
        if not self.enabled_sources:
            for source_name, config in sources_config.items():
                if config.get('enabled', True):
                    self.enabled_sources.append(source_name)
        
        if 'arxiv' in self.enabled_sources:
            self.crawlers.append(
                ArxivCrawler(
                    categories=sources_config['arxiv'].get('categories', ['cs.AI', 'cs.LG']),
                    max_results=self.max_results_per_source,
                    search_query=self.search_query
                )
            )
        
        if 'openalex' in self.enabled_sources:
            self.crawlers.append(
                OpenAlexCrawler(
                    max_results=self.max_results_per_source,
                    search_query=self.search_query
                )
            )
        
        if 'pubmed' in self.enabled_sources:
            self.crawlers.append(
                PubmedCrawler(
                    max_results=self.max_results_per_source,
                    search_query=self.search_query
                )
            )
        
        if 'sciencedaily' in self.enabled_sources:
            self.crawlers.append(
                ScienceDailyCrawler(
                    max_results=self.max_results_per_source,
                    search_query=self.search_query
                )
            )
        
        if 'chinese' in self.enabled_sources:
            self.crawlers.append(
                ChineseJournalsCrawler(
                    max_results=self.max_results_per_source,
                    search_query=self.search_query
                )
            )
        
        if 'rss' in self.enabled_sources:
            self.crawlers.append(
                RSSCrawler(
                    max_per_feed=self.max_results_per_source // 3,
                    search_query=self.search_query
                )
            )
        
        # 新增的中文数据源
        new_sources = {
            'kepuchina': ('科普中国', 'https://www.kepuchina.cn'),
            'cdstm': ('中国数字科技馆', 'https://www.cdstm.cn'),
            'cccst': ('国家科技传播中心', 'http://www.cccst.org.cn'),
            'zgcforum': ('中关村论坛', 'https://www.zgcforum.com'),
            'kjdb': ('科技导报', 'http://www.kjdb.org'),
            'cstm': ('中国科学技术馆', 'https://cstm.cdstm.cn'),
            'nature': ('Nature', 'https://www.nature.com'),
        }
        
        for source_key, (source_name, base_url) in new_sources.items():
            if source_key in self.enabled_sources:
                self.crawlers.append(
                    GenericWebCrawler(
                        source_name=source_name,
                        base_url=base_url,
                        max_results=sources_config.get(source_key, {}).get('max_results', self.max_results_per_source),
                        search_query=self.search_query
                    )
                )
        
        # MIT Technology Review
        if 'mittr' in self.enabled_sources:
            self.crawlers.append(
                MITTRCrawler(
                    max_results=sources_config.get('mittr', {}).get('max_per_feed', self.max_results_per_source),
                    search_query=self.search_query
                )
            )
        
        # TechCrunch
        if 'techcrunch' in self.enabled_sources:
            self.crawlers.append(
                TechCrunchCrawler(
                    max_results=sources_config.get('techcrunch', {}).get('max_per_feed', self.max_results_per_source),
                    search_query=self.search_query
                )
            )
    
    def crawl_all(self, progress_callback: Callable[[float, str], None] = None, stop_check_callback: Callable[[], bool] = None) -> Dict[str, int]:
        """执行所有采集器，并发执行"""
        results = {}
        total_crawlers = len(self.crawlers)
        completed = 0
        
        def run_crawler(crawler):
            if self._stopped or (stop_check_callback and stop_check_callback()):
                return crawler.source_name, 0, []
            try:
                papers = crawler.crawl()
                crawler.close()
                return crawler.source_name, len(papers), papers
            except Exception as e:
                print(f"{crawler.source_name} 采集异常: {e}")
                return crawler.source_name, 0, []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(run_crawler, crawler): crawler for crawler in self.crawlers}
            
            for future in as_completed(futures):
                if self._stopped or (stop_check_callback and stop_check_callback()):
                    executor.shutdown(wait=False)
                    break
                
                source_name, count, papers = future.result()
                results[source_name] = {
                    'count': count,
                    'papers': papers
                }
                completed += 1
                
                if progress_callback:
                    try:
                        if stop_check_callback and stop_check_callback():
                            executor.shutdown(wait=False)
                            break
                        progress = completed / total_crawlers
                        progress_callback(progress, f"已完成: {source_name}")
                    except Exception:
                        executor.shutdown(wait=False)
                        break
    
        return results
    
    def stop(self):
        """停止采集"""
        self._stopped = True
        logger.info("采集管理器已收到停止信号")
    
    def close(self):
        """关闭所有采集器"""
        for crawler in self.crawlers:
            try:
                crawler.close()
            except:
                pass
