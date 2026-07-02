"""子智能体 Persona 定义。

每个 .md 文件对应一个 AstrBot SubAgent 的 system prompt。
在 WebUI → SubAgent 编排中创建子智能体时，将对应 .md 的内容粘贴到 Persona 编辑器中。

角色对应关系：
- market_analyst: 市场技术面分析师
- fundamentals_analyst: 基本面分析师
- news_analyst: 新闻与宏观分析师
- bull_researcher: 多方研究员
- bear_researcher: 空方研究员
- research_manager: 研究主管（辩论综合）
- risk_judge: 风险评估官
"""
import os

_PERSONA_DIR = os.path.dirname(__file__)

PERSONAS = {
    "market_analyst": "market_analyst.md",
    "fundamentals_analyst": "fundamentals_analyst.md",
    "news_analyst": "news_analyst.md",
    "bull_researcher": "bull_researcher.md",
    "bear_researcher": "bear_researcher.md",
    "research_manager": "research_manager.md",
    "risk_judge": "risk_judge.md",
}


def load_persona(name: str) -> str:
    """加载指定子智能体的 system prompt。

    Args:
        name: PERSONAS 中的键名，如 "market_analyst"

    Returns:
        对应 .md 文件的完整内容

    Raises:
        ValueError: 未知的 persona 名称
    """
    filename = PERSONAS.get(name)
    if not filename:
        raise ValueError(f"未知 Persona: {name}。可选: {list(PERSONAS.keys())}")
    filepath = os.path.join(_PERSONA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
