"""
主程序 - Streamlit界面（支持多用户并发 + JWT认证 + 主题分类增强版）
"""
import logging
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import io
import uuid
from pathlib import Path

from config import CONFIG
from database import db
from processor import ThemeClassifier, TextbookMatcher
from auth import auth_manager
from crawler import CrawlerManager, CHINESE_SOURCE_MAP
from tasks import RedisTaskManager
from ai_classifier import classify_papers

logger = logging.getLogger(__name__)

def init_user_session():
    if 'user_id' not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
        logger.info(f"新用户会话: {st.session_state.user_id[:8]}...")
    
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = None
    
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    
    if 'editing_paper_id' not in st.session_state:
        st.session_state.editing_paper_id = None
    
    if 'page' not in st.session_state:
        st.session_state.page = 1
    
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "dashboard"
    
    if 'search_keyword' not in st.session_state:
        st.session_state.search_keyword = ""
    
    if 'filter_starred' not in st.session_state:
        st.session_state.filter_starred = False
    
    if 'crawl_sources' not in st.session_state:
        st.session_state.crawl_sources = []
    
    if 'crawl_task_id' not in st.session_state:
        st.session_state.crawl_task_id = None
    
    if 'crawl_keyword' not in st.session_state:
        st.session_state.crawl_keyword = ""
    
    if 'crawl_in_progress' not in st.session_state:
        st.session_state.crawl_in_progress = False
    
    if 'crawl_completed' not in st.session_state:
        st.session_state.crawl_completed = False

init_user_session()

def get_current_user_id():
    current_user = st.session_state.get('current_user')
    if current_user and 'id' in current_user:
        return current_user['id']
    return 1

def render_login():
    st.title("🔐 登录")
    
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        username = st.text_input("用户名", key="login_username")
        password = st.text_input("密码", type="password", key="login_password")
        remember_me = st.checkbox("记住登录状态", value=True, key="remember_me")
        
        if st.button("登录", type="primary", key="login_button"):
            user = auth_manager.authenticate(username, password)
            if user:
                token = auth_manager.create_token(user)
                st.session_state.auth_token = token
                st.session_state.current_user = {
                    'id': user.id,
                    'username': user.username,
                    'full_name': user.full_name,
                    'email': user.email
                }
                st.session_state.remember_login = remember_me
                st.success(f"✅ 登录成功！欢迎, {user.full_name or user.username}")
                st.rerun()
            else:
                st.error("❌ 用户名或密码错误")
        
        st.markdown("""
        **默认管理员账号:**
        - 用户名: `admin`
        - 密码: `admin123`
        """)
    
    with tab2:
        new_username = st.text_input("新用户名", key="reg_username")
        new_email = st.text_input("邮箱", key="reg_email")
        new_password = st.text_input("密码", type="password", key="reg_password")
        confirm_password = st.text_input("确认密码", type="password", key="reg_confirm_password")
        full_name = st.text_input("姓名（可选）", key="reg_full_name")
        
        if st.button("注册", key="reg_button"):
            if new_password != confirm_password:
                st.error("❌ 两次输入的密码不一致")
            elif not new_username or not new_email or not new_password:
                st.error("❌ 请填写所有必填字段")
            else:
                if auth_manager.create_user(new_username, new_email, new_password, full_name):
                    st.success("✅ 注册成功！请登录")
                else:
                    st.error("❌ 注册失败，用户名或邮箱已存在")

def logout():
    token = st.session_state.get('auth_token')
    if token:
        db.invalidate_session(token)
    
    st.components.v1.html("""
    <script>
    window.parent.localStorage.removeItem('auth_token');
    </script>
    """, height=0)
    
    st.session_state.auth_token = None
    st.session_state.current_user = None
    st.success("✅ 已退出登录")
    st.rerun()

