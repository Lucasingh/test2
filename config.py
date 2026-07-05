"""
配置文件管理模块
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any
import yaml

# 项目根目录
BASE_DIR = Path(__file__).parent

# 配置文件路径
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "settings.yaml"

# 创建必要目录
for dir_path in [CONFIG_DIR, BASE_DIR / "data", BASE_DIR / "logs"]:
    dir_path.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR / "logs" / "app.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "database": {
        "host": "localhost",
        "user": "root",
        "password": "111111",
        "database": "signals",
        "port": 3306,
        "charset": "utf8mb4"
    },
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "enabled": False
    },
    "themes": {
        "AI": {
            "name": "未来信息与人工智能",
            "core_keywords": ["大语言模型", "多模态AI", "AI Agent", "可解释人工智能", "超大规模智算集群", "具身智能", "人形机器人", "脑机接口", "量子科技", "量子计算", "量子通信", "量子精密测量", "高端芯片", "卫星互联网", "6G通信"],
            "extended_keywords": ["AIGC", "生成式人工智能", "边缘计算", "类脑芯片", "自动驾驶感知系统", "联邦学习", "光计算", "通用人工智能", "量子传感", "量子AI", "AI+科学发现", "数字孪生"],
            "subject_tags": ["信息技术", "计算机科学", "智能科学"],
            "priority": 1
        },
        "LifeScience": {
            "name": "生命科学与健康",
            "core_keywords": ["高端医疗器械", "手术机器人", "合成生物学", "基因治疗", "脑机接口", "新型电极与专用芯片", "精准医疗", "创新药", "基因编辑", "mRNA技术", "干细胞", "免疫治疗", "CAR-T"],
            "extended_keywords": ["微生物组", "类器官", "阿尔茨海默病新靶点", "癌症早筛", "通用疫苗", "表观遗传学", "光遗传学", "蛋白质结构预测", "脑科学", "AI驱动蛋白质设计", "AI神经调控", "闭环深部脑刺激", "神经康复BCI", "认知训练BCI", "量子生物传感"],
            "subject_tags": ["生物学", "医学", "生物技术"],
            "priority": 2
        },
        "Energy": {
            "name": "能源与环境",
            "core_keywords": ["钙钛矿太阳能电池", "氢能", "智能电网", "新型储能", "液流电池", "压缩空气储能", "可控核聚变", "固态电池", "碳捕集利用与封存", "CCUS"],
            "extended_keywords": ["直接空气碳捕获", "DAC", "海洋碳汇", "微塑料治理", "气候数字孪生", "生物燃料", "氢冶金", "量子重力仪", "量子磁力仪", "可再生能源技术"],
            "subject_tags": ["能源科学", "环境科学", "可持续发展"],
            "priority": 3
        },
        "Materials": {
            "name": "材料与未来制造",
            "core_keywords": ["高端特殊钢", "高温合金", "超纯金属", "先进陶瓷", "高性能复合材料", "超导材料", "超材料", "工业机器人", "人形机器人", "增材制造", "3D打印", "4D打印", "可重复使用运载火箭", "太空安全防御"],
            "extended_keywords": ["自修复材料", "液态金属", "数字孪生工厂", "太空3D打印", "软体机器人材料", "可穿戴传感器", "二维材料", "智能仿生材料", "柔性电子材料", "纳米制造", "生物制造", "生物塑料", "量子硬件工程"],
            "subject_tags": ["材料科学", "制造工程", "航天工程"],
            "priority": 4
        },
        "EarthSpace": {
            "name": "地球、海洋与空间",
            "core_keywords": ["北斗系统", "大载重固定翼无人机", "卫星互联网", "海洋装备", "奋斗者号", "深海一号", "深空探测", "空间站科学实验", "海底原位观测", "大洋钻探", "地球系统模式"],
            "extended_keywords": ["太空资源利用", "极地冰芯研究", "全球变化遥感", "海洋碳汇", "空间引力波探测", "深海基因", "行星科学", "空间地球观测", "AI卫星图像分析", "量子地球观测", "卫星遥感", "激光雷达", "多光谱卫星仪器"],
            "subject_tags": ["地球科学", "海洋科学", "空间科学"],
            "priority": 5
        },
        "Engineering": {
            "name": "未来工程与社会系统",
            "core_keywords": ["智慧城市", "数字孪生城市", "灾害预警系统", "工程韧性", "自动驾驶交通系统"],
            "extended_keywords": ["新型建筑工业化", "城市生命线监测", "AI伦理治理", "无人配送网络", "疫情防控多智能体模拟", "碳市场机制", "科技伦理", "人机协同社会", "神经技术伦理治理", "前瞻性技术评估", "地平线扫描", "融合空间设计"],
            "subject_tags": ["工程技术", "城市科学", "社会治理"],
            "priority": 6
        }
    },
    "crawler": {
        "max_workers": 4,
        "timeout": 30,
        "retry_times": 3,
        "retry_backoff": 1
    },
    "sources": {
        "arxiv": {
            "enabled": True,
            "categories": ["cs.AI", "cs.LG", "cs.CV", "cs.CL", "cs.NE"],
            "max_results": 30
        },
        "openalex": {
            "enabled": True,
            "max_results": 40
        },
        "pubmed": {
            "enabled": True,
            "max_results": 25
        },
        "sciencedaily": {
            "enabled": True,
            "max_results": 20
        },
        "chinese": {
            "enabled": True,
            "max_results": 20
        },
        "rss": {
            "enabled": True,
            "max_per_feed": 10
        },
        "kepuchina": {"enabled": True, "max_results": 10},
        "cdstm": {"enabled": True, "max_results": 10},
        "cccst": {"enabled": True, "max_results": 10},
        "zgcforum": {"enabled": True, "max_results": 10},
        "kjdb": {"enabled": True, "max_results": 10},
        "cstm": {"enabled": True, "max_results": 10},
        "nature": {"enabled": True, "max_results": 10},
        "mittr": {"enabled": True, "max_per_feed": 10},
        "techcrunch": {"enabled": True, "max_per_feed": 10}
    },
    "rss_feeds": {
        "Science Daily": "https://www.sciencedaily.com/rss/top.xml",
        "MIT Technology Review": "https://www.technologyreview.com/feed/",
        "Nature": "https://www.nature.com/nature.rss",
        "Science": "https://www.science.org/rss/news-current.xml",
        "TechCrunch": "https://techcrunch.com/feed/"
    },
    "ui": {
        "page_title": "🚀 跨学科前沿成果数据可视化面板",
        "page_icon": "📊",
        "layout": "wide"
    }
}

def load_config() -> Dict[str, Any]:
    """加载配置文件，不存在则创建默认配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                # 合并默认配置
                return merge_configs(DEFAULT_CONFIG, config)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        print(f"保存配置文件失败: {e}")

def merge_configs(default: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
    """合并配置，保持默认配置的结构完整性"""
    result = default.copy()
    for key, value in custom.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result

# 全局配置实例
CONFIG = load_config()
