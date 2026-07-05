# 🚀 跨学科前沿成果数据可视化面板 V2.0

基于 Streamlit 的数据可视化应用，自动采集全球学术论文与科技新闻，智能分类，可视化分析。

## ✨ 新特性（V2.0）

- 🎯 **模块化架构**：代码分离为 config/database/crawler/processor
- ⚡ **并发采集**：多线程同时采集多个数据源，速度更快
- 🔄 **智能去重**：基于内容哈希自动检测重复数据
- ⭐ **收藏功能**：一键收藏重要论文/新闻
- 📥 **数据导出**：支持导出 CSV 和 Excel 格式
- 📄 **分页浏览**：大量数据友好显示
- 📊 **Plotly 高级图表**：交互式可视化图表
- 🎨 **现代化 UI**：渐变色设计，卡片式布局
- ⚙️ **YAML 配置**：灵活配置采集参数
- 📝 **采集历史**：记录每次采集详情

## 📋 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库

确保 MySQL 服务已启动，然后执行：

```bash
mysql -u root -p < init_database.sql
```

或在 MySQL 客户端中执行：

```sql
SOURCE init_database.sql;
```

### 3. 配置数据库

如果需要修改数据库配置，编辑 `config.py` 中的 DB_CONFIG：

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'signals',
    'port': 3306,
    'charset': 'utf8mb4'
}
```

### 4. 启动应用

```bash
streamlit run app.py
```

### 5. 访问应用

打开浏览器访问: http://localhost:8501

## 📁 项目结构

```
test2/
├── config.py          # 配置管理模块
├── database.py        # 数据库模块 (SQLAlchemy ORM)
├── crawler.py         # 数据采集模块 (支持并发)
├── processor.py       # 数据处理和分类模块
├── app.py            # 主程序 (Streamlit UI)
├── requirements.txt  # Python 依赖
├── init_database.sql # 数据库初始化脚本
├── .streamlit/       # Streamlit 配置
│   └── config.toml
├── README.md         # 使用说明
└── 开发日志.md      # 开发记录
```

## 🌐 数据源

- **arXiv** - 论文预印本（AI/ML/CV/NLP/Neuroscience 等）
- **OpenAlex** - 开放学术图谱
- **PubMed** - 生物医学文献
- **ScienceDaily** - 科技新闻
- **RSS订阅** - Nature/Science/MIT TechReview/等

## 🏷️ 主题分类

- 🤖 人工智能
- 🔬 生命科学
- 🌱 能源环境
- ⚛️ 物理科学
- 🧪 化学材料
- 🔧 工程技术
- 📦 其他

## 💡 使用说明

### 数据采集

1. 在侧边栏点击 **"开始采集"** 按钮
2. 等待采集完成，会显示新增数据量
3. 数据自动去重后保存到数据库

### 数据浏览

1. 切换到 **"📚 数据浏览"** 标签页
2. 使用筛选条件：
   - 关键词搜索
   - 主题分类
   - 数据源
   - 日期范围
   - 只看收藏
3. 点击 ⭐ 按钮收藏文章
4. 点击导出按钮下载数据

### 数据概览

1. 在 **"📊 概览"** 标签页查看统计
2. 查看领域分布、时间趋势、数据源分布

## 🛠️ 技术栈

- **Streamlit** - Web 应用框架
- **SQLAlchemy** - ORM 框架
- **Pandas** - 数据处理
- **Plotly** - 可视化图表
- **PyMySQL** - MySQL 驱动
- **arXiv.py** - arXiv API 客户端
- **Feedparser** - RSS 解析
- **BeautifulSoup4** - HTML 解析
- **PyYAML** - 配置文件

## 📊 数据库设计

### papers 表
- `id` - 主键
- `source_type` - 数据源类型
- `title` - 标题
- `abstract` - 摘要
- `url` - 原文链接
- `published_date` - 发布日期
- `crawled_date` - 采集日期
- `signal_type` - 类型(paper/news)
- `theme_bucket` - 主题分类
- `field` - 学科领域
- `content_hash` - 内容哈希(去重用)
- `is_starred` - 是否收藏
- `read_count` - 阅读次数
- `tags` - 关键词标签

### crawl_history 表
- 记录每次采集的历史详情

## ⚙️ 配置说明

编辑 `config/settings.yaml` (自动生成) 或修改 `config.py` 中的默认配置：

- 数据库连接参数
- 数据源启用状态
- 采集数量限制
- 主题分类关键词

## 🚀 启动指南

### 环境要求

- Python 3.8+
- MySQL 5.7+
- 网络连接（用于采集数据源）

### 常见问题

**Q: 数据库连接失败？**

A: 检查 MySQL 服务是否启动，用户名密码是否正确。

**Q: 采集没有数据？**

A: 检查网络连接，部分源可能需要 API 密钥。

**Q: 如何修改数据源？**

A: 编辑 `config.py` 中的配置。

## 📝 更新日志

### V2.0 (2026-06-01)
- ✨ 全面重构为模块化架构
- ⚡ 支持并发采集
- 🔄 智能去重
- ⭐ 收藏功能
- 📥 CSV/Excel 导出
- 📄 分页浏览
- 📊 Plotly 高级可视化
- 🎨 现代化 UI 设计

### V1.0 (2026-06-01)
- 🎉 初始版本发布

---

享受探索学术前沿的乐趣！🚀