st.set_page_config(
    page_title=CONFIG['ui']['page_title'],
    page_icon=CONFIG['ui']['page_icon'],
    layout=CONFIG['ui']['layout'],
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
    }
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        text-align: center;
    }
    .stat-value {
        font-size: 2.5rem;
        font-weight: bold;
        color: #667eea;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .paper-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        transition: transform 0.2s, box-shadow 0.2s;
        position: relative;
    }
    .paper-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.12);
    }
    .tag {
        display: inline-block;
        background: #f0f0f0;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .source-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.75rem;
        margin-right: 0.5rem;
    }
    .theme-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.75rem;
        margin-right: 0.5rem;
    }
    .config-panel {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    
    .tooltip-container {
        position: relative;
        display: inline-block;
        cursor: pointer;
    }
    
    .tooltip-text {
        visibility: hidden;
        width: 400px;
        background-color: #333;
        color: #fff;
        text-align: left;
        border-radius: 8px;
        padding: 12px;
        position: absolute;
        z-index: 1000;
        bottom: 125%;
        left: 50%;
        margin-left: -200px;
        opacity: 0;
        transition: opacity 0.3s;
        box-shadow: 0 8px 24px rgba(0,0,0,0.25);
        font-size: 0.9rem;
        line-height: 1.5;
    }
    
    .tooltip-text::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -8px;
        border-width: 8px;
        border-style: solid;
        border-color: #333 transparent transparent transparent;
    }
    
    .tooltip-container:hover .tooltip-text {
        visibility: visible;
        opacity: 1;
        transition-delay: 0.5s;
    }
    
    .tooltip-title {
        font-weight: bold;
        margin-bottom: 8px;
        font-size: 1rem;
        color: #667eea;
    }
    
    .tooltip-abstract {
        color: #e0e0e0;
        margin-bottom: 8px;
        white-space: pre-wrap;
    }
    
    .tooltip-meta {
        font-size: 0.8rem;
        color: #aaa;
    }
    
    .hover-title {
        text-decoration: underline;
        text-decoration-color: transparent;
        transition: text-decoration-color 0.3s;
        cursor: pointer;
    }
    
    .hover-title:hover {
        text-decoration-color: #667eea;
    }

    .confidence-bar {
        height: 6px;
        border-radius: 3px;
        background: #e0e0e0;
        margin: 0.5rem 0;
        overflow: hidden;
    }
    .confidence-fill {
        height: 100%;
        border-radius: 3px;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        transition: width 0.3s;
    }
    .reviewed-badge {
        display: inline-block;
        background: #10b981;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.7rem;
        margin-left: 0.5rem;
    }
    .core-tag {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        color: white;
    }
    .extended-tag {
        background: #e0e7ff;
        color: #4338ca;
    }
    .edit-panel, [data-testid="stVerticalBlock"]:has(.edit-panel-marker) {
        background: #fafbfc;
        padding: 1rem 1.25rem;
        border-radius: 10px;
        margin: 0.75rem 0;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .brace-row {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        margin: 0.35rem 0;
    }
    .brace-mark {
        font-size: 1.8rem;
        font-weight: 300;
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1.2;
        font-family: 'Georgia', serif;
        user-select: none;
        flex-shrink: 0;
    }
    .brace-body {
        flex: 1;
        min-width: 0;
    }
    .brace-body h4 {
        margin: 0 0 0.35rem 0;
        font-size: 0.95rem;
        font-weight: 600;
        color: #374151;
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }
    .panel-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #e5e7eb, transparent);
        margin: 0.75rem 0;
    }
    .panel-title {
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .panel-title h3 {
        margin: 0;
        font-size: 1.05rem;
        font-weight: 600;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .unreviewed-badge {
        display: inline-block;
        background: #f59e0b;
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.7rem;
        margin-left: 0.5rem;
    }
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-primary"] p {
        white-space: nowrap;
        margin: 0;
    }
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"] {
        padding: 0.25rem 0.5rem !important;
        min-height: auto !important;
        height: auto !important;
    }
    [data-testid="stBaseButton-secondary"] p {
        font-size: 0.8rem !important;
    }
</style>
""", unsafe_allow_html=True)

DEFAULT_KEYWORDS = [
    "machine learning",
    "artificial intelligence",
    "deep learning",
    "climate change",
    "gene therapy",
    "quantum computing",
    "renewable energy",
    "cancer treatment",
    "robotics",
    "computer vision",
    "natural language processing"
]

def render_sidebar():
    user = st.session_state.get('current_user')
    if user:
        st.sidebar.markdown(f"""
        **👤 用户: {user.get('full_name') or user.get('username')}**
        ({user.get('email', '')})
        """)
        if st.sidebar.button("🚪 退出登录"):
            logout()
        st.sidebar.markdown("---")
    
    st.sidebar.subheader("📊 数据管理")
    
    if st.sidebar.button("🔄 重新分类所有论文"):
        user_id = get_current_user_id()
        result = db.batch_reclassify_papers(user_id)
        st.sidebar.success(f"重新分类完成，更新了 {result['updated']} 条记录")
        st.rerun()
    
    if st.sidebar.button("🗑️ 清空当前用户数据"):
        user_id = get_current_user_id()
        count = db.delete_all_papers(user_id)
        st.sidebar.success(f"已删除 {count} 条记录")
        st.rerun()
    
    if st.sidebar.button("📥 初始化示例数据"):
        user_id = get_current_user_id()
        added = db.initialize_sample_data(user_id)
        st.sidebar.success(f"已添加 {added} 条示例数据")
        st.rerun()

def render_dashboard():
    user_id = get_current_user_id()
    
    st.markdown("""
    <div class="main-header">
        <h1 style="margin:0;">🚀 跨学科前沿成果数据可视化面板</h1>
        <p style="margin:0.5rem 0 0 0;opacity:0.9;">实时追踪、智能分类、深度分析学术前沿动态</p>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        stats = db.get_statistics(user_id)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats['total']}</div>
                <div class="stat-label">📚 总成果数</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats['papers']}</div>
                <div class="stat-label">📄 论文数</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats['news']}</div>
                <div class="stat-label">📰 新闻数</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats.get('reviewed', 0)}</div>
                <div class="stat-label">✅ 已审核</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader("📊 主题分布")
            if stats['themes']:
                theme_data = pd.DataFrame({
                    '主题': [ThemeClassifier.get_theme_name(k) for k in stats['themes'].keys()],
                    '数量': list(stats['themes'].values())
                })
                fig = px.pie(theme_data, values='数量', names='主题', 
                            title='各主题成果分布',
                            color_discrete_sequence=px.colors.qualitative.Set3)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暂无主题数据")
        
        with col_chart2:
            st.subheader("📈 来源分布")
            if stats['sources']:
                source_data = pd.DataFrame({
                    '来源': list(stats['sources'].keys()),
                    '数量': list(stats['sources'].values())
                })
                fig = px.bar(source_data, x='来源', y='数量', 
                            title='各数据来源成果数量',
                            color='来源')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("暂无来源数据")
        
        st.markdown("---")
        st.subheader("📅 近期趋势")
        
        trend_data = db.get_trend_data(user_id, days=30)
        if not trend_data.empty:
            fig = px.line(trend_data, x='date', y='count', 
                         title='近30天新增成果趋势',
                         labels={'date': '日期', 'count': '新增数量'})
            fig.update_layout(xaxis_title='日期', yaxis_title='新增数量')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("暂无趋势数据")
            
        if stats.get('unreviewed', 0) > 0:
            st.markdown("---")
            col_info1, col_info2 = st.columns([3, 1])
            with col_info1:
                st.info(f"📝 有 {stats.get('unreviewed', 0)} 条成果待审核，点击下方按钮进入审核")
            with col_info2:
                if st.button("➡️ 去审核", type="primary"):
                    st.session_state.active_tab = "review"
                    st.rerun()
    
    except Exception as e:
        st.error(f"加载数据失败: {e}")

