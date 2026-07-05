"""
数据库管理模块 - 增强版
支持主题分类标签、人工审核、教材匹配预留
"""
import logging
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, date, timedelta
import hashlib
import json
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Text, Date, DateTime, Boolean, func, Float, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

from config import CONFIG

logger = logging.getLogger(__name__)

Base = declarative_base()

class Paper(Base):
    """论文/新闻数据表 - 增强版"""
    __tablename__ = 'papers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    title = Column(String(1024), nullable=False)
    abstract = Column(Text)
    url = Column(String(512))
    published_date = Column(Date, index=True)
    crawled_date = Column(DateTime, default=datetime.now, index=True)
    signal_type = Column(String(50), index=True)
    theme_bucket = Column(String(50), index=True)
    field = Column(String(100))
    content_hash = Column(String(64), index=True)
    is_starred = Column(Boolean, default=False, index=True)
    read_count = Column(Integer, default=0)
    tags = Column(Text)
    
    theme_confidence = Column(Float, default=0.0)
    matched_keywords = Column(Text)
    core_matched_keywords = Column(Text)
    subject_tags = Column(Text)
    
    is_manual_reviewed = Column(Boolean, default=False, index=True)
    manual_theme = Column(String(50))
    review_note = Column(Text)
    
    textbook_matches = Column(Text)
    
    def __repr__(self):
        return f"<Paper(id={self.id}, user_id={self.user_id}, title='{self.title[:30]}...')>"

class CrawlHistory(Base):
    """采集历史记录表"""
    __tablename__ = 'crawl_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    start_time = Column(DateTime, default=datetime.now)
    end_time = Column(DateTime)
    papers_added = Column(Integer, default=0)
    status = Column(String(20), default='pending')
    error_message = Column(Text)

class Favorite(Base):
    """收藏表"""
    __tablename__ = 'favorites'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    paper_id = Column(Integer, nullable=False, index=True)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

