"""LangGraph 多智能体金融分析图。

流程（asyncio.gather 实现真并行）:
  data_collect
      └──→ parallel_analysts  (market + fundamentals + news 同时跑)
              └──→ [full mode] parallel_debate (bull + bear 同时跑)
                      └──→ risk_judge
                              └──→ verdict (最终买卖建议)

LLM 调用复用 AstrBot 内置 Provider (context.llm_generate)，无需单独配置 API Key。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("astrbot")


@dataclass
class AgentState:
    """流经图的状态容器。"""
    # 输入
    ticker: str = ""
    stock_name: str = ""
    market_info: dict = field(default_factory=dict)
    quick_mode: bool = False

    # 数据层（data_collect 填充）
    kline_data: str = ""
    quote_data: str = ""
    fund_flow_data: str = ""
    financials_data: str = ""
    macro_data: str = ""

    # 分析师层（parallel_analysts 填充）
    market_analysis: str = ""
    fundamentals_analysis: str = ""
    news_analysis: str = ""

    # 辩论层（parallel_debate 填充，quick_mode 时跳过）
    bull_report: str = ""
    bear_report: str = ""

    # 风险评估
    risk_assessment: str = ""

    # 最终输出
    verdict: str = ""
    error: str = ""


# ============================================================
# LLM 调用封装 —— 复用 AstrBot 内置 Provider
# ============================================================

async def _llm_ask(context, umo: str, prompt: str, system_prompt: str = "") -> str:
    """通过 AstrBot context.llm_generate() 调用内置 LLM。

    Args:
        context: AstrBot Context 对象
        umo: unified_msg_origin（用于获取用户偏好的模型）
        prompt: 用户提示词
        system_prompt: 系统提示词（角色定义）
    Returns:
        LLM 响应文本
    """
    try:
        prov = context.get_using_provider(umo)
        if not prov:
            providers = context.get_all_providers()
            if not providers:
                return "❌ 未找到可用的 LLM 提供商，请在 AstrBot WebUI 中配置模型。"
            prov = providers[0]

        resp = await context.llm_generate(
            chat_provider_id=prov.meta().id,
            prompt=prompt,
            system_prompt=system_prompt if system_prompt else None,
        )
        return resp.result_message or ""
    except Exception as e:
        logger.error(f"[TradingGraph] LLM 调用失败: {e}")
        return f"❌ LLM 调用失败: {e}"


# ============================================================
# 数据收集节点 —— 并发调用国信 API 所有工具
# ============================================================

async def node_data_collect(state: AgentState, context, umo: str) -> AgentState:
    """并发获取所有国信 API 数据，填入 state。"""
    from .data_sources.market_data import (
        query_single_quote, query_historical_kline, query_fund_flow, get_set_code
    )
    from .data_sources.financial_data import (
        query_a_stock_balance_sheet, query_a_stock_income_statement,
        query_a_stock_cash_flow, query_hk_stock_balance_sheet,
        query_hk_stock_income_statement, query_hk_stock_cash_flow,
    )
    from .data_sources.macro_data import query_macro_data
    import json

    ticker = state.ticker
    market_info = state.market_info
    market = market_info.get("market_name", "CN")

    # 清理代码
    clean = ticker
    for s in ('.HK', '.SH', '.SZ', '.BJ'):
        clean = clean.replace(s, '')

    is_hk = market_info.get('is_hk', False)
    is_us = not market_info.get('is_china', True) and not is_hk
    set_code = get_set_code(ticker, "HK" if is_hk else ("US" if is_us else "CN"))
    target = 3 if (is_hk or is_us) else 0
    mkt = "SH" if ticker.startswith(('6', '9', '5')) else "SZ"

    async def _run(func, *args):
        try:
            return await asyncio.to_thread(func, *args)
        except Exception as e:
            return {"error": str(e)}

    # 并发拉取所有数据
    kline, quote, flow, bs, inc, cf, macro = await asyncio.gather(
        _run(query_historical_kline, clean, set_code, 60, target, "5,10,20,60"),
        _run(query_single_quote, clean, set_code, target),
        _run(query_fund_flow, clean, set_code, 30),
        _run(query_hk_stock_balance_sheet, clean) if is_hk
            else _run(query_a_stock_balance_sheet, clean, mkt),
        _run(query_hk_stock_income_statement, clean) if is_hk
            else _run(query_a_stock_income_statement, clean, mkt),
        _run(query_hk_stock_cash_flow, clean) if is_hk
            else _run(query_a_stock_cash_flow, clean, mkt),
        _run(query_macro_data, "中国最新PMI CPI LPR 货币政策"),
        return_exceptions=True,
    )

    def _fmt(r):
        if isinstance(r, Exception):
            return f"获取失败: {r}"
        if isinstance(r, dict) and "content" in r:
            return r["content"] or r.get("error", "")
        return json.dumps(r, ensure_ascii=False)[:2000]

    state.kline_data = _fmt(kline)
    state.quote_data = _fmt(quote)
    state.fund_flow_data = _fmt(flow)
    state.financials_data = (
        f"资产负债表:\n{_fmt(bs)}\n\n利润表:\n{_fmt(inc)}\n\n现金流量表:\n{_fmt(cf)}"
    )
    state.macro_data = _fmt(macro)
    return state


# ============================================================
# 分析师节点 —— 并行执行（asyncio.gather 在 parallel_analysts 中调用）
# ============================================================

def _market_hints(market_info: dict) -> str:
    """根据市场返回技术面/基本面/宏观面的分析要点。"""
    name = market_info.get("market_name", "")
    is_hk = market_info.get("is_hk", False)
    is_us = not market_info.get("is_china", True) and not is_hk

    if is_hk:
        return (
            "港股特有要点：关注南向资金流向、港元联系汇率影响、港股通持仓变化、"
            "与A股折溢价水平、做空比率。"
        )
    if is_us:
        return (
            "美股特有要点：关注美联储政策预期、美元指数、VIX恐慌指数、"
            "科技/非农数据、机构持仓变化、财报季影响。"
        )
    return (
        "A股特有要点：关注北向资金（沪深股通）流向、两融余额、"
        "涨跌停板限制、政策面驱动、板块轮动节奏。"
    )


async def node_market_analyst(state: AgentState, context, umo: str) -> str:
    """技术面分析师：分析K线、均线、资金流向。"""
    hints = _market_hints(state.market_info)
    prompt = (
        f"股票: {state.stock_name}（{state.ticker}），{state.market_info.get('market_name','')}\n\n"
        f"K线数据:\n{state.kline_data[:1500]}\n\n"
        f"实时行情:\n{state.quote_data[:500]}\n\n"
        f"资金流向:\n{state.fund_flow_data[:800]}\n\n"
        f"{hints}\n\n"
        "从技术面给出3-5条关键结论，每条一行格式：• [结论]。"
        "涵盖：趋势方向、均线信号、支撑压力、MACD/KDJ/RSI信号。每条20字以内。"
    )
    return await _llm_ask(
        context, umo, prompt,
        system_prompt="你是专业股票技术分析师，只输出结论要点，不写报告标题和段落。"
    )


async def node_fundamentals_analyst(state: AgentState, context, umo: str) -> str:
    """基本面分析师：分析财报数据。"""
    hints = _market_hints(state.market_info)
    prompt = (
        f"股票: {state.stock_name}（{state.ticker}），{state.market_info.get('market_name','')}\n\n"
        f"财务报表:\n{state.financials_data[:2000]}\n\n"
        f"估值快照:\n{state.quote_data[:500]}\n\n"
        f"{hints}\n\n"
        "从基本面给出3-5条关键结论，每条一行格式：• [结论]。"
        "涵盖：PE/PB估值分位、ROE/毛利率/净利率、营收利润增速、资产负债质量。每条20字以内。"
    )
    return await _llm_ask(
        context, umo, prompt,
        system_prompt="你是专业基本面分析师，只输出结论要点，不写报告标题和段落。"
    )


async def node_news_analyst(state: AgentState, context, umo: str) -> str:
    """宏观/情绪分析师：分析宏观经济和资金情绪。"""
    hints = _market_hints(state.market_info)
    prompt = (
        f"股票: {state.stock_name}（{state.ticker}），{state.market_info.get('market_name','')}\n\n"
        f"宏观经济数据:\n{state.macro_data[:1500]}\n\n"
        f"资金流向:\n{state.fund_flow_data[:800]}\n\n"
        f"{hints}\n\n"
        "从宏观/情绪面给出3-5条关键结论，每条一行格式：• [结论]。"
        "涵盖：宏观环境、行业政策、市场情绪、主力资金方向。每条20字以内。"
    )
    return await _llm_ask(
        context, umo, prompt,
        system_prompt="你是专业宏观分析师，只输出结论要点，不写报告标题和段落。"
    )


# ============================================================
# 并行分析师编排节点
# ============================================================

async def node_parallel_analysts(state: AgentState, context, umo: str) -> AgentState:
    """同时运行三个分析师，填充 state。"""
    results = await asyncio.gather(
        node_market_analyst(state, context, umo),
        node_fundamentals_analyst(state, context, umo),
        node_news_analyst(state, context, umo),
        return_exceptions=True,
    )
    state.market_analysis = (
        results[0] if not isinstance(results[0], Exception)
        else f"技术面分析失败: {results[0]}"
    )
    state.fundamentals_analysis = (
        results[1] if not isinstance(results[1], Exception)
        else f"基本面分析失败: {results[1]}"
    )
    state.news_analysis = (
        results[2] if not isinstance(results[2], Exception)
        else f"宏观分析失败: {results[2]}"
    )
    return state


# ============================================================
# 多空辩论节点（quick_mode 时跳过）
# ============================================================

async def node_bull_researcher(state: AgentState, context, umo: str) -> str:
    prompt = (
        f"股票: {state.stock_name}（{state.ticker}）\n\n"
        f"技术面:\n{state.market_analysis}\n\n"
        f"基本面:\n{state.fundamentals_analysis}\n\n"
        f"宏观面:\n{state.news_analysis}\n\n"
        "列出最核心的3个利好因素，每条一行，格式：• [利好]，每条20字以内。"
    )
    return await _llm_ask(context, umo, prompt,
        system_prompt="你是多方研究员，只找利好，简洁直接，不超过3条。")


async def node_bear_researcher(state: AgentState, context, umo: str) -> str:
    prompt = (
        f"股票: {state.stock_name}（{state.ticker}）\n\n"
        f"技术面:\n{state.market_analysis}\n\n"
        f"基本面:\n{state.fundamentals_analysis}\n\n"
        f"宏观面:\n{state.news_analysis}\n\n"
        "列出最核心的3个利空/风险，每条一行，格式：• [风险]，每条20字以内。"
    )
    return await _llm_ask(context, umo, prompt,
        system_prompt="你是空方研究员，只找风险，简洁直接，不超过3条。")


async def node_parallel_debate(state: AgentState, context, umo: str) -> AgentState:
    """同时运行多方和空方研究员。"""
    results = await asyncio.gather(
        node_bull_researcher(state, context, umo),
        node_bear_researcher(state, context, umo),
        return_exceptions=True,
    )
    state.bull_report = results[0] if not isinstance(results[0], Exception) else ""
    state.bear_report = results[1] if not isinstance(results[1], Exception) else ""
    return state


# ============================================================
# 风险评估节点
# ============================================================

async def node_risk_judge(state: AgentState, context, umo: str) -> AgentState:
    """综合所有分析，输出风险等级和最终建议。"""
    debate_section = ""
    if state.bull_report or state.bear_report:
        debate_section = (
            f"\n利好因素:\n{state.bull_report}\n\n"
            f"利空因素:\n{state.bear_report}\n"
        )

    prompt = (
        f"股票: {state.stock_name}（{state.ticker}）\n\n"
        f"技术面:\n{state.market_analysis}\n\n"
        f"基本面:\n{state.fundamentals_analysis}\n\n"
        f"宏观面:\n{state.news_analysis}\n"
        f"{debate_section}\n"
        "综合以上分析，给出：\n"
        "1. 投资建议（买入/持有/卖出，三选一）\n"
        "2. 核心理由（3条，每条一行，格式：• [理由]，20字以内）\n"
        "3. 主要风险（1条，格式：• [风险]，20字以内）\n"
        "不要其他内容，直接按格式输出。"
    )
    state.verdict = await _llm_ask(
        context, umo, prompt,
        system_prompt="你是资深风险评估专家，直接给出结论，不写前言和标题。"
    )
    return state


# ============================================================
# 主图编排类
# ============================================================

class TradingGraph:
    """LangGraph 金融分析图。

    用法:
        graph = TradingGraph(context, umo)
        result = await graph.analyze("600519", quick_mode=False)
        print(result)  # 买卖建议纯文本
    """

    def __init__(self, context, umo: str,
                 progress_callback=None):
        """
        Args:
            context: AstrBot Context 对象（用于 llm_generate）
            umo: unified_msg_origin（用于获取用户偏好模型）
            progress_callback: async (msg: str) -> None，进度推送回调（可选）
        """
        self.context = context
        self.umo = umo
        self._progress = progress_callback

    async def _notify(self, msg: str):
        if self._progress:
            try:
                await self._progress(msg)
            except Exception:
                pass

    async def analyze(self, ticker: str, quick_mode: bool = False) -> str:
        """执行完整分析流程，返回买卖建议文本。"""
        from .utils.stock_utils import StockUtils

        market_info = StockUtils.get_market_info(ticker)
        stock_name = StockUtils.get_stock_name(ticker)

        state = AgentState(
            ticker=ticker,
            stock_name=stock_name,
            market_info=market_info,
            quick_mode=quick_mode,
        )

        # Step 1: 数据收集
        await self._notify("稍等，帮你去拉数据(・ω・)...")
        state = await node_data_collect(state, self.context, self.umo)

        # Step 2: 三位分析师并行
        await self._notify("数据到手了，三位分析师同时看一下～")
        state = await node_parallel_analysts(state, self.context, self.umo)

        # Step 3: 多空辩论（完整模式）
        if not quick_mode:
            await self._notify("多空辩论开始了...")
            state = await node_parallel_debate(state, self.context, self.umo)

        # Step 4: 风险评估 + 最终建议
        await self._notify("综合一下，马上出结论(°ω°)")
        state = await node_risk_judge(state, self.context, self.umo)

        # 格式化最终输出
        return self._format_output(state)

    def _format_output(self, state: AgentState) -> str:
        market = state.market_info.get('market_name', '')
        verdict_text = state.verdict or "无法生成建议"

        # 从 verdict 中提取建议关键词并加 emoji
        if "买入" in verdict_text:
            tag = "🔴 买入"
        elif "卖出" in verdict_text:
            tag = "🟢 卖出"
        else:
            tag = "🟡 持有"

        return (
            f"📊 {state.stock_name}（{state.ticker}）{market}\n\n"
            f"建议：{tag}\n\n"
            f"{verdict_text}\n\n"
            f"⚠️ AI分析，仅供参考，不构成投资建议。"
        )
