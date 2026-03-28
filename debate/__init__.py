"""
辩论模块 - 包含多空辩论研究者、研究主管和风险裁判
"""
from .bull_researcher import BullResearcher
from .bear_researcher import BearResearcher
from .research_manager import ResearchManager
from .risk_judge import RiskJudge

__all__ = ['BullResearcher', 'BearResearcher', 'ResearchManager', 'RiskJudge']
