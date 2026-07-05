"""
数据处理和分类模块 - 增强版
支持核心标签和扩展标签的分级分类，命中数优先+主题优先级规则
"""
import logging
from typing import Dict, List, Optional, Tuple
import re
from datetime import datetime, date
from config import CONFIG

THEME_CONFIG = CONFIG['themes']
logger = logging.getLogger(__name__)

class ThemeClassifier:
    """主题分类器 - 增强版"""
    
    @staticmethod
    def classify(title: str, abstract: str = "", field: str = "") -> Dict:
        """
        分类论文主题（增强版）
        返回详细的分类结果，包括命中标签、得分等
        """
        text = (title + " " + abstract + " " + field).lower()
        
        theme_scores = {}
        theme_matched_keywords = {}
        theme_matched_core = {}
        
        for bucket_id, bucket_config in THEME_CONFIG.items():
            core_keywords = bucket_config.get('core_keywords', [])
            extended_keywords = bucket_config.get('extended_keywords', [])
            priority = bucket_config.get('priority', 99)
            
            core_matches = [kw for kw in core_keywords if kw.lower() in text]
            extended_matches = [kw for kw in extended_keywords if kw.lower() in text]
            
            core_score = len(core_matches) * 2
            extended_score = len(extended_matches) * 1
            total_score = core_score + extended_score
            
            if total_score > 0:
                theme_scores[bucket_id] = {
                    'total_score': total_score,
                    'core_score': core_score,
                    'extended_score': extended_score,
                    'priority': priority
                }
                theme_matched_keywords[bucket_id] = core_matches + extended_matches
                theme_matched_core[bucket_id] = core_matches
        
        if not theme_scores:
            return {
                'theme_bucket': 'Other',
                'theme_name': '其他',
                'confidence': 0,
                'matched_keywords': [],
                'core_matched_keywords': [],
                'all_scores': {},
                'subject_tags': []
            }
        
        sorted_themes = sorted(
            theme_scores.items(),
            key=lambda x: (-x[1]['total_score'], x[1]['priority'])
        )
        
        best_theme = sorted_themes[0][0]
        best_score = sorted_themes[0][1]['total_score']
        max_possible_score = len(THEME_CONFIG[best_theme].get('core_keywords', [])) * 2 + \
                             len(THEME_CONFIG[best_theme].get('extended_keywords', [])) * 1
        confidence = min(best_score / max_possible_score if max_possible_score > 0 else 0, 1.0)
        
        subject_tags = THEME_CONFIG[best_theme].get('subject_tags', [])
        
        return {
            'theme_bucket': best_theme,
            'theme_name': THEME_CONFIG[best_theme]['name'],
            'confidence': round(confidence, 2),
            'matched_keywords': theme_matched_keywords.get(best_theme, []),
            'core_matched_keywords': theme_matched_core.get(best_theme, []),
            'all_scores': {k: v['total_score'] for k, v in theme_scores.items()},
            'subject_tags': subject_tags
        }
    
    @staticmethod
    def classify_simple(title: str, abstract: str = "", field: str = "") -> str:
        """简化版分类，只返回主题bucket ID（保持向后兼容）"""
        result = ThemeClassifier.classify(title, abstract, field)
        return result['theme_bucket']
    
    @staticmethod
    def get_theme_name(bucket_id: str) -> str:
        """获取主题名称"""
        if bucket_id in THEME_CONFIG:
            return THEME_CONFIG[bucket_id]['name']
        return "其他"
    
    @staticmethod
    def get_all_themes() -> List[Dict]:
        """获取所有主题配置"""
        result = []
        for bucket_id, config in THEME_CONFIG.items():
            result.append({
                'id': bucket_id,
                'name': config['name'],
                'core_keywords': config.get('core_keywords', []),
                'extended_keywords': config.get('extended_keywords', []),
                'subject_tags': config.get('subject_tags', []),
                'priority': config.get('priority', 99)
            })
        return sorted(result, key=lambda x: x['priority'])
    
    @staticmethod
    def get_theme_keywords(bucket_id: str) -> Dict:
        """获取指定主题的关键词配置"""
        if bucket_id in THEME_CONFIG:
            config = THEME_CONFIG[bucket_id]
            return {
                'core_keywords': config.get('core_keywords', []),
                'extended_keywords': config.get('extended_keywords', [])
            }
        return {'core_keywords': [], 'extended_keywords': []}