class UserSession(Base):
    """用户会话表 - 用于单点登录控制"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    token = Column(String(191), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    ip_address = Column(String(50))
    user_agent = Column(String(200))
    
    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, token='{self.token[:20]}...')>"

class DatabaseManager:
    """数据库管理器 - 增强版"""
    
    def __init__(self, db_config: Dict = None):
        if db_config is None:
            db_config = CONFIG['database']
        
        self.db_url = (
            f"mysql+pymysql://{db_config['user']}:{db_config['password']}"
            f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            f"?charset={db_config['charset']}"
        )
        self.engine = create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        
        try:
            Base.metadata.create_all(self.engine, checkfirst=True)
            logger.info("数据库表初始化成功")
        except Exception as e:
            if "Duplicate key" in str(e) or "key was too long" in str(e):
                logger.warning(f"表已存在或索引冲突，继续: {e}")
            else:
                logger.error(f"数据库表初始化失败: {e}")
                raise
    
    @contextmanager
    def get_session(self) -> Session:
        """获取数据库会话"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def compute_content_hash(self, title: str, abstract: str, url: str) -> str:
        """计算内容哈希用于去重"""
        content = f"{title}|{abstract}|{url}".encode('utf-8')
        return hashlib.sha256(content).hexdigest()
    
    def add_paper(self, paper_data: Dict, user_id: int = 1) -> bool:
        """添加单条论文数据"""
        with self.get_session() as session:
            content_hash = self.compute_content_hash(
                paper_data['title'], 
                paper_data.get('abstract', ''),
                paper_data.get('url', '')
            )
            
            existing = session.query(Paper).filter_by(user_id=user_id, content_hash=content_hash).first()
            if existing:
                return False
            
            paper = Paper(
                user_id=user_id,
                source_type=paper_data['source_type'],
                title=paper_data['title'],
                abstract=paper_data.get('abstract', ''),
                url=paper_data.get('url', ''),
                published_date=paper_data.get('published_date'),
                signal_type=paper_data.get('signal_type', 'paper'),
                theme_bucket=paper_data.get('theme_bucket', 'Other'),
                field=paper_data.get('field', ''),
                content_hash=content_hash,
                tags=paper_data.get('tags', ''),
                theme_confidence=paper_data.get('theme_confidence', 0.0),
                matched_keywords=paper_data.get('matched_keywords', ''),
                core_matched_keywords=paper_data.get('core_matched_keywords', ''),
                subject_tags=paper_data.get('subject_tags', ''),
                textbook_matches=paper_data.get('textbook_matches', '')
            )
            session.add(paper)
            return True
    
    def add_papers(self, papers_data: List[Dict], user_id: int = 1) -> Tuple[int, int]:
        """批量添加论文数据，返回(新增数, 重复数)"""
        added = 0
        duplicates = 0
        
        for paper_data in papers_data:
            try:
                if self.add_paper(paper_data, user_id):
                    added += 1
                else:
                    duplicates += 1
            except Exception as e:
                logger.error(f"添加论文失败: {e}")
                continue
        
        logger.info(f"用户 {user_id} 批量添加完成: 新增 {added} 条, 重复 {duplicates} 条")
        return added, duplicates
    
    def get_paper_by_id(self, paper_id: int, user_id: int = 1) -> Optional[Dict]:
        """根据ID获取论文详情（用户隔离）"""
        with self.get_session() as session:
            paper = session.query(Paper).filter(
                Paper.id == paper_id, 
                Paper.user_id == user_id
            ).first()
            return self._paper_to_dict(paper) if paper else None
    
    def get_papers(self, 
                  user_id: int = 1,
                  offset: int = 0, limit: int = 100,
                  source_type: Optional[str] = None,
                  theme_bucket: Optional[str] = None,
                  keyword: Optional[str] = None,
                  date_from: Optional[date] = None,
                  date_to: Optional[date] = None,
                  only_starred: bool = False,
                  only_unreviewed: bool = False,
                  order_by: str = 'published_date',
                  order_dir: str = 'desc',
                  core_keywords_filter: Optional[List[str]] = None,
                  extended_keywords_filter: Optional[List[str]] = None) -> List[Paper]:
        """查询论文列表（用户隔离）"""
        with self.get_session() as session:
            query = session.query(Paper).filter(Paper.user_id == user_id)
            
            if source_type:
                query = query.filter(Paper.source_type == source_type)
            if theme_bucket:
                query = query.filter(or_(
                    Paper.theme_bucket == theme_bucket,
                    Paper.manual_theme == theme_bucket
                ))
            if keyword:
                keyword = f"%{keyword}%"
                query = query.filter(Paper.title.like(keyword))
            if date_from:
                query = query.filter(Paper.published_date >= date_from)
            if date_to:
                query = query.filter(Paper.published_date <= date_to)
            if only_starred:
                query = query.filter(Paper.is_starred == True)
            if only_unreviewed:
                query = query.filter(Paper.is_manual_reviewed == False)
            
            # 标签联合过滤：核心标签和拓展标签可同时命中
            conditions = []
            if core_keywords_filter:
                conditions += [Paper.core_matched_keywords.like(f'%{kw}%') for kw in core_keywords_filter]
            if extended_keywords_filter:
                conditions += [Paper.matched_keywords.like(f'%{kw}%') for kw in extended_keywords_filter]
            if conditions:
                query = query.filter(or_(*conditions))
            
            if order_by == 'published_date':
                order_column = Paper.published_date
            elif order_by == 'theme_confidence':
                order_column = Paper.theme_confidence
            else:
                order_column = Paper.crawled_date
            
            if order_dir == 'desc':
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())
            
            papers = query.offset(offset).limit(limit).all()
            return [self._paper_to_dict(p) for p in papers]
    
    def get_paper_count(self, 
                       user_id: int = 1,
                       source_type: Optional[str] = None,
                       theme_bucket: Optional[str] = None,
                       keyword: Optional[str] = None,
                       date_from: Optional[date] = None,
                       date_to: Optional[date] = None,
                       only_starred: bool = False,
                       only_unreviewed: bool = False,
                       core_keywords_filter: Optional[List[str]] = None,
                       extended_keywords_filter: Optional[List[str]] = None) -> int:
        """获取论文总数（用户隔离）"""
        with self.get_session() as session:
            query = session.query(func.count(Paper.id)).filter(Paper.user_id == user_id)
            
            if source_type:
                query = query.filter(Paper.source_type == source_type)
            if theme_bucket:
                query = query.filter(or_(
                    Paper.theme_bucket == theme_bucket,
                    Paper.manual_theme == theme_bucket
                ))
            if keyword:
                keyword = f"%{keyword}%"
                query = query.filter(Paper.title.like(keyword))
            if date_from:
                query = query.filter(Paper.published_date >= date_from)
            if date_to:
                query = query.filter(Paper.published_date <= date_to)
            if only_starred:
                query = query.filter(Paper.is_starred == True)
            if only_unreviewed:
                query = query.filter(Paper.is_manual_reviewed == False)
            
            # 标签联合过滤：核心标签和拓展标签可同时命中
            conditions = []
            if core_keywords_filter:
                conditions += [Paper.core_matched_keywords.like(f'%{kw}%') for kw in core_keywords_filter]
            if extended_keywords_filter:
                conditions += [Paper.matched_keywords.like(f'%{kw}%') for kw in extended_keywords_filter]
            if conditions:
                query = query.filter(or_(*conditions))
            
            return query.scalar() or 0
    
    def _paper_to_dict(self, paper: Paper) -> Dict:
        """转换Paper对象为字典"""
        return {
            'id': paper.id,
            'user_id': paper.user_id,
            'source_type': paper.source_type,
            'title': paper.title,
            'abstract': paper.abstract,
            'url': paper.url,
            'published_date': paper.published_date,
            'crawled_date': paper.crawled_date,
            'signal_type': paper.signal_type,
            'theme_bucket': paper.manual_theme or paper.theme_bucket,
            'original_theme': paper.theme_bucket,
            'field': paper.field,
            'is_starred': paper.is_starred,
            'read_count': paper.read_count,
            'tags': paper.tags,
            'theme_confidence': paper.theme_confidence or 0.0,
            'matched_keywords': paper.matched_keywords or '',
            'core_matched_keywords': paper.core_matched_keywords or '',
            'subject_tags': paper.subject_tags or '',
            'is_manual_reviewed': paper.is_manual_reviewed or False,
            'manual_theme': paper.manual_theme,
            'review_note': paper.review_note or '',
            'textbook_matches': paper.textbook_matches or ''
        }
    
    def update_paper_theme(self, paper_id: int, user_id: int, theme_bucket: str, 
                          review_note: str = '', is_manual: bool = True,
                          matched_keywords: str = '', core_matched_keywords: str = '') -> bool:
        """更新论文主题分类（人工审核）"""
        with self.get_session() as session:
            paper = session.query(Paper).filter(
                Paper.id == paper_id, 
                Paper.user_id == user_id
            ).first()
            if paper:
                if is_manual:
                    paper.manual_theme = theme_bucket
                    paper.is_manual_reviewed = True
                    paper.review_note = review_note
                    if matched_keywords:
                        paper.matched_keywords = matched_keywords
                    if core_matched_keywords:
                        paper.core_matched_keywords = core_matched_keywords
                else:
                    paper.theme_bucket = theme_bucket
                    paper.manual_theme = None
                    paper.is_manual_reviewed = False
                return True
            return False
    
    def batch_reclassify_papers(self, user_id: int = 1, batch_size: int = 100) -> Dict:
        """批量重新分类论文（用于标签库更新后）"""
        from processor import ThemeClassifier
        
        total_updated = 0
        offset = 0
        
        while True:
            with self.get_session() as session:
                papers = session.query(Paper).filter(
                    Paper.user_id == user_id
                ).offset(offset).limit(batch_size).all()
                
                if not papers:
                    break
                
                for paper in papers:
                    classification = ThemeClassifier.classify(
                        paper.title, paper.abstract or '', paper.field or ''
                    )
                    
                    paper.theme_bucket = classification['theme_bucket']
                    paper.theme_confidence = classification['confidence']
                    paper.matched_keywords = ','.join(classification['matched_keywords'])
                    paper.core_matched_keywords = ','.join(classification['core_matched_keywords'])
                    paper.subject_tags = ','.join(classification['subject_tags'])
                    
                    if paper.is_manual_reviewed and paper.manual_theme:
                        pass
                    
                    total_updated += 1
                
                offset += batch_size
        
        logger.info(f"用户 {user_id} 重新分类完成，更新 {total_updated} 条记录")
        return {'updated': total_updated}
    
    def batch_ai_classify(self, user_id: int, results: list) -> int:
        """AI 分类结果批量写入（DeepSeek 返回结果直接入库）"""
        updated = 0
        with self.get_session() as session:
            papers = {p.id: p for p in session.query(Paper).filter(
                Paper.user_id == user_id
            ).all()}
        
            for r in results:
                title = r.get('title', '')
                theme = r.get('theme', 'Other')
                if theme == 'Other' or theme not in CONFIG['themes']:
                    continue
                
                # 按标题模糊匹配（取前60字符）
                title_key = title[:60].strip().lower()
                for pid, paper in papers.items():
                    if paper.title[:60].strip().lower() == title_key:
                        paper.manual_theme = theme
                        paper.is_manual_reviewed = True
                        paper.theme_confidence = r.get('confidence', 0.8)
                        paper.core_matched_keywords = ','.join(r.get('core_keywords', []))
                        paper.matched_keywords = ','.join(r.get('extended_keywords', []))
                        paper.subject_tags = ','.join(r.get('subject_tags', []))
                        paper.review_note = '[AI自动审核]'
                        updated += 1
                        break
            
            if updated > 0:
                session.commit()
        logger.info(f"AI 分类完成: 用户={user_id}, 更新={updated} 篇")
        return updated
    
    def toggle_star(self, paper_id: int, user_id: int = 1) -> bool:
        """切换收藏状态（用户隔离）"""
        with self.get_session() as session:
            paper = session.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
            if paper:
                paper.is_starred = not paper.is_starred
                return paper.is_starred
            return False
    
    def increment_read_count(self, paper_id: int, user_id: int = 1):
        """增加阅读计数（用户隔离）"""
        with self.get_session() as session:
            paper = session.query(Paper).filter(Paper.id == paper_id, Paper.user_id == user_id).first()
            if paper:
                paper.read_count += 1
    
    def get_statistics(self, user_id: int = 1) -> Dict[str, Any]:
        """获取统计数据（用户隔离）"""
        with self.get_session() as session:
            total = session.query(func.count(Paper.id)).filter(Paper.user_id == user_id).scalar() or 0
            papers_count = session.query(func.count(Paper.id)).filter(Paper.user_id == user_id, Paper.signal_type == 'paper').scalar() or 0
            news_count = session.query(func.count(Paper.id)).filter(Paper.user_id == user_id, Paper.signal_type == 'news').scalar() or 0
            sources = sorted(session.query(Paper.source_type, func.count(Paper.id)).filter(Paper.user_id == user_id).group_by(Paper.source_type).all(), key=lambda x: -x[1])
            themes = session.query(Paper.theme_bucket, func.count(Paper.id)).filter(Paper.user_id == user_id, Paper.theme_bucket.isnot(None)).group_by(Paper.theme_bucket).all()
            starred_count = session.query(func.count(Paper.id)).filter(Paper.user_id == user_id, Paper.is_starred == True).scalar() or 0
            reviewed_count = session.query(func.count(Paper.id)).filter(Paper.user_id == user_id, Paper.is_manual_reviewed == True).scalar() or 0
            
            return {
                'total': total,
                'papers': papers_count,
                'news': news_count,
                'sources': {s[0]: s[1] for s in sources},
                'themes': {t[0]: t[1] for t in themes},
                'starred': starred_count,
                'reviewed': reviewed_count,
                'unreviewed': total - reviewed_count
            }
    
    def initialize_sample_data(self, user_id: int = 1) -> int:
        """初始化示例数据（用户隔离）"""
        from processor import ThemeClassifier, clean_text, parse_date, extract_keywords
        
        sample_papers = [
            {
                'source_type': 'arXiv',
                'title': 'GPT-5: Advanced Reasoning and Multimodal Understanding',
                'abstract': 'We present GPT-5, the next generation of large language models with unprecedented reasoning capabilities and multimodal understanding. The model achieves state-of-the-art performance on multiple benchmarks including reasoning, mathematics, and creative writing tasks.',
                'url': 'https://arxiv.org/abs/2401.00001',
                'published_date': date(2024, 1, 15),
                'signal_type': 'paper',
                'field': 'cs.AI',
            },
            {
                'source_type': 'arXiv',
                'title': 'Diffusion Models for Scientific Discovery',
                'abstract': 'Diffusion models have revolutionized generative AI. This paper explores their applications in scientific discovery, including protein structure prediction, drug design, and materials science. We demonstrate significant improvements over existing methods.',
                'url': 'https://arxiv.org/abs/2401.00002',
                'published_date': date(2024, 1, 14),
                'signal_type': 'paper',
                'field': 'cs.LG',
            },
            {
                'source_type': 'PubMed',
                'title': 'CRISPR-Cas9 Gene Therapy for Sickle Cell Anemia',
                'abstract': 'Recent advances in CRISPR-Cas9 gene therapy have shown promising results in treating sickle cell anemia. This clinical trial demonstrates successful correction of the genetic mutation in 90% of patients, with no major adverse effects.',
                'url': 'https://pubmed.ncbi.nlm.nih.gov/38012345/',
                'published_date': date(2024, 1, 13),
                'signal_type': 'paper',
                'field': 'Medicine',
            },
            {
                'source_type': 'ScienceDaily',
                'title': 'New Solar Panel Technology Achieves 40% Efficiency',
                'abstract': 'Scientists have developed a new solar panel technology using perovskite materials that achieves over 40% efficiency, a significant breakthrough in renewable energy. The panels are also more affordable to produce.',
                'url': 'https://www.sciencedaily.com/releases/2024/01/240112103021.htm',
                'published_date': date(2024, 1, 12),
                'signal_type': 'news',
                'field': 'Renewable Energy',
            },
            {
                'source_type': 'OpenAlex',
                'title': 'Quantum Computing Breakthrough: Error Correction at Scale',
                'abstract': 'Researchers have achieved a major breakthrough in quantum error correction, enabling quantum computers to operate at much larger scales. This brings us closer to practical quantum computing applications.',
                'url': 'https://openalex.org/W1234567890',
                'published_date': date(2024, 1, 11),
                'signal_type': 'paper',
                'field': 'Quantum Physics',
            },
            {
                'source_type': 'RSS-Nature',
                'title': 'AI Breakthrough in Protein Folding Prediction',
                'abstract': 'DeepMind announces a major update to AlphaFold that can now predict the structure of complex protein complexes with unprecedented accuracy, accelerating drug discovery.',
                'url': 'https://www.nature.com/articles/d41586-024-00123-4',
                'published_date': date(2024, 1, 10),
                'signal_type': 'news',
                'field': 'Computational Biology',
            },
            {
                'source_type': 'arXiv',
                'title': 'Large Language Models for Climate Science Analysis',
                'abstract': 'We introduce ClimateLLM, a specialized large language model for climate science that can analyze complex climate data, generate insights, and assist in climate modeling and prediction.',
                'url': 'https://arxiv.org/abs/2401.00003',
                'published_date': date(2024, 1, 9),
                'signal_type': 'paper',
                'field': 'Climate Science',
            },
            {
                'source_type': 'PubMed',
                'title': 'mRNA Vaccine Technology for Cancer Treatment',
                'abstract': 'mRNA vaccine technology, made famous by COVID-19 vaccines, is now being applied to cancer treatment. Early trials show promising results in treating melanoma and other cancers.',
                'url': 'https://pubmed.ncbi.nlm.nih.gov/38012346/',
                'published_date': date(2024, 1, 8),
                'signal_type': 'paper',
                'field': 'Oncology',
            },
            {
                'source_type': 'ScienceDaily',
                'title': 'Revolutionary Battery Technology Doubles Electric Vehicle Range',
                'abstract': 'A new solid-state battery technology promises to double the range of electric vehicles while significantly reducing charging times. This could be the breakthrough needed for widespread EV adoption.',
                'url': 'https://www.sciencedaily.com/releases/2024/01/240108092134.htm',
                'published_date': date(2024, 1, 7),
                'signal_type': 'news',
                'field': 'Battery Technology',
            },
            {
                'source_type': 'RSS-Science',
                'title': 'New Materials for Next-Generation Electronics',
                'abstract': 'Researchers have developed novel 2D materials with exceptional electronic properties that could revolutionize the semiconductor industry and enable faster, more efficient electronics.',
                'url': 'https://www.science.org/content/article/new-materials-next-generation-electronics',
                'published_date': date(2024, 1, 6),
                'signal_type': 'news',
                'field': 'Materials Science',
            }
        ]
        
        formatted_papers = []
        for p in sample_papers:
            classification = ThemeClassifier.classify(p.get('title', ''), p.get('abstract', ''), p.get('field', ''))
            formatted_papers.append({
                'source_type': p.get('source_type', ''),
                'title': clean_text(p.get('title', '')),
                'abstract': clean_text(p.get('abstract', '')),
                'url': p.get('url', ''),
                'published_date': parse_date(p.get('published_date')),
                'signal_type': p.get('signal_type', 'paper'),
                'theme_bucket': classification['theme_bucket'],
                'field': p.get('field', ''),
                'tags': ','.join(extract_keywords((p.get('title', '') + ' ' + p.get('abstract', ''))[:1000])),
                'theme_confidence': classification['confidence'],
                'matched_keywords': ','.join(classification['matched_keywords']),
                'core_matched_keywords': ','.join(classification['core_matched_keywords']),
                'subject_tags': ','.join(classification['subject_tags'])
            })
        
        added, _ = self.add_papers(formatted_papers, user_id)
        return added
    
    def delete_all_papers(self, user_id: int = 1) -> int:
        """删除当前用户的所有论文数据（用户隔离）"""
        with self.get_session() as session:
            count = session.query(func.count(Paper.id)).filter(Paper.user_id == user_id).scalar() or 0
            session.query(Paper).filter(Paper.user_id == user_id).delete()
            session.query(CrawlHistory).filter(CrawlHistory.user_id == user_id).delete()
            session.query(Favorite).filter(Favorite.user_id == user_id).delete()
            return count

    def create_user_session(self, user_id: int, token: str, expires_at: datetime, ip_address: str = None, user_agent: str = None) -> bool:
        """创建用户会话（单点登录：先使旧会话失效）"""
        try:
            update_count = 0
            with self.get_session() as session:
                update_count = session.query(UserSession).filter(UserSession.user_id == user_id).update({
                    UserSession.is_active: False
                })
                logger.info(f"已使 {update_count} 个旧会话失效")
            
            with self.get_session() as session:
                session_obj = UserSession(
                    user_id=user_id,
                    token=token,
                    expires_at=expires_at,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    is_active=True
                )
                session.add(session_obj)
            
            logger.info(f"用户 {user_id} 创建新会话，旧会话已失效")
            return True
        except Exception as e:
            logger.error(f"创建用户会话失败: {e}")
            return False

    def validate_session(self, token: str) -> Optional[int]:
        """验证会话是否有效（单点登录验证）"""
        try:
            with self.get_session() as session:
                session_obj = session.query(UserSession).filter(
                    UserSession.token == token
                ).first()
                
                if not session_obj:
                    logger.warning(f"会话不存在: token={token[:20]}...")
                    return None
                
                now = datetime.now()
                if not session_obj.is_active:
                    logger.warning(f"会话已失效: user_id={session_obj.user_id}, token={token[:20]}...")
                    return None
                
                if session_obj.expires_at <= now:
                    logger.warning(f"会话已过期: user_id={session_obj.user_id}, expires_at={session_obj.expires_at}, now={now}")
                    return None
                
                logger.debug(f"会话验证成功: user_id={session_obj.user_id}")
                return session_obj.user_id
        except Exception as e:
            logger.error(f"验证会话失败: {e}")
            return None

    def invalidate_session(self, token: str) -> bool:
        """使指定会话失效"""
        try:
            with self.get_session() as session:
                session.query(UserSession).filter(UserSession.token == token).update({
                    UserSession.is_active: False
                })
            logger.info("会话已失效")
            return True
        except Exception as e:
            logger.error(f"使会话失效失败: {e}")
            return False

    def get_trend_data(self, user_id: int = 1, days: int = 30) -> pd.DataFrame:
        """获取时间趋势数据（用户隔离）"""
        with self.get_session() as session:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            results = session.query(
                func.date(Paper.published_date),
                func.count(Paper.id)
            ).filter(
                Paper.user_id == user_id,
                Paper.published_date >= start_date,
                Paper.published_date <= end_date
            ).group_by(
                func.date(Paper.published_date)
            ).order_by(func.date(Paper.published_date)).all()
            
            df = pd.DataFrame(results, columns=['date', 'count'])
            df['date'] = pd.to_datetime(df['date'])
            return df
    
    def add_crawl_history(self, user_id: int, source_type: str, papers_added: int, status: str = 'success', error: str = ''):
        """添加采集历史（用户隔离）"""
        with self.get_session() as session:
            history = CrawlHistory(
                user_id=user_id,
                source_type=source_type,
                start_time=datetime.now(),
                papers_added=papers_added,
                status=status,
                error_message=error
            )
            session.add(history)
    
    def export_to_csv(self, papers: List[Dict], filename: str):
        """导出为CSV"""
        df = pd.DataFrame(papers)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
    
    def export_to_excel(self, papers: List[Dict], filename: str):
        """导出为Excel"""
        df = pd.DataFrame(papers)
        df.to_excel(filename, index=False, engine='openpyxl')

db = DatabaseManager()
