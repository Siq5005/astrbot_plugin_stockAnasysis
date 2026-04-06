"""基于 LangGraph 的多智能体金融分析图。"""

from datetime import datetime
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass, field

from langgraph.graph import END, StateGraph, START

from astrbot.api import logger

from .data_fetcher import DataFetcher
from .analysts.market_analyst import MarketAnalyst
from .analysts.fundamentals_analyst import FundamentalsAnalyst
from .analysts.news_analyst import NewsAnalyst
from .debate.bull_researcher import BullResearcher
from .debate.bear_researcher import BearResearcher
from .debate.research_manager import ResearchManager
from .debate.risk_judge import RiskJudge
from .utils.stock_utils import StockUtils

# 各分析阶段的进度消息
STAGE_MESSAGES: Dict[str, str] = {
    "data_prefetch": "📡 正在获取所有数据源...",
    "market_analyst": "📊 正在进行市场技术面分析...",
    "fundamentals_analyst": "📋 正在进行基本面分析...",
    "news_analyst": "📰 正在进行新闻面分析...",
    "bull_researcher": "🐂 多方研究员正在分析看涨因素...",
    "bear_researcher": "🐻 空方研究员正在分析看跌因素...",
    "research_manager": "⚔️ 研究主管正在汇总多空辩论...",
    "risk_judge": "🛡️ 风险裁判正在评估风险等级...",
    "report_generator": "📝 正在生成最终报告...",
}


@dataclass
class AgentState:
    """
    LangGraph智能体状态
    用于在图节点之间传递信息
    """
    ticker: str = ""
    stock_name: str = ""
    trade_date: str = ""
    market_info: Dict[str, Any] = field(default_factory=dict)
    
    # 预获取的原始数据（在数据预取节点中一次性填充）
    market_data_raw: str = ""
    fundamentals_data_raw: str = ""
    news_data_raw: str = ""
    sentiment_data_raw: str = ""
    
    # 各分析师结果
    market_analysis: str = ""
    fundamentals_analysis: str = ""
    news_analysis: str = ""
    
    # 辩论阶段结果
    bull_research: str = ""
    bear_research: str = ""
    debate_report: str = ""
    
    # 风险评估结果
    risk_assessment: str = ""
    
    # 最终报告
    final_report: str = ""
    
    # 错误信息
    error: str = ""
    
    # 数据预取结果（包含 missing_sources, error_details 等）
    data_fetch_result: Dict[str, Any] = field(default_factory=dict)
    
    # 快速分析模式（跳过多空辩论）
    quick_mode: bool = False
    
    # 迭代计数
    iteration: int = 0


