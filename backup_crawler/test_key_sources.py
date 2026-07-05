"""
关键数据源测试脚本
"""
from test_data_sources import DataSourceTester

tester = DataSourceTester(search_topic='前沿科技')

test_sources = [
    {
        'name': 'arXiv', 
        'url': 'https://arxiv.org', 
        'type': 'api', 
        'search_url': 'https://export.arxiv.org/api/query?search_query={keyword}&start=0&max_results=10', 
        'tags': ['预印本', '英文']
    },
    {
        'name': 'B站科普分区', 
        'url': 'https://www.bilibili.com', 
        'type': 'api', 
        'search_url': 'https://api.bilibili.com/x/web-interface/search/all/v2?keyword={keyword}', 
        'tags': ['视频', '中文']
    },
    {
        'name': '科学网', 
        'url': 'https://www.sciencenet.cn', 
        'type': 'crawler', 
        'search_url': None, 
        'tags': ['媒体', '中文']
    },
    {
        'name': '知乎科学', 
        'url': 'https://www.zhihu.com', 
        'type': 'crawler', 
        'search_url': None, 
        'tags': ['社区', '中文']
    },
]

print('=' * 80)
print('🔍 关键数据源测试')
print('=' * 80)

for source in test_sources:
    print(f'\n--- {source["name"]} ---')
    result = tester.test_single_source(source)
    if result['success']:
        print(f'✅ 成功 - {result["article_count"]}篇文章')
        for article in result['articles'][:3]:
            print(f'  • {article["title"][:50]}...')
    else:
        print(f'❌ 失败 - {result["error"]}')