def render_papers():
    st.subheader("📚 数据浏览")
    
    user_id = get_current_user_id()
    
    col1, col2, col3, col4 = st.columns(4)
    
    keyword = col1.text_input("🔍 关键词", value=st.session_state.search_keyword, key="papers_search_keyword")
    st.session_state.search_keyword = keyword
    
    theme_options = ["全部"] + list(CONFIG['themes'].keys())
    selected_theme = col2.selectbox("🏷️ 主题", theme_options, 
                                  format_func=lambda x: "全部主题" if x == "全部" else ThemeClassifier.get_theme_name(x))
    
    source_options = ["全部"]
    try:
        stats = db.get_statistics(user_id)
        if stats['sources']:
            source_options += list(stats['sources'].keys())
    except:
        pass
    selected_source = col3.selectbox("🌐 来源", source_options)
    
    date_from = col4.date_input("📅 从", value=date.today() - timedelta(days=30))
    
    col5, col6, col7 = st.columns(3)
    date_to = col5.date_input("到", value=date.today())
    only_starred = col6.checkbox("⭐ 只看收藏", value=st.session_state.get('filter_starred', False))
    per_page = col7.slider("每页显示", 5, 30, 10)
    
    # 标签等级过滤 - 选择具体主题后显示，核心标签和拓展标签可同时命中
    selected_core_keywords = []
    selected_extended_keywords = []
    
    if selected_theme != "全部":
        st.markdown("---")
        theme_keywords = ThemeClassifier.get_theme_keywords(selected_theme)
        
        col_core, col_ext = st.columns(2)
        
        with col_core:
            selected_core_keywords = st.multiselect(
                "★ 核心标签（精确匹配）",
                theme_keywords['core_keywords'],
                key=f"core_tags_{selected_theme}"
            )
        
        with col_ext:
            selected_extended_keywords = st.multiselect(
                "☆ 拓展标签（补充展示）",
                theme_keywords['extended_keywords'],
                key=f"extended_tags_{selected_theme}"
            )
        
        st.markdown("---")
    
    try:
        filter_theme = selected_theme if selected_theme != "全部" else None
        filter_source = selected_source if selected_source != "全部" else None
        
        total_count = db.get_paper_count(
            user_id=user_id,
            source_type=filter_source,
            theme_bucket=filter_theme,
            keyword=keyword if keyword else None,
            date_from=date_from,
            date_to=date_to,
            only_starred=only_starred,
            core_keywords_filter=selected_core_keywords if selected_core_keywords else None,
            extended_keywords_filter=selected_extended_keywords if selected_extended_keywords else None
        )
        
        total_pages = (total_count + per_page - 1) // per_page
        
        has_tag_filter = selected_core_keywords or selected_extended_keywords
        if has_tag_filter:
            tag_parts = []
            if selected_core_keywords:
                tag_parts.append(f"★核心: {'、'.join(selected_core_keywords)}")
            if selected_extended_keywords:
                tag_parts.append(f"☆拓展: {'、'.join(selected_extended_keywords)}")
            st.info(f"📌 {' | '.join(tag_parts)} | 共找到 {total_count} 条记录（第 {st.session_state.page}/{max(1, total_pages)} 页）")
        elif keyword:
            st.info(f"搜索 '{keyword}' 共找到 {total_count} 条记录（第 {st.session_state.page}/{max(1, total_pages)} 页）")
        else:
            st.info(f"共找到 {total_count} 条记录（第 {st.session_state.page}/{max(1, total_pages)} 页）")
        
        offset = (st.session_state.page - 1) * per_page
        papers = db.get_papers(
            user_id=user_id,
            offset=offset,
            limit=per_page,
            source_type=filter_source,
            theme_bucket=filter_theme,
            keyword=keyword if keyword else None,
            date_from=date_from,
            date_to=date_to,
            only_starred=only_starred,
            core_keywords_filter=selected_core_keywords if selected_core_keywords else None,
            extended_keywords_filter=selected_extended_keywords if selected_extended_keywords else None
        )
        
        if papers:
            col_export1, col_export2, col_export3 = st.columns([2, 2, 6])
            if col_export1.button("📥 导出为 CSV"):
                export_csv(papers)
            if col_export2.button("📥 导出为 Excel"):
                export_excel(papers)
        
        for paper in papers:
            render_paper_card(paper, user_id)
        
        if total_pages > 1:
            col_prev, col_page, col_next = st.columns([1, 2, 1])
            
            if col_prev.button("⬅️ 上一页") and st.session_state.page > 1:
                st.session_state.page -= 1
                st.rerun()
            
            col_page.markdown(f"<div style='text-align:center'>第 {st.session_state.page} / {total_pages} 页</div>", 
                             unsafe_allow_html=True)
            
            if col_next.button("下一页 ➡️") and st.session_state.page < total_pages:
                st.session_state.page += 1
                st.rerun()
        
        elif not papers:
            if keyword:
                st.warning(f"⚠️ 未找到包含 '{keyword}' 的结果，请尝试其他关键词")
            else:
                st.info("暂无数据，请先添加示例数据或通过其他方式导入")
    
    except Exception as e:
        st.error(f"数据加载失败: {e}")

