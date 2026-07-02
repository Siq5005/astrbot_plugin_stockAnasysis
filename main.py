"""AstrBot 金融助手插件入口 —— 国信 API + LangGraph 并行架构。

命令（支持斜杠命令和自然语言）：
- /股票分析 <code>: 完整多智能体分析（含多空辩论）
- /快速分析 <code>: 跳过多空辩论
- /选股 <条件>: 自然语言智能选股
- /查股 <名称>: 股票名称→代码解析
- /帮助: 显示帮助信息

架构：
- 数据：国信证券 API（4 个 skill，纯 stdlib）
- 编排：LangGraph 并行图（三位分析师并行 + 多空并行）
- LLM：复用 AstrBot 内置模型（context.llm_generate），无需单独配置
"""
import asyncio
import json

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import logger, AstrBotConfig
from astrbot.api.star import Context, Star, register

from .utils.stock_utils import StockUtils
from .data_sources.http_client import is_available as guosen_available


@register("astrbot_plugin_stockanalysis", "Coe", "基于国信API + LangGraph 的多智能体金融分析插件", "v2.0.0")
class TradingAssistantPlugin(Star):
    """金融助手插件 —— 国信API + SubAgent 架构"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        logger.info("TradingAssistantPlugin v2.0 初始化中...")
        self.config = config or {}

        if not guosen_available():
            logger.warning(
                "未配置 GS_API_KEY 环境变量，国信 API 工具不可用。"
                "请在环境变量中设置 GS_API_KEY 或联系国信证券获取 API Key。"
            )

        logger.info("TradingAssistantPlugin v2.0 初始化完成（国信API + SubAgent 架构）")

    async def terminate(self):
        """插件卸载时清理资源。"""
        logger.info("TradingAssistantPlugin v2.0 已卸载")

    # ================================================================
    # LLM 工具 —— @filter.llm_tool 注册，AstrBot 框架自动发现
    # ================================================================

    @filter.llm_tool(name="query_single_quote")
    async def tool_query_single_quote(self, event: AstrMessageEvent, code: str, market: str = "CN") -> str:
        """获取单只股票实时行情数据，包括最新价、涨跌幅、成交量、市盈率、总市值等。

        Args:
            code(string): 股票代码，A股6位数字如600519，港股如0700.HK，美股如AAPL
            market(string): 市场类型，CN表示A股，HK表示港股，US表示美股，默认CN
        """
        from .data_sources.market_data import query_single_quote, get_set_code
        clean = code
        for s in ('.HK', '.SH', '.SZ', '.BJ'):
            clean = clean.replace(s, '')
        set_code = get_set_code(code, market)
        target = 3 if market in ("HK", "US") else 0
        result = await asyncio.to_thread(query_single_quote, clean, set_code, target)
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="query_historical_kline")
    async def tool_query_historical_kline(self, event: AstrMessageEvent, code: str, market: str = "CN", days: int = 60) -> str:
        """获取股票历史K线数据，包含开高低收价格、成交量和MA均线，用于技术面分析。

        Args:
            code(string): 股票代码，A股6位数字，港股如0700.HK，美股如AAPL
            market(string): 市场类型，CN表示A股，HK表示港股，US表示美股，默认CN
            days(number): 近几个交易日的数据，默认60
        """
        from .data_sources.market_data import query_historical_kline, get_set_code
        clean = code
        for s in ('.HK', '.SH', '.SZ', '.BJ'):
            clean = clean.replace(s, '')
        set_code = get_set_code(code, market)
        target = 3 if market in ("HK", "US") else 0
        result = await asyncio.to_thread(query_historical_kline, clean, set_code, days, target, "5,10,20,60")
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="query_fund_flow")
    async def tool_query_fund_flow(self, event: AstrMessageEvent, code: str, market: str = "CN", period: int = 30) -> str:
        """获取股票资金流向数据，分析主力、大户、散户的净流入流出情况。

        Args:
            code(string): 股票代码，A股6位数字，港股如0700.HK，美股如AAPL
            market(string): 市场类型，CN表示A股，HK表示港股，US表示美股，默认CN
            period(number): 查询天数，最大60，默认30
        """
        from .data_sources.market_data import query_fund_flow, get_set_code
        clean = code
        for s in ('.HK', '.SH', '.SZ', '.BJ'):
            clean = clean.replace(s, '')
        set_code = get_set_code(code, market)
        result = await asyncio.to_thread(query_fund_flow, clean, set_code, min(period, 60))
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="query_market_ranking")
    async def tool_query_market_ranking(self, event: AstrMessageEvent, set_domain: int = 6, want_num: int = 10, sort_type: int = 1) -> str:
        """查询A股涨跌排名，获取涨幅或跌幅最大的股票列表。

        Args:
            set_domain(number): 查询范围，0为上证A股，2为深证A股，6为沪深全部，14为创业板，14515为北交所，默认6
            want_num(number): 返回股票数量，最大80，默认10
            sort_type(number): 排序方式，1为按涨幅排名，2为按跌幅排名，默认1
        """
        from .data_sources.market_data import query_market_ranking
        result = await asyncio.to_thread(query_market_ranking, set_domain, want_num, sort_type)
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="query_financials")
    async def tool_query_financials(self, event: AstrMessageEvent, code: str, market: str = "CN") -> str:
        """获取股票三大财务报表：资产负债表、利润表、现金流量表，用于基本面分析。

        Args:
            code(string): 股票代码，A股6位数字，港股如0700.HK
            market(string): 市场类型，CN表示A股，HK表示港股，默认CN
        """
        from .data_sources.financial_data import (
            query_a_stock_balance_sheet, query_a_stock_income_statement,
            query_a_stock_cash_flow, query_hk_stock_balance_sheet,
            query_hk_stock_income_statement, query_hk_stock_cash_flow,
        )
        clean = code
        for s in ('.HK', '.SH', '.SZ', '.BJ'):
            clean = clean.replace(s, '')
        if market == "HK":
            bs, inc, cf = await asyncio.gather(
                asyncio.to_thread(query_hk_stock_balance_sheet, clean),
                asyncio.to_thread(query_hk_stock_income_statement, clean),
                asyncio.to_thread(query_hk_stock_cash_flow, clean),
                return_exceptions=True,
            )
        else:
            mkt = "SH" if code.startswith(('6', '9', '5')) else "SZ"
            bs, inc, cf = await asyncio.gather(
                asyncio.to_thread(query_a_stock_balance_sheet, clean, mkt),
                asyncio.to_thread(query_a_stock_income_statement, clean, mkt),
                asyncio.to_thread(query_a_stock_cash_flow, clean, mkt),
                return_exceptions=True,
            )
        return json.dumps({"balance_sheet": bs if not isinstance(bs, Exception) else str(bs),
                           "income_statement": inc if not isinstance(inc, Exception) else str(inc),
                           "cash_flow": cf if not isinstance(cf, Exception) else str(cf)}, ensure_ascii=False)

    @filter.llm_tool(name="query_macro_data")
    async def tool_query_macro_data(self, event: AstrMessageEvent, query: str) -> str:
        """查询全球宏观经济指标，支持GDP、CPI、PMI、LPR、汇率、商品期货等数据。

        Args:
            query(string): 中文自然语言查询条件，如中国最新GDP增速、近三个月COMEX黄金走势
        """
        from .data_sources.macro_data import query_macro_data
        result = await asyncio.to_thread(query_macro_data, query)
        if isinstance(result, dict):
            return result.get("content", "") or result.get("error", "宏观经济数据查询失败")
        return str(result)

    @filter.llm_tool(name="smart_stock_picking")
    async def tool_smart_stock_picking(self, event: AstrMessageEvent, searchstring: str, searchtype: str = "stock") -> str:
        """根据自然语言条件筛选股票，支持财务指标、技术指标、行业板块等多维度组合筛选。

        Args:
            searchstring(string): 中文自然语言筛选条件，如市盈率小于20的银行股、MACD金叉的科技股
            searchtype(string): 资产类型，stock表示A股，fund表示基金，HK_stock表示港股，US_stock表示美股，默认stock
        """
        from .data_sources.stock_picking import smart_stock_picking
        result = await asyncio.to_thread(smart_stock_picking, searchstring, searchtype)
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="analyze_stock")
    async def tool_analyze_stock(self, event: AstrMessageEvent, code: str, quick: bool = False) -> str:
        """对股票进行完整的多智能体分析（含技术面、基本面、宏观面、多空辩论、风险评估），直接返回买卖建议。

        这是最高层级的分析工具——当用户想分析某只股票时优先使用此工具，无需逐个调用底层数据工具。

        Args:
            code(string): 股票代码或名称，如000001、平安银行、AAPL、0700.HK
            quick(boolean): 是否快速模式，false为完整分析含多空辩论，true为快速跳过辩论，默认false
        """
        from .trading_graph import TradingGraph
        from astrbot.api.message_components import Plain
        from astrbot.core.message.message_event_result import MessageChain

        # 名称解析
        ticker = code.strip()
        if not StockUtils.is_valid_stock_code(ticker):
            try:
                resolved = StockUtils.resolve_stock_name(ticker)
                if resolved:
                    ticker = resolved
            except Exception:
                pass

        async def progress(msg: str):
            try:
                await event.send(MessageChain([Plain(msg)]))
            except Exception:
                pass

        try:
            await progress(f"好嘞，帮你查「{ticker}」，稍等一下下～")
            umo = event.unified_msg_origin
            graph = TradingGraph(self.context, umo, progress_callback=progress)
            result = await graph.analyze(ticker, quick_mode=quick)
            return result
        except Exception as e:
            logger.error(f"[analyze_stock] 分析失败: {e}", exc_info=True)
            return f"分析失败: {e}"

    # ================================================================
    # 命令: /股票分析 <code>
    # ================================================================
    async def analyze_stock(self, event: AstrMessageEvent) -> MessageEventResult:
        """启动完整多智能体分析流程。

        主智能体将依次:
        1. 调用国信 API 工具获取数据
        2. 委托 market_analyst 子智能体进行技术分析
        3. 委托 fundamentals_analyst 子智能体进行基本面分析
        4. 委托 news_analyst 子智能体进行宏观/情绪分析
        5. 委托 bull_researcher + bear_researcher 进行多空辩论
        6. 委托 research_manager 综合辩论
        7. 委托 risk_judge 进行风险评估
        8. 汇总生成最终分析报告
        """
        arg = self._extract_command_arg(event.message_str, ["股票分析", "股票"])
        if not arg:
            yield event.plain_result("要分析哪只股票？发代码或者名字给我(・ω・)")
            return

        ticker = arg.strip()

        if self._needs_ticker_resolution(ticker):
            resolved = await self._resolve_stock_name(ticker, event)
            if not resolved:
                yield event.plain_result(f"「{ticker}」找不到捏，换个代码试试？")
                return
            ticker = resolved

        yield event.plain_result(f"好嘞，帮你查「{ticker}」，稍等一下下～")

        async for result in self._run_graph(event, ticker, quick_mode=False):
            yield result

    @filter.command("股票")
    async def stock_command(self, event: AstrMessageEvent) -> MessageEventResult:
        """快捷命令：/股票 <code>"""
        arg = self._extract_command_arg(event.message_str, ["股票"])
        if not arg:
            yield event.plain_result("请提供股票代码或名称，例如：/股票 000001")
            return
        async for result in self.analyze_stock(event):
            yield result

    # ================================================================
    # 命令: /快速分析 <code>
    # ================================================================
    @filter.command("快速分析")
    async def quick_analyze(self, event: AstrMessageEvent) -> MessageEventResult:
        """快速分析 —— 跳过多空辩论，直接汇总。"""
        arg = self._extract_command_arg(event.message_str, ["快速分析"])
        if not arg:
            yield event.plain_result("要快速看哪只？发代码给我(°ω°)")
            return

        ticker = arg.strip()
        if self._needs_ticker_resolution(ticker):
            resolved = await self._resolve_stock_name(ticker, event)
            if not resolved:
                yield event.plain_result(f"「{ticker}」找不到，换个代码试试")
                return
            ticker = resolved

        yield event.plain_result(f"快速模式帮你看「{ticker}」，马上好～")

        async for result in self._run_graph(event, ticker, quick_mode=True):
            yield result

    # ================================================================
    # 命令: /选股 <条件>
    # ================================================================
    @filter.command("选股")
    async def pick_stocks(self, event: AstrMessageEvent) -> MessageEventResult:
        """智能选股 —— 调用国信选股 API。"""
        arg = self._extract_command_arg(event.message_str, ["选股"])
        if not arg:
            yield event.plain_result("说说你想选什么类型的股票？( •̀ ω •́ )✧")
            return

        condition = arg.strip()
        yield event.plain_result(f"帮你找「{condition}」，稍等～")

        prompt = (
            f"用 smart_stock_picking 工具帮用户筛选：{condition}，市场类型stock。"
            f"结果用表格列出来，没找到就说一声并建议换个条件。"
            f"最后加一句：以上结果仅供参考，不构成投资建议，入市需谨慎哦。"
        )
        yield event.request_llm(prompt)

    # ================================================================
    # 命令: /查股 <名称>
    # ================================================================
    @filter.command("查股")
    async def lookup_stock(self, event: AstrMessageEvent) -> MessageEventResult:
        """股票名称 → 代码解析。"""
        arg = self._extract_command_arg(event.message_str, ["查股"])
        if not arg:
            yield event.plain_result("请提供股票名称。用法: /查股 <名称>")
            return

        ticker = arg.strip()
        try:
            if self._needs_ticker_resolution(ticker):
                resolved = await self._resolve_stock_name(ticker, event)
                if resolved is None:
                    yield event.plain_result(f"「{ticker}」找不到，换个名字试试？")
                    return
                ticker = resolved

            market_info = StockUtils.get_market_info(ticker)
            if market_info.get('resolution_failed'):
                yield event.plain_result(f"这个代码查不到捏(・_・?)")
                return

            normalized = market_info['normalized_ticker']
            stock_name = StockUtils.get_stock_name(ticker)

            yield event.plain_result(
                f"{stock_name}（{normalized}）"
                f"，{market_info['market_name']}，{market_info['exchange']}"
                f"，计价货币{market_info['currency_name']}"
            )

        except Exception as e:
            logger.error(f"股票查询失败: {e}", exc_info=True)
            yield event.plain_result("查询炸了，再试一次？")

    # ================================================================
    # 命令: /帮助
    # ================================================================
    @filter.command("帮助")
    async def show_help(self, event: AstrMessageEvent) -> MessageEventResult:
        """显示帮助信息。"""
        yield event.plain_result(
            "我能帮你看股票哦～\n\n"
            "• /股票分析 000001 — 完整分析（含多空辩论）\n"
            "• /快速分析 AAPL — 快速看一下\n"
            "• /选股 市盈率小于20的银行股 — 帮你筛\n"
            "• /查股 茅台 — 查代码和市场\n\n"
            "直接说「分析一下茅台」「快速看看腾讯」也可以(・ω・)\n"
            "数据来自国信证券，仅供参考，不构成投资建议～"
        )

    # ================================================================
    # 内部方法
    # ================================================================

    async def _run_graph(self, event: AstrMessageEvent,
                         ticker: str, quick_mode: bool = False):
        """执行 LangGraph 分析流程，yield 结果给用户。"""
        from .trading_graph import TradingGraph

        umo = event.unified_msg_origin

        async def progress(msg: str):
            try:
                await event.send(event.plain_result(msg))
            except Exception:
                pass

        try:
            graph = TradingGraph(self.context, umo, progress_callback=progress)
            result = await graph.analyze(ticker, quick_mode=quick_mode)
            yield event.plain_result(result)
        except Exception as e:
            logger.error(f"[TradingGraph] 分析失败: {e}", exc_info=True)
            yield event.plain_result(f"分析炸了orz，再试一次？（{e}）")

    @staticmethod
    def _extract_command_arg(message_str: str, command_names: list) -> str:
        """从消息中提取命令参数。"""
        cleaned = message_str.strip()
        for name in command_names:
            for prefix in (f'/{name}', name):
                if cleaned.startswith(prefix):
                    rest = cleaned[len(prefix):]
                    if not rest or rest[0] in (' ', '\t'):
                        return rest.strip()
        return cleaned

    @staticmethod
    def _needs_ticker_resolution(ticker: str) -> bool:
        """判断是否需要名称→代码解析。"""
        return not StockUtils.is_valid_stock_code(ticker)

    async def _resolve_stock_name(self, raw_input: str,
                                  event: AstrMessageEvent = None) -> str | None:
        """解析股票名称 → 代码（本地查找，A股优先）。"""
        try:
            local_result = StockUtils.resolve_stock_name(raw_input)
            if local_result:
                logger.info(f"本地解析: '{raw_input}' → '{local_result}'")
                return local_result
        except Exception as e:
            logger.warning(f"本地名称解析异常: {e}")
        return None