class TextbookMatcher:
    """教材匹配器 - 预留框架"""
    
    @staticmethod
    def match_textbook_units(subject_tags: List[str], keywords: List[str]) -> List[Dict]:
        """
        根据学科标签和关键词匹配教材单元（第一轮粗匹配）
        预留接口，待教材标签库建设完成后实现
        """
        matched_units = []
        
        textbook_library = TextbookMatcher._get_textbook_library()
        
        for unit in textbook_library:
            unit_tags = set(tag.lower() for tag in unit.get('subject_tags', []))
            subject_tag_set = set(tag.lower() for tag in subject_tags)
            keyword_set = set(kw.lower() for kw in keywords)
            
            tag_matches = unit_tags & subject_tag_set
            keyword_matches = keyword_set & set(kw.lower() for kw in unit.get('keywords', []))
            
            match_score = len(tag_matches) * 2 + len(keyword_matches) * 1
            
            if match_score > 0:
                matched_units.append({
                    'textbook': unit.get('textbook', ''),
                    'unit': unit.get('unit', ''),
                    'chapter': unit.get('chapter', ''),
                    'match_score': match_score,
                    'matched_tags': list(tag_matches),
                    'matched_keywords': list(keyword_matches)
                })
        
        return sorted(matched_units, key=lambda x: -x['match_score'])
    
    @staticmethod
    def _get_textbook_library() -> List[Dict]:
        """获取教材标签库（预留）"""
        return []
    
    @staticmethod
    def quick_match(subject_tags: List[str]) -> List[str]:
        """快速匹配学科关联（第一轮粗匹配）"""
        related_subjects = []
        for tag in subject_tags:
            tag_lower = tag.lower()
            if any(subj in tag_lower for subj in ['信息', '计算机', '智能', '软件', '电子']):
                related_subjects.extend(['信息技术', '通用技术'])
            elif any(subj in tag_lower for subj in ['生物', '医学', '生命']):
                related_subjects.extend(['生物学', '医学基础'])
            elif any(subj in tag_lower for subj in ['物理', '力学', '电磁', '量子']):
                related_subjects.extend(['物理学', '应用物理'])
            elif any(subj in tag_lower for subj in ['化学', '材料', '分子']):
                related_subjects.extend(['化学', '材料科学'])
            elif any(subj in tag_lower for subj in ['能源', '环境', '气候']):
                related_subjects.extend(['能源科学', '环境保护'])
            elif any(subj in tag_lower for subj in ['工程', '机械', '土木']):
                related_subjects.extend(['工程技术', '机械基础'])
        
        return list(set(related_subjects))

def clean_text(text: str) -> str:
    """清洗文本内容"""
    if not text:
        return ""
    
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    if len(text) > 2000:
        text = text[:2000] + "..."
    
    return text

def parse_date(date_str: Optional[str], default: date = None) -> Optional[date]:
    """解析日期字符串"""
    if not date_str:
        return default or date.today()
    
    if isinstance(date_str, date):
        return date_str
    
    formats = [
        '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
        '%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S %z',
        '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S',
        '%b %d %Y', '%d %b %Y',
        '%Y'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.date()
        except (ValueError, TypeError):
            continue
    
    return default or date.today()

def extract_keywords(text: str, max_count: int = 5) -> List[str]:
    """提取关键词（简单版本）"""
    if not text:
        return []
    
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
        'ought', 'used', 'it', 'its', 'this', 'that', 'these', 'those', 'we',
        'you', 'they', 'he', 'she', 'i', 'me', 'us', 'them', 'him', 'her',
        'my', 'your', 'his', 'her', 'its', 'our', 'their', 'what', 'which',
        'who', 'whom', 'whose', 'where', 'when', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
        'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
        'just', 'also', 'now', 'here', 'there', 'then', 'once', 'using',
        'use', 'used', 'uses', 'using', 'used', 'study', 'studies', 'result',
        'results', 'method', 'methods', 'approach', 'approaches', 'system',
        'systems', 'model', 'models', 'algorithm', 'algorithms', 'data',
        'information', 'knowledge', 'learning', 'learned', 'learn', 'learns',
        'training', 'trained', 'train', 'trains', 'testing', 'tested', 'test',
        'tests', 'evaluation', 'evaluated', 'evaluate', 'evaluates'
    }
    
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    word_counts = {}
    
    for word in words:
        if word not in stopwords:
            word_counts[word] = word_counts.get(word, 0) + 1
    
    sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
    return [word for word, count in sorted_words[:max_count]]