def get_theme_color(theme: str) -> str:
    colors = {
        'AI': '#667eea',
        'LifeScience': '#10b981',
        'Energy': '#f59e0b',
        'EarthSpace': '#ef4444',
        'Materials': '#8b5cf6',
        'Engineering': '#06b6d4',
        'Other': '#6b7280'
    }
    return colors.get(theme, '#6b7280')

def render_paper_card(paper: dict, user_id: int = 1, show_edit: bool = True):
    theme_color = get_theme_color(paper['theme_bucket'])
    theme_name = ThemeClassifier.get_theme_name(paper['theme_bucket'])
    abstract_full = paper['abstract'][:500] if paper['abstract'] else "暂无摘要"
    
    is_editing = st.session_state.get('editing_paper_id') == paper['id']
    
    with st.container():
        st.markdown(f"""
        <div class="paper-card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1rem;">
                <div style="flex:1">
                    <div class="tooltip-container">
                        <h3 class="hover-title" style="margin:0 0 0.5rem 0;">{paper['title']}</h3>
                        <div class="tooltip-text">
                            <div class="tooltip-title">{paper['title']}</div>
                            <div class="tooltip-abstract">{abstract_full}</div>
                            <div class="tooltip-meta">
                                <strong>来源:</strong> {paper['source_type']} | 
                                <strong>领域:</strong> {theme_name} | 
                                <strong>日期:</strong> {paper['published_date']}
                            </div>
                        </div>
                    </div>
                    <div style="margin-bottom:0.5rem;">
                        <span class="source-badge">{paper['source_type']}</span>
                        <span class="theme-badge" style="background:{theme_color};color:white;">
                            {theme_name}
                        </span>
                        {f"{'📰' if paper['signal_type'] == 'news' else '📄'}"}
                        {'<span class="reviewed-badge">✓ 已审核</span>' if paper.get('is_manual_reviewed') else '<span class="unreviewed-badge">待审核</span>'}
                    </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([3.5, 1])
        with col1:
            if paper['abstract']:
                st.write(paper['abstract'][:300] + "..." if len(paper['abstract']) > 300 else paper['abstract'])
            
            if paper.get('matched_keywords'):
                matched = paper['matched_keywords'].split(',') if paper['matched_keywords'] else []
                core_matched = paper.get('core_matched_keywords', '').split(',') if paper.get('core_matched_keywords') else []
                
                if matched:
                    st.markdown("<div style='margin-top:0.5rem;'>", unsafe_allow_html=True)
                    tags_html = ""
                    for kw in matched[:6]:
                        is_core = kw in core_matched
                        tag_class = "tag core-tag" if is_core else "tag extended-tag"
                        prefix = "★ " if is_core else "☆ "
                        tags_html += f"<span class='{tag_class}'>{prefix}{kw}</span>"
                    st.markdown(tags_html, unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
            
            if paper.get('theme_confidence', 0) > 0:
                confidence = paper['theme_confidence']
                st.markdown(f"""
                <div style="margin-top:0.5rem;font-size:0.8rem;color:#666;">
                    分类置信度: {int(confidence * 100)}%
                </div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width:{confidence * 100}%;"></div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            star_text = "⭐" if paper['is_starred'] else "☆"
            if show_edit:
                col_star, col_edit = st.columns([1.2, 1])
                with col_star:
                    if st.button(f"{star_text} 收藏", key=f"star_{paper['id']}", use_container_width=True):
                        db.toggle_star(paper['id'], user_id)
                        st.rerun()
                with col_edit:
                    if st.button("✏️ 编辑", key=f"edit_btn_{paper['id']}", use_container_width=True):
                        if is_editing:
                            st.session_state.editing_paper_id = None
                        else:
                            st.session_state.editing_paper_id = paper['id']
                        st.rerun()
            else:
                if st.button(f"{star_text} 收藏", key=f"star_{paper['id']}", use_container_width=True):
                    db.toggle_star(paper['id'], user_id)
                    st.rerun()
        
        if is_editing:
            render_edit_panel(paper, user_id)
        
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.markdown(f"📅 发布日期: {paper['published_date']}")
        with col_info2:
            if paper['tags']:
                tags = paper['tags'].split(',')
                st.markdown("🏷️ " + " ".join([f"<span class='tag'>{t}</span>" for t in tags[:3]]), 
                           unsafe_allow_html=True)
        with col_info3:
            if paper['url']:
                st.markdown(f"[🔗 查看原文]({paper['url']})")
        
        if paper.get('subject_tags'):
            st.markdown(f"""
            <div style="margin-top:0.5rem;font-size:0.8rem;color:#666;">
                📚 学科标签: {paper['subject_tags']}
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div></div>", unsafe_allow_html=True)

def render_edit_panel(paper: dict, user_id: int):
    with st.container():
        st.markdown('<span class="edit-panel-marker" style="display:none;"></span>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="panel-title">
            <h3>✏️ 编辑主题分类</h3>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)
        
        col_left, col_right = st.columns([3, 2])
        
        with col_left:
            st.markdown("""
            <div class="brace-row">
                <span class="brace-mark">{</span>
                <div class="brace-body">
                    <h4>📋 分类设置</h4>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            all_themes = ThemeClassifier.get_all_themes()
            theme_options = [(t['id'], t['name']) for t in all_themes]
            theme_options.append(('Other', '其他'))
            
            current_theme = paper.get('manual_theme') or paper.get('theme_bucket', 'Other')
            
            selected_theme = st.selectbox(
                "选择主题分类",
                options=[t[0] for t in theme_options],
                format_func=lambda x: dict(theme_options).get(x, x),
                index=[i for i, t in enumerate(theme_options) if t[0] == current_theme][0] if any(t[0] == current_theme for t in theme_options) else 0,
                key=f"edit_theme_{paper['id']}",
                label_visibility="collapsed"
            )
            
            review_note = st.text_area(
                "审核备注（可选）",
                value=paper.get('review_note', ''),
                height=70,
                key=f"edit_note_{paper['id']}",
                placeholder="输入审核备注..."
            )
        
        with col_right:
            st.markdown("""
            <div class="brace-row">
                <span class="brace-mark">{</span>
                <div class="brace-body">
                    <h4>💡 辅助信息</h4>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            theme_keywords = ThemeClassifier.get_theme_keywords(selected_theme)
            
            # 当前已匹配的标签（逗号分隔字符串 → 列表）
            current_matched = [kw.strip() for kw in (paper.get('matched_keywords') or '').split(',') if kw.strip()]
            current_core = [kw.strip() for kw in (paper.get('core_matched_keywords') or '').split(',') if kw.strip()]
            
            selected_core = st.multiselect(
                "★ 核心标签",
                theme_keywords['core_keywords'],
                default=[kw for kw in current_core if kw in theme_keywords['core_keywords']],
                key=f"edit_core_tags_{paper['id']}"
            )
            
            selected_extended = st.multiselect(
                "☆ 扩展标签",
                theme_keywords['extended_keywords'],
                default=[kw for kw in current_matched if kw in theme_keywords['extended_keywords']],
                key=f"edit_ext_tags_{paper['id']}"
            )
            
            if selected_theme != 'Other':
                subject_tags = CONFIG['themes'].get(selected_theme, {}).get('subject_tags', [])
                if subject_tags:
                    st.markdown(f"**📚 学科:** {', '.join(subject_tags)}")
        
        st.markdown('<div class="panel-divider"></div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="brace-row">
            <span class="brace-mark">{</span>
            <div class="brace-body">
                <h4>⚡ 操作</h4>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col_save, col_cancel, col_reset = st.columns([1, 1, 1])
        
        if col_save.button("💾 保存", key=f"save_edit_{paper['id']}", type="primary", use_container_width=True):
            db.update_paper_theme(
                paper['id'], user_id, selected_theme, review_note,
                is_manual=True,
                matched_keywords=','.join(selected_extended),
                core_matched_keywords=','.join(selected_core)
            )
            st.session_state.editing_paper_id = None
            st.success("✅ 主题分类已更新")
            st.rerun()
        
        if col_cancel.button("❌ 取消", key=f"cancel_edit_{paper['id']}", use_container_width=True):
            st.session_state.editing_paper_id = None
            st.rerun()
        
        if col_reset.button("🔄 恢复", key=f"reset_edit_{paper['id']}", use_container_width=True):
            # 重新自动分类，还原原始关键词
            cls_result = ThemeClassifier.classify(
                paper.get('title', ''), paper.get('abstract', ''), paper.get('field', '')
            )
            db.update_paper_theme(
                paper['id'], user_id, paper.get('original_theme', paper['theme_bucket']),
                '', is_manual=False,
                matched_keywords=','.join(cls_result['matched_keywords']),
                core_matched_keywords=','.join(cls_result['core_matched_keywords'])
            )
            st.session_state.editing_paper_id = None
            st.info("已恢复自动分类")
            st.rerun()

def render_review_page():
    st.subheader("📋 审核文献")
    
    user_id = get_current_user_id()
    
    stats = db.get_statistics(user_id)
    unreviewed_count = stats.get('unreviewed', 0)
    
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("待审核", unreviewed_count)
    col_info2.metric("已审核", stats.get('reviewed', 0))
    col_info3.metric("总计", stats.get('total', 0))
    
    # AI 一键审核
    if unreviewed_count > 0:
        st.markdown("---")
        col_btn, col_info = st.columns([1, 3])
        with col_btn:
            if st.button("🤖 AI 一键审核", type="primary", use_container_width=True, 
                         disabled=unreviewed_count == 0,
                         help=f"调用 DeepSeek AI 对 {unreviewed_count} 篇未审核文献自动分类"):
                with st.spinner(f"AI 正在审核 {unreviewed_count} 篇文献..."):
                    from database import Paper
                    with db.get_session() as session:
                        unreviewed = session.query(Paper).filter(
                            Paper.user_id == user_id,
                            Paper.is_manual_reviewed == False
                        ).all()
                        paper_list = [{"id": p.id, "title": p.title, "abstract": p.abstract or "", "source_type": p.source_type} for p in unreviewed]
                    
                    # 分批处理（每批10篇）
                    total_updated = 0
                    batch_size = 10
                    for i in range(0, len(paper_list), batch_size):
                        batch = paper_list[i:i+batch_size]
                        results = classify_papers(batch)
                        if results:
                            updated = db.batch_ai_classify(user_id, results)
                            total_updated += updated
                    
                    if total_updated > 0:
                        st.success(f"🎉 AI 审核完成！共处理 {total_updated} 篇文献")
                    else:
                        st.error("AI 审核失败，请稍后重试")
                    st.rerun()
        with col_info:
            st.caption("调用 DeepSeek AI 自动对未审核文献进行分类和打标签，无需人工逐个审核")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    show_unreviewed = col1.checkbox("只看未审核", value=True)
    selected_theme = col2.selectbox(
        "筛选主题",
        ["全部"] + list(CONFIG['themes'].keys()),
        format_func=lambda x: "全部主题" if x == "全部" else ThemeClassifier.get_theme_name(x)
    )
    per_page = col3.slider("每页显示", 3, 20, 5)
    
    try:
        filter_theme = selected_theme if selected_theme != "全部" else None
        
        total_count = db.get_paper_count(
            user_id=user_id,
            theme_bucket=filter_theme,
            only_unreviewed=show_unreviewed
        )
        
        total_pages = (total_count + per_page - 1) // per_page
        
        st.info(f"共 {total_count} 条记录待审核（第 {st.session_state.get('review_page', 1)}/{max(1, total_pages)} 页）")
        
        offset = (st.session_state.get('review_page', 1) - 1) * per_page
        papers = db.get_papers(
            user_id=user_id,
            offset=offset,
            limit=per_page,
            theme_bucket=filter_theme,
            only_unreviewed=show_unreviewed,
            order_by='theme_confidence',
            order_dir='asc'
        )
        
        for paper in papers:
            render_paper_card(paper, user_id, show_edit=True)
        
        if total_pages > 1:
            col_prev, col_page, col_next = st.columns([1, 2, 1])
            
            if col_prev.button("⬅️ 上一页", key="review_prev") and st.session_state.get('review_page', 1) > 1:
                st.session_state.review_page = st.session_state.get('review_page', 1) - 1
                st.rerun()
            
            col_page.markdown(f"<div style='text-align:center'>第 {st.session_state.get('review_page', 1)} / {total_pages} 页</div>", 
                             unsafe_allow_html=True)
            
            if col_next.button("下一页 ➡️", key="review_next") and st.session_state.get('review_page', 1) < total_pages:
                st.session_state.review_page = st.session_state.get('review_page', 1) + 1
                st.rerun()
        
        if not papers:
            if show_unreviewed:
                st.success("🎉 所有成果都已审核完成！")
            else:
                st.info("暂无数据")
    
    except Exception as e:
        st.error(f"加载数据失败: {e}")

def render_crawl_page():
    """数据采集页面 - 选择数据源、输入关键词、启动采集并查看进度"""
    st.subheader("📡 数据采集")

    # 初始化任务管理器
    task_manager = RedisTaskManager()

    # --- 采集配置区 ---
    with st.container():
        st.markdown('<div class="config-panel">', unsafe_allow_html=True)
        st.markdown("**⚙️ 采集配置**")

        col1, col2 = st.columns([3, 2])

        with col1:
            # 搜索关键词
            keyword = st.text_input(
                "🔍 搜索关键词（可选，中文关键词会自动翻译）",
                value=st.session_state.crawl_keyword,
                placeholder="输入关键词，留空则采集最新数据...",
                key="crawl_keyword_input",
            )

        with col2:
            # 每源最大结果数
            max_results = st.number_input(
                "📊 每源最大采集数", min_value=1, max_value=50, value=10, step=5
            )

        # 数据源选择 - 全选/取消
        all_sources = {
            'arxiv': 'arXiv 预印本',
            'openalex': 'OpenAlex 开放学术',
            'pubmed': 'PubMed 生物医学',
            'sciencedaily': 'Science Daily',
            'mittr': 'MIT Technology Review',
            'techcrunch': 'TechCrunch',
            'rss': '国际期刊 RSS 订阅',
            'kepuchina': '中国科普博览',
            'cdstm': '中国数字科技馆',
            'cccst': '国家科技传播中心',
            'zgcforum': '中关村论坛',
            'kjdb': '科技导报',
            'cstm': '中国科学技术馆',
            'nature': 'Nature',
            'chinese': '中文学术期刊',
        }

        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            selected_sources = st.multiselect(
                "🌐 选择数据源",
                options=list(all_sources.keys()),
                default=st.session_state.crawl_sources or [],
                format_func=lambda x: all_sources[x],
                placeholder="选择要采集的数据源...",
                key="crawl_sources_select",
            )
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            col_a, col_b = st.columns(2)
            if col_a.button("全选", use_container_width=True):
                st.session_state.crawl_sources = list(all_sources.keys())
                st.rerun()
            if col_b.button("取消", use_container_width=True):
                st.session_state.crawl_sources = []
                st.rerun()

        # 更新 session_state
        st.session_state.crawl_sources = selected_sources
        st.session_state.crawl_keyword = keyword

        # 操作按钮
        col_start, col_status = st.columns([1, 3])
        with col_start:
            can_start = selected_sources and not st.session_state.crawl_in_progress
            if can_start and st.button("🚀 开始采集", type="primary", use_container_width=True):
                user_id = get_current_user_id()
                task_id = task_manager.create_crawl_task(
                    user_id=user_id,
                    sources=selected_sources,
                    query=keyword,
                    max_results=max_results,
                )
                st.session_state.crawl_task_id = task_id
                st.session_state.crawl_in_progress = True
                st.session_state.crawl_completed = False
                st.rerun()

            if st.session_state.crawl_in_progress:
                if st.button("⏹️ 停止采集", type="secondary", use_container_width=True):
                    task_id = st.session_state.get('crawl_task_id')
                    if task_id:
                        task_manager.cancel_task(task_id)
                    st.session_state.crawl_in_progress = False
                    st.info("⏹️ 采集已停止")
                    st.rerun()

        with col_status:
            # 清空结果按钮
            if st.session_state.crawl_completed:
                if st.button("🔄 重置", use_container_width=True):
                    st.session_state.crawl_in_progress = False
                    st.session_state.crawl_completed = False
                    st.session_state.crawl_task_id = None
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

    # --- 进度与结果区 ---
    task_id = st.session_state.get('crawl_task_id')

    if st.session_state.crawl_in_progress and task_id:
        with st.container():
            st.markdown("---")
            st.markdown("**📈 采集进度**")

            # 先查一次任务状态
            task_status = task_manager.get_task_status(task_id)

            if task_status is None:
                # 任务不存在（可能是进程重启后丢失）
                logger.warning(f"任务 {task_id[:8]}... 已丢失（可能因进程重启），自动重置采集状态")
                st.session_state.crawl_in_progress = False
                st.session_state.crawl_completed = False
                st.session_state.crawl_task_id = None
                st.warning("⚠️ 之前的采集任务因服务重启已丢失，请重新开始采集")
                st.rerun()

            else:
                status = task_status.get('status', 'unknown')

                if status == 'completed':
                    completed = task_status.get('completed', 0)
                    st.success(f"✅ 采集完成！成功采集 **{completed}** 条新数据")
                    st.session_state.crawl_in_progress = False
                    st.session_state.crawl_completed = True
                    st.rerun()

                elif status == 'failed':
                    error_msg = task_status.get('message', '未知错误')
                    st.error(f"❌ 采集失败: {error_msg}")
                    st.session_state.crawl_in_progress = False
                    st.rerun()

                elif status == 'running':
                    st.info("⏳ 采集任务正在后台执行中...")
                    st.caption("任务将在后台自动完成，完成后刷新页面即可查看结果")
                    progress = task_status.get('progress', 0)
                    if progress > 0:
                        st.progress(min(progress / 100.0, 0.9))

                else:
                    st.info(f"⏳ 任务状态: {status}，请稍候...")

            # 手动刷新按钮
            if st.button("🔄 刷新状态", use_container_width=True):
                st.rerun()

    elif st.session_state.crawl_completed and task_id:
        # 显示最终结果
        task_status = task_manager.get_task_status(task_id)
        if task_status and task_status.get('status') == 'completed':
            completed = task_status.get('completed', 0)
            st.success(f"✅ 采集完成！成功采集 **{completed}** 条新数据")
            if st.button("📊 查看数据", use_container_width=True):
                st.session_state.active_tab = "papers"
                st.rerun()

    # --- 数据源说明 ---
    with st.expander("📖 数据源说明"):
        st.markdown("""
        ### 已确认接入的数据源（14个）

        **API 数据源**
        - **arXiv** - 计算机科学、物理学等预印本，通过 arxiv Python 库接入
        - **OpenAlex** - 开放学术图谱，REST API，涵盖全学科
        - **PubMed** - 生物医学文献，NCBI E-utilities API

        **RSS 数据源**
        - **Science Daily** - 科技新闻门户，RSS 订阅
        - **MIT Technology Review** - MIT 科技评论，RSS 订阅
        - **TechCrunch** - 科技媒体，RSS 订阅
        - **国际期刊 RSS 订阅** - 综合 RSS 订阅源

        **网页爬虫**
        - **Nature** - 《自然》期刊网站
        - **中国科普博览** - 科普综合网站
        - **中国数字科技馆** - 数字科技展示平台
        - **国家科技传播中心** - 科技传播平台
        - **中关村论坛** - 科技创新论坛
        - **科技导报** - 中国科技期刊
        - **中国科学技术馆** - 科技馆官网

        **中文学术期刊**
        - 综合中文学术期刊采集（含预设数据）

        > 注：仅包含文档中明确指定的数据源，未纳入"未定"数据源
        """)

def render_textbook_page():
    st.subheader("📚 教材匹配（预留功能）")
    
    st.info("📖 教材标签库建设中，敬请期待！")
    
    st.markdown("""
    ### 功能规划
    
    **第一阶段：粗匹配（已预留接口）**
    - 基于学科关联标签与教材单元进行第一轮粗匹配
    - 自动关联相关学科的教材内容
    
    **第二阶段：精匹配**
    - 基于关键词和知识点进行精准匹配
    - 支持教材版本选择
    
    **第三阶段：教学应用**
    - 生成教学参考资料
    - 跨学科融合教学设计
    """)
    
    st.markdown("---")
    
    st.subheader("🔍 快速学科匹配测试")
    
    test_subjects = st.multiselect(
        "选择学科标签测试匹配",
        ["信息技术", "计算机科学", "智能科学", "生物学", "医学", "生物技术",
         "物理学", "天文学", "应用物理", "化学", "材料科学", "化工",
         "能源科学", "环境科学", "可持续发展", "工程技术", "电子信息", "机械工程"],
        default=["信息技术", "计算机科学"]
    )
    
    if st.button("测试匹配"):
        matches = TextbookMatcher.quick_match(test_subjects)
        st.success(f"匹配到 {len(matches)} 个相关学科: {', '.join(matches)}")

def export_csv(papers: list):
    df = pd.DataFrame(papers)
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    
    st.download_button(
        label="下载 CSV 文件",
        data=csv,
        file_name=f"papers_{date.today()}.csv",
        mime="text/csv"
    )

def export_excel(papers: list):
    df = pd.DataFrame(papers)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Papers')
    
    output.seek(0)
    
    st.download_button(
        label="下载 Excel 文件",
        data=output.getvalue(),
        file_name=f"papers_{date.today()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def main():
    current_user = st.session_state.get('current_user')
    
    if not current_user:
        auto_token = st.session_state.get('auto_login_token_input', '')
        
        if auto_token:
            payload = auth_manager.verify_token(auto_token)
            if payload:
                user = auth_manager.get_user_by_id(payload['user_id'])
                if user:
                    st.session_state.auth_token = auto_token
                    st.session_state.current_user = {
                        'id': user.id,
                        'username': user.username,
                        'full_name': user.full_name,
                        'email': user.email
                    }
                    st.success(f"✅ 自动登录成功！欢迎, {user.full_name or user.username}")
                    st.rerun()
                    return
            else:
                st.session_state.auto_login_token_input = ''
                st.components.v1.html("""
                <script>
                try {
                    window.parent.localStorage.removeItem('auth_token');
                    console.log('Invalid token cleared from localStorage');
                } catch(e) {
                    console.error('Clear token error:', e);
                }
                </script>
                """, height=0)
        
        render_login()
        
        st.markdown("""
        <style>
        [data-testid="stTextInput"]:has(input[placeholder="__auto_login_token__"]) {
            position: fixed !important;
            left: -9999px !important;
            top: -9999px !important;
            opacity: 0 !important;
            pointer-events: auto !important;
            z-index: -1 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.text_input(
            "auto_token", 
            key="auto_login_token_input", 
            label_visibility="collapsed",
            placeholder="__auto_login_token__"
        )
        
        st.components.v1.html("""
        <script>
        setTimeout(function() {
            try {
                const token = window.parent.localStorage.getItem('auth_token');
                if (token) {
                    const input = window.parent.document.querySelector('input[placeholder="__auto_login_token__"]');
                    if (input && input.value !== token) {
                        input.focus();
                        input.select();
                        
                        try {
                            window.parent.document.execCommand('delete');
                            window.parent.document.execCommand('insertText', false, token);
                        } catch(e) {
                            const nativeSetter = Object.getOwnPropertyDescriptor(
                                window.parent.HTMLInputElement.prototype, 'value'
                            ).set;
                            nativeSetter.call(input, token);
                            input.dispatchEvent(new window.parent.Event('input', { bubbles: true }));
                        }
                        
                        input.dispatchEvent(new window.parent.Event('change', { bubbles: true }));
                        
                        console.log('Auto login token set');
                    }
                }
            } catch(e) {
                console.error('Auto login error:', e);
            }
        }, 1000);
        </script>
        """, height=0)
        return
    
    render_sidebar()
    
    if st.session_state.get('remember_login'):
        token = st.session_state.get('auth_token', '')
        if token:
            st.components.v1.html(f"""
            <script>
            window.parent.localStorage.setItem('auth_token', '{token}');
            </script>
            """, height=0)
        st.session_state.remember_login = False
    
    tab_buttons = st.columns(5)
    active_tab = st.session_state.get('active_tab', 'dashboard')

    tab_configs = [
        ('dashboard', '📊 仪表盘'),
        ('papers', '📚 数据浏览'),
        ('crawl', '📡 数据采集'),
        ('review', '📋 审核文献'),
        ('textbook', '📚 教材匹配'),
    ]
    
    for i, (tab_key, tab_label) in enumerate(tab_configs):
        button_type = "primary" if active_tab == tab_key else "secondary"
        if tab_buttons[i].button(tab_label, key=f"tab_{tab_key}", type=button_type, use_container_width=True):
            st.session_state.active_tab = tab_key
            st.rerun()
    
    st.markdown("---")
    
    if active_tab == 'dashboard':
        render_dashboard()
    elif active_tab == 'papers':
        render_papers()
    elif active_tab == 'crawl':
        render_crawl_page()
    elif active_tab == 'review':
        render_review_page()
    elif active_tab == 'textbook':
        render_textbook_page()

if __name__ == "__main__":
    main()
