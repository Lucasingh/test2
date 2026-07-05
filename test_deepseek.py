"""
DeepSeek AI 自动分类测试脚本
测试 DeepSeek 对未审核文献的分类效果，确认无误后再接入主程序
"""
import json
import logging
import os
import requests
from typing import Dict, List, Any

from config import CONFIG
from database import DatabaseManager, Paper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
THEME_CONFIG = CONFIG['themes']


def build_system_prompt() -> str:
    """构建系统提示词"""
    theme_desc_lines = []
    for bucket_id, cfg in THEME_CONFIG.items():
        core = "、".join(cfg.get('core_keywords', [])[:8])
        extended = "、".join(cfg.get('extended_keywords', [])[:8])
        subjects = "、".join(cfg.get('subject_tags', []))
        theme_desc_lines.append(
            f"- {bucket_id}（{cfg['name']}）：核心标签=[{core}]，扩展标签=[{extended}]，学科标签=[{subjects}]"
        )

    theme_desc = "\n".join(theme_desc_lines)

    return f"""你是学术文献分类专家。请根据以下主题体系对文献进行分类。

=== 主题体系 ===
{theme_desc}

=== 分类规则 ===
1. 每篇文献必须归属于一个主题，选择最匹配的那个
2. 从该主题的标签库中，选出文献内容实际涉及的核心标签（0-3个）和扩展标签（0-3个）
3. 输出 confidence（0-1），表示你对该分类的确信程度
4. 如果文献不属于任何主题，theme 填 "Other"，confidence 填 0

=== 输出格式（严格JSON） ===
[
  {{"title": "文献原标题", "theme": "AI", "core_keywords": ["多模态AI"], "extended_keywords": ["AIGC"], "subject_tags": ["计算机科学"], "confidence": 0.9}},
  ...
]"""


def classify_papers(papers: List[Dict]) -> List[Dict]:
    """
    调用 DeepSeek API 批量分类文献
    papers: [{"id": 1, "title": "...", "abstract": "..."}, ...]
    """
    # 构建用户消息
    papers_text = ""
    for i, p in enumerate(papers):
        abstract = (p.get('abstract') or '')[:500]
        papers_text += f"[{i+1}] 标题：{p['title']}\n摘要：{abstract}\n\n"

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": f"请对以下 {len(papers)} 篇文献分类：\n\n{papers_text}"}
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content']

        # 剥离可能的 markdown 代码块标记
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.endswith("```"):
            content = content[:-3].strip()

        results = json.loads(content)
        logger.info(f"DeepSeek 分类完成: {len(results)} 篇")
        return results

    except json.JSONDecodeError as e:
        logger.error(f"DeepSeek 返回解析失败: {e}\n原始内容: {content}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"DeepSeek API 调用失败: {e}")
        return []
    except Exception as e:
        logger.error(f"DeepSeek 分类异常: {e}")
        return []


def main():
    """主测试逻辑"""
    db = DatabaseManager()

    # 1. 取数据库中所有文献
    with db.get_session() as session:
        papers = session.query(Paper).filter(
            Paper.user_id == 3
        ).order_by(Paper.crawled_date.desc()).all()

    if not papers:
        logger.warning("没有待审核的文献！")
        return

    logger.info(f"共 {len(papers)} 篇待审核文献")

    # 2. 转成 DeepSeek 需要的格式
    paper_list = [
        {
            "id": p.id,
            "title": p.title,
            "abstract": p.abstract or "",
            "source_type": p.source_type
        }
        for p in papers
    ]

    # 3. 调用 DeepSeek 分类
    results = classify_papers(paper_list)

    if not results:
        logger.error("分类失败，检查 API Key 或网络")
        return

    # 4. 展示分类结果（不写入数据库）
    correct = 0
    wrong = 0
    uncertain = 0

    print("\n" + "=" * 80)
    print(f" DeepSeek AI 自动分类结果（共 {len(results)} 篇）")
    print("=" * 80)

    for i, r in enumerate(results):
        title = r.get('title', f'文献{i+1}')[:60]
        theme = r.get('theme', 'Other')
        theme_name = THEME_CONFIG.get(theme, {}).get('name', '其他')
        confidence = r.get('confidence', 0)
        core = r.get('core_keywords', [])
        extended = r.get('extended_keywords', [])

        status = ""
        if confidence >= 0.8:
            status = "🟢 高置信"
        elif confidence >= 0.5:
            status = "🟡 中等"
        else:
            status = "🔴 低置信"

        print(f"\n[{i+1}] {status} | {theme_name} | 置信度={confidence}")
        print(f"    标题: {title}")
        if core:
            print(f"    ★核心: {', '.join(core)}")
        if extended:
            print(f"    ☆扩展: {', '.join(extended)}")

    print("\n" + "=" * 80)
    high = sum(1 for r in results if r.get('confidence', 0) >= 0.8)
    mid = sum(1 for r in results if 0.5 <= r.get('confidence', 0) < 0.8)
    low = sum(1 for r in results if r.get('confidence', 0) < 0.5)
    print(f" 统计: 🟢高置信={high} | 🟡中等={mid} | 🔴低置信={low}")
    print("=" * 80)


if __name__ == "__main__":
    main()