class TradingGraphLangGraph:
    """
    基于LangGraph的金融分析图
    使用多智能体架构进行股票分析
    """
    
    def __init__(self, llm, data_fetcher: DataFetcher = None, progress_callback: Optional[Callable] = None):
        """
        初始化LangGraph交易图
        
        Args:
            llm: LLM实例，需支持async ask(prompt)方法
            data_fetcher: 数据获取器实例
            progress_callback: 进度回调函数，签名为 async def callback(stage: str, detail: str)
        """
        self.llm = llm
        self.data_fetcher = data_fetcher or DataFetcher()
        self.progress_callback = progress_callback
        
        # 初始化分析师
        self.market_analyst = MarketAnalyst(llm, self.data_fetcher)
        self.fundamentals_analyst = FundamentalsAnalyst(llm, self.data_fetcher)
        self.news_analyst = NewsAnalyst(llm, self.data_fetcher)
        
        # 初始化辩论模块
        self.bull_researcher = BullResearcher(llm, self.data_fetcher)
        self.bear_researcher = BearResearcher(llm, self.data_fetcher)
        self.research_manager = ResearchManager(
            llm, self.data_fetcher, 
            self.bull_researcher, self.bear_researcher
        )
        self.risk_judge = RiskJudge(llm, self.data_fetcher)
        
        # 构建图
        self.graph = self._build_graph()
    
    @staticmethod
    def _route_after_prefetch(state: AgentState) -> str:
        """条件路由：数据预取完成后，根据是否成功决定下一步。

        Returns:
            "market_analyst" — 数据预取成功，进入分析流程
            "report_generator" — 数据预取失败，直接生成错误报告
        """
        if state.error:
            return "report_generator"
        return "market_analyst"

    @staticmethod
    def _route_after_analysts(state: AgentState) -> str:
        """条件路由：新闻分析完成后，根据 quick_mode 决定走辩论还是直接风险评估。
        
        Returns:
            "bull_researcher" — 完整模式，进入多空辩论
            "risk_judge" — 快速模式，跳过辩论直接评估风险
        """
        if state.quick_mode:
            return "risk_judge"
        return "bull_researcher"
    
    def _build_graph(self):
        """构建LangGraph状态图，返回 CompiledGraph。"""
        
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("data_prefetch", self._data_prefetch_node)
        workflow.add_node("market_analyst", self._market_analyst_node)
        workflow.add_node("fundamentals_analyst", self._fundamentals_analyst_node)
        workflow.add_node("news_analyst", self._news_analyst_node)
        workflow.add_node("bull_researcher", self._bull_researcher_node)
        workflow.add_node("bear_researcher", self._bear_researcher_node)
        workflow.add_node("research_manager", self._research_manager_node)
        workflow.add_node("risk_judge", self._risk_judge_node)
        workflow.add_node("report_generator", self._report_generator_node)
        
        # 设置入口点：先进行数据预取
        workflow.add_edge(START, "data_prefetch")

        # 数据预取完成后：根据是否成功决定进入分析师还是直接生成错误报告
        workflow.add_conditional_edges(
            "data_prefetch",
            self._route_after_prefetch,
            {
                "market_analyst": "market_analyst",
                "report_generator": "report_generator",
            }
        )
        
        # 分析师链式连接
        workflow.add_edge("market_analyst", "fundamentals_analyst")
        workflow.add_edge("fundamentals_analyst", "news_analyst")
        
        # 新闻分析后：根据 quick_mode 决定是否跳过辩论阶段
        workflow.add_conditional_edges(
            "news_analyst",
            self._route_after_analysts,
            {
                "bull_researcher": "bull_researcher",
                "risk_judge": "risk_judge",
            }
        )
        
        # 多空辩论循环（简单并行后进入研究主管）
        workflow.add_edge("bull_researcher", "bear_researcher")
        workflow.add_edge("bear_researcher", "research_manager")
        
        # 研究主管输出后进入风险裁判
        workflow.add_edge("research_manager", "risk_judge")
        
        # 风险裁判后生成最终报告
        workflow.add_edge("risk_judge", "report_generator")
        
        # 最终报告节点是终点
        workflow.add_edge("report_generator", END)
        
        return workflow.compile()
    
    async def _data_prefetch_node(self, state: AgentState) -> Dict:
        """数据预取节点：一次性并发获取所有数据源"""
        logger.info(f"开始预取数据: {state.ticker}")

        try:
            fetch_result = await self.data_fetcher.fetch_all_data(state.ticker, state.trade_date)

            result = {
                "market_data_raw": fetch_result['market_data'],
                "fundamentals_data_raw": fetch_result['fundamentals_data'],
                "news_data_raw": fetch_result['news_data'],
                "sentiment_data_raw": fetch_result['sentiment_data'],
                "data_fetch_result": fetch_result,
            }

            if not fetch_result['success']:
                missing = fetch_result['missing_sources']
                details = fetch_result['error_details']
                detail_lines = "\n".join(f"  - {src}: {details.get(src, '未知原因')}" for src in missing)
                # 诊断失败原因，生成针对性建议
                diagnostic_hints = []
                all_errors = ' '.join(str(v) for v in details.values())
                if 'RemoteDisconnected' in all_errors or 'Connection aborted' in all_errors:
                    diagnostic_hints.append('• 数据源服务器拒绝了连接，可能是网络或反爬策略导致')
                    diagnostic_hints.append('• 建议安装 curl_cffi: `pip install curl_cffi`（可绕过 TLS 指纹检测）')
                    diagnostic_hints.append('• 如果服务器在海外，可能导致国内数据源访问不稳定')
                if 'Too Many Requests' in all_errors:
                    diagnostic_hints.append('• 数据源请求频率过高，请等待几分钟后再试')
                if not diagnostic_hints:
                    diagnostic_hints.append('• 请检查网络连接或稍后重试')
                    diagnostic_hints.append('• 如果问题持续，请确认股票代码是否正确')

                hints_text = '\n'.join(diagnostic_hints)
                error_msg = (
                    f"❌ 数据源不齐全，无法进行分析。\n\n"
                    f"**缺失的信息源**:\n{detail_lines}\n\n"
                    f"**可能的原因与建议**:\n{hints_text}"
                )
                result["error"] = error_msg
                logger.warning(f"数据预取不完整: {missing}")
            else:
                logger.info(f"数据预取完成，所有必要信息源已就绪")

            return result
        except Exception as e:
            logger.error(f"数据预取失败: {e}")
            return {"error": f"数据预取失败: {str(e)}"}

    async def _market_analyst_node(self, state: AgentState) -> Dict:
        """市场分析师节点"""
        logger.info(f"执行市场分析师: {state.ticker}")

        # 通用错误短路：上游发生致命错误时跳过本节点
        if state.error:
            logger.warning(f"跳过市场分析师：上游错误")
            return {"market_analysis": "⚠️ 因上游数据缺失，跳过市场分析", "iteration": state.iteration + 1}

        try:
            analysis = await self.market_analyst.analyze_with_data(
                state.ticker, state.trade_date, state.market_data_raw
            )
            return {"market_analysis": analysis, "iteration": state.iteration + 1}
        except Exception as e:
            logger.error(f"市场分析师错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return {"market_analysis": f"市场分析失败: {str(e)}", "error": str(e)}
    
    async def _fundamentals_analyst_node(self, state: AgentState) -> Dict:
        """基本面分析师节点"""
        logger.info(f"执行基本面分析师: {state.ticker}")

        # 通用错误短路：上游发生致命错误时跳过本节点
        if state.error:
            logger.warning(f"跳过基本面分析师：上游错误")
            return {"fundamentals_analysis": "⚠️ 因上游数据缺失，跳过基本面分析"}

        try:
            analysis = await self.fundamentals_analyst.analyze_with_data(
                state.ticker, state.trade_date, state.fundamentals_data_raw
            )
            return {"fundamentals_analysis": analysis}
        except Exception as e:
            logger.error(f"基本面分析师错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return {"fundamentals_analysis": f"基本面分析失败: {str(e)}", "error": str(e)}
    
    async def _news_analyst_node(self, state: AgentState) -> Dict:
        """新闻分析师节点"""
        logger.info(f"执行新闻分析师: {state.ticker}")

        # 通用错误短路：上游发生致命错误时跳过本节点
        if state.error:
            logger.warning(f"跳过新闻分析师：上游错误")
            return {"news_analysis": "⚠️ 因上游数据缺失，跳过新闻分析"}

        try:
            analysis = await self.news_analyst.analyze_with_data(
                state.ticker, state.trade_date,
                state.news_data_raw, state.sentiment_data_raw
            )
            return {"news_analysis": analysis}
        except Exception as e:
            logger.error(f"新闻分析师错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return {"news_analysis": f"新闻分析失败: {str(e)}", "error": str(e)}
    
    async def _bull_researcher_node(self, state: AgentState) -> Dict:
        """多方研究员节点"""
        logger.info(f"执行多方研究员: {state.ticker}")

        # 通用错误短路：上游发生致命错误时跳过本节点
        if state.error:
            logger.warning("跳过多方研究员：上游错误")
            return {"bull_research": "⚠️ 因上游数据缺失，跳过多方研究"}

        context = {
            'market_analysis': state.market_analysis,
            'fundamentals_analysis': state.fundamentals_analysis,
            'news_analysis': state.news_analysis
        }
        
        try:
            research = await self.bull_researcher.research(
                state.ticker, state.trade_date, context
            )
            return {"bull_research": research}
        except Exception as e:
            logger.error(f"多方研究员错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return {"bull_research": f"多方研究失败: {type(e).__name__}: {e}", "error": f"{type(e).__name__}: {e}"}
    
    async def _bear_researcher_node(self, state: AgentState) -> Dict:
        """空方研究员节点"""
        logger.info(f"执行空方研究员: {state.ticker}")

        # 通用错误短路：上游发生致命错误时跳过本节点
        if state.error:
            logger.warning("跳过空方研究员：上游错误")
            return {"bear_research": "⚠️ 因上游数据缺失，跳过空方研究"}

        context = {
            'market_analysis': state.market_analysis,
            'fundamentals_analysis': state.fundamentals_analysis,
            'news_analysis': state.news_analysis
        }
        
        try:
            research = await self.bear_researcher.research(
                state.ticker, state.trade_date, context
            )
            return {"bear_research": research}
        except Exception as e:
            logger.error(f"空方研究员错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return {"bear_research": f"空方研究失败: {type(e).__name__}: {e}", "error": f"{type(e).__name__}: {e}"}
    
    async def _research_manager_node(self, state: AgentState) -> Dict:
        """研究主管节点"""
        logger.info(f"执行研究主管: {state.ticker}")
        
        context = {
            'market_analysis': state.market_analysis,
            'fundamentals_analysis': state.fundamentals_analysis,
            'news_analysis': state.news_analysis
        }
        
        try:
            debate_report = await self.research_manager.conduct_debate(
                state.ticker, state.trade_date, context
            )
            return {"debate_report": debate_report}
        except Exception as e:
            logger.error(f"研究主管错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return {"debate_report": f"辩论综合失败: {type(e).__name__}: {e}", "error": f"{type(e).__name__}: {e}"}
    
    async def _risk_judge_node(self, state: AgentState) -> Dict:
        """风险裁判节点"""
        logger.info(f"执行风险裁判: {state.ticker}")

        # 通用错误短路：上游发生致命错误时跳过本节点
        if state.error:
            logger.warning(f"跳过风险裁判：上游错误")
            return {"risk_assessment": "⚠️ 因上游数据缺失，跳过风险评估"}

        context = {
            'market_analysis': state.market_analysis,
            'fundamentals_analysis': state.fundamentals_analysis,
            'news_analysis': state.news_analysis
        }

        # 快速模式下跳过多空辩论，使用占位文本
        debate_report = state.debate_report or "快速分析模式：未进行多空辩论分析，请直接基于三分析师结论进行风险评估。"

        try:
            risk_assessment = await self.risk_judge.assess_risk_with_data(
                state.ticker, state.trade_date, context, debate_report,
                state.market_data_raw
            )
            return {"risk_assessment": risk_assessment}
        except Exception as e:
            logger.error(f"风险裁判错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return {"risk_assessment": f"风险评估失败: {type(e).__name__}: {e}", "error": f"{type(e).__name__}: {e}"}
    
    async def _report_generator_node(self, state: AgentState) -> Dict:
        """最终报告生成节点"""
        logger.info(f"生成最终报告: {state.ticker}")
        
        final_report = self._build_final_report(state)
        
        return {"final_report": final_report}
    
    def _build_final_report(self, state: AgentState) -> str:
        """构建最终综合报告"""

        # 如果上游发生致命错误，直接返回错误信息
        if state.error:
            return state.error

        # 快速分析模式标题
        mode_label = "（快速分析）" if state.quick_mode else ""
        
        # 基础报告头
        report_header = f"""# 📈 {state.stock_name} ({state.ticker}) 分析报告{mode_label}

**分析日期**: {state.trade_date}  
**市场**: {state.market_info.get('market_name', '未知')}  
**货币**: {state.market_info.get('currency_name', '未知')}（{state.market_info.get('currency_symbol', '')}）"""

        # 构建报告各章节
        sections = f"""
---

## 📊 市场技术面分析

{state.market_analysis}

---

## 📋 基本面分析

{state.fundamentals_analysis}

---

## 📰 新闻面分析

{state.news_analysis}"""

        # 快速模式下跳过多空辩论综合章节
        if not state.quick_mode:
            sections += f"""

---

## ⚔️ 多空辩论综合

{state.debate_report}"""

        sections += f"""

---

## ⚠️ 风险评估

{state.risk_assessment}

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
*本报告由AI自动生成，仅供参考，不构成投资建议。*
"""
        
        return report_header + sections
    
    async def analyze(self, ticker: str, trade_date: str = None,
                     progress_callback: Optional[Callable] = None,
                     quick_mode: bool = False) -> str:
        """
        执行股票分析
        
        Args:
            ticker: 股票代码
            trade_date: 交易日期（YYYY-MM-DD），默认为今天
            progress_callback: 进度回调函数（优先于构造时传入的回调）
            quick_mode: 快速分析模式（跳过多空辩论），默认为 False
            
        Returns:
            完整的分析报告
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')
        
        # 选择回调：优先使用 analyze 传入的，其次使用构造时的
        callback = progress_callback or self.progress_callback
        
        # 获取市场信息
        market_info = StockUtils.get_market_info(ticker)
        normalized_ticker = market_info['normalized_ticker']
        stock_name = StockUtils.get_stock_name(ticker)
        
        logger.info(f"开始分析: {stock_name} ({normalized_ticker})")
        
        # 初始化状态
        initial_state = AgentState(
            ticker=normalized_ticker,
            stock_name=stock_name,
            trade_date=trade_date,
            market_info=market_info,
            quick_mode=quick_mode,
        )
        
        # 执行图（流式）
        try:
            final_state = initial_state
            async for chunk in self.graph.astream(initial_state, stream_mode="updates"):
                # chunk 格式: {node_name: {updated_state_fields}}
                for node_name, node_output in chunk.items():
                    logger.info(f"[进度] 节点完成: {node_name} ({stock_name})")
                    
                    # 触发进度回调
                    if callback:
                        if node_name == "data_prefetch":
                            # 检查预取是否成功：只要 error 字段存在即视为失败
                            if node_output.get("error"):
                                stage_msg = "❌ 数据获取失败，无法继续分析"
                            else:
                                stage_msg = "✅ 数据预取完成，所有信息源已就绪"
                        elif node_name == "report_generator":
                            # 区分正常报告生成和错误报告生成
                            if final_state.error or node_output.get("error"):
                                stage_msg = "📋 正在生成错误报告..."
                            else:
                                stage_msg = STAGE_MESSAGES.get(node_name, f"⏳ 正在执行 {node_name}...")
                        else:
                            stage_msg = STAGE_MESSAGES.get(node_name, f"⏳ 正在执行 {node_name}...")
                        try:
                            await callback(node_name, stage_msg)
                        except Exception as cb_err:
                            logger.warning(f"进度回调执行失败: {cb_err}")
                    
                    # 累积状态更新
                    for key, value in node_output.items():
                        if hasattr(final_state, key):
                            setattr(final_state, key, value)
            
            return final_state.final_report or '报告生成失败'
        except Exception as e:
            logger.error(f"分析执行错误: {type(e).__name__}: {repr(e)}", exc_info=True)
            return f"分析执行失败: {type(e).__name__}: {e}"


# 兼容性：保留原有的简化版类
FinancialAssistantGraph = TradingGraphLangGraph
