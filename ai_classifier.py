"""
DeepSeek AI 自动分类模块
采集入库后自动调用 DeepSeek 对未审核文献打标签
"""
import json
import logging
import os
import requests
from typing import Dict, List

from config import CONFIG

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
THEME_CONFIG = CONFIG['themes']


def _build_system_prompt() -> str:
    """构建系统提示词"""
    lines = []
    for bucket_id, cfg in THEME_CONFIG.items():
        core = "、".join(cfg.get('core_keywords', []))
        extended = "、".join(cfg.get('extended_keywords', []))
        subjects = "、".join(cfg.get('subject_tags', []))
        lines.append(
            f"- {bucket_id}（{cfg['name']}）：核心=[{core}]，扩展=[{extended}]，学科=[{subjects}]"
        )
    return f"""你是学术文献分类专家。根据以下主题体系对文献分类。

=== 主题体系 ===
{chr(10).join(lines)}

=== 规则 ===
1. 每篇文献归属于一个主题，选最匹配的
2. 从该主题标签库中，选文献涉及的核心标签（0-3个）和扩展标签（0-3个）
3. confidence 为 0-1，表示确信程度
4. 不属于任何主题时 theme="Other", confidence=0
5. 只输出 JSON，不要任何解释

=== 输出格式 ===
[{{"title":"原标题","theme":"AI","core_keywords":["多模态AI"],"extended_keywords":["AIGC"],"subject_tags":["计算机科学"],"confidence":0.9}}]"""


def classify_papers(papers: List[Dict]) -> List[Dict]:
    """调用 DeepSeek API 批量分类，返回分类结果列表"""
    texts = []
    for i, p in enumerate(papers):
        abstract = (p.get('abstract') or '')[:500]
        texts.append(f"[{i+1}] {p['title']}\n摘要：{abstract}")

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": f"分类以下 {len(papers)} 篇：\n\n{chr(10).join(texts)}"}
        ],
        "temperature": 0.1,
        "max_tokens": 4096
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content'].strip()

        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.endswith("```"):
            content = content[:-3].strip()

        results = json.loads(content)

        # 后处理校验：只保留该主题配置中实际存在的标签
        results = _validate_results(results)
        return results

    except json.JSONDecodeError as e:
        logger.error(f"DeepSeek 返回解析失败: {e}")
        return []
    except Exception as e:
        logger.error(f"DeepSeek 调用失败: {e}")
        return []


def _validate_results(results: List[Dict]) -> List[Dict]:
    """校验并清洗分类结果，过滤不在配置中的标签"""
    for r in results:
        theme = r.get('theme', 'Other')
        if theme not in THEME_CONFIG:
            r['theme'] = 'Other'
            r['core_keywords'] = []
            r['extended_keywords'] = []
            r['subject_tags'] = []
            continue

        cfg = THEME_CONFIG[theme]
        valid_core = set(cfg.get('core_keywords', []))
        valid_extended = set(cfg.get('extended_keywords', []))
        valid_subjects = set(cfg.get('subject_tags', []))

        r['core_keywords'] = [k for k in r.get('core_keywords', []) if k in valid_core]
        r['extended_keywords'] = [k for k in r.get('extended_keywords', []) if k in valid_extended]
        r['subject_tags'] = [s for s in r.get('subject_tags', []) if s in valid_subjects]

    return results
