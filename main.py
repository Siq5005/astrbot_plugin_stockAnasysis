"""AstrBot 金融助手插件入口 —— 国信 API + SubAgent 架构。

命令（支持斜杠命令和自然语言两种方式）：
- /股票分析 <code> 或 "分析一下XX" / "XX怎么样": 完整多智能体分析
- /快速分析 <code> 或 "快速看看XX": 跳过多空辩论的快速分析
- /选股 <条件> 或 "筛选XX的股票": 自然语言智能选股
- /查股 <名称> 或 "XX是什么股票": 股票名称→代码解析
- /帮助 或 "你能做什么": 显示帮助信息

架构说明：
- 数据源：纯国信证券 API（4 个 skill），零第三方爬取依赖
- 编排：AstrBot SubAgent 框架（主智能体 + 7 个子智能体并行协作）
- 报告：Markdown/TXT/PDF 多格式输出
- 交互：支持斜杠命令和自然语言，LLM 意图识别自动路由
"""
import asyncio
import os
import re
from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import logger, AstrBotConfig
from astrbot.api.star import Context, Star, register

from .utils.stock_utils import StockUtils
from .utils.report_utils import (
    extract_conclusion, save_report_pdf, save_report_md,
    save_report_txt, check_pdf_available,
)
from .data_sources.http_client import is_available as guosen_available

# ============================================================
# 自然语言意图识别 prompt


@register("astrbot_plugin_stockanalysis", "Coe", "基于国信API的多智能体金融分析插件", "v2.0.0")
class TradingAssistantPlugin(Star):
    """金融助手插件 —— 国信API + SubAgent 架构"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        logger.info("TradingAssistantPlugin v2.0 初始化中...")
        self.config = config or {}

        # PDF 相关
        self._pdf_available, self._pdf_unavailable_reason = check_pdf_available()
        self.export_pdf = self.config.get('export_pdf', True)
        self._export_txt = False

        if not self._pdf_available and self.export_pdf:
            self._export_txt = True
            logger.warning(
                f"weasyprint 系统依赖缺失，PDF 导出不可用"
                f"（{self._pdf_unavailable_reason}），已自动降级为 TXT。"
            )
            self.export_pdf = False

        if not guosen_available():
            logger.warning(
                "未配置 GS_API_KEY 环境变量，国信 API 工具不可用。"
                "请在环境变量中设置 GS_API_KEY 或联系国信证券获取 API Key。"
            )

        logger.info("TradingAssistantPlugin v2.0 初始化完成（国信API + SubAgent 架构）")

    def terminate(self):
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
            yield event.plain_result(
                "请提供股票代码或名称。\n"
                "用法: /股票分析 <代码>\n"
                "示例: /股票分析 000001\n"
                "      /股票分析 平安银行\n"
                "      /股票分析 AAPL"
            )
            return

        ticker = arg.strip()

        # 名称解析
        if self._needs_ticker_resolution(ticker):
            yield event.plain_result(f"🔍 正在解析「{ticker}」...")
            resolved = await self._resolve_stock_name(ticker, event)
            if not resolved:
                yield event.plain_result(f"❌ 无法识别「{ticker}」，请提供有效的股票代码。")
                return
            yield event.plain_result(f"🔍 已识别「{ticker}」→ {resolved}")
            ticker = resolved

        market_info = StockUtils.get_market_info(ticker)
        stock_name = StockUtils.get_stock_name(ticker)

        yield event.plain_result(
            f"📊 开始分析 **{stock_name}**（{ticker}）\n"
            f"市场: {market_info.get('market_name', 'N/A')}\n\n"
            f"主智能体将调度以下子智能体并行工作：\n"
            f"• 市场技术面分析师\n"
            f"• 基本面分析师\n"
            f"• 新闻宏观分析师\n"
            f"• 多方/空方研究员\n\n"
            f"⏳ 分析进行中，预计耗时 1-3 分钟..."
        )

        # 构建主智能体的分析编排提示词，交给 AstrBot 框架执行
        prompt = self._build_analysis_prompt(ticker, stock_name, market_info, quick_mode=False)
        yield event.request_llm(prompt)

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
            yield event.plain_result("请提供股票代码。用法: /快速分析 <代码>")
            return

        ticker = arg.strip()
        if self._needs_ticker_resolution(ticker):
            resolved = await self._resolve_stock_name(ticker, event)
            if not resolved:
                yield event.plain_result(f"❌ 无法识别「{ticker}」")
                return
            ticker = resolved

        market_info = StockUtils.get_market_info(ticker)
        stock_name = StockUtils.get_stock_name(ticker)

        yield event.plain_result(
            f"⚡ 快速分析模式：**{stock_name}**（{ticker}）\n"
            f"跳过多空辩论，直接生成分析报告。预计 30-60 秒。"
        )

        prompt = self._build_analysis_prompt(ticker, stock_name, market_info, quick_mode=True)
        yield event.request_llm(prompt)

    # ================================================================
    # 命令: /选股 <条件>
    # ================================================================
    @filter.command("选股")
    async def pick_stocks(self, event: AstrMessageEvent) -> MessageEventResult:
        """智能选股 —— 调用国信选股 API。"""
        arg = self._extract_command_arg(event.message_str, ["选股"])
        if not arg:
            yield event.plain_result(
                "请提供选股条件。\n"
                "用法: /选股 <自然语言条件>\n"
                "示例: /选股 市盈率小于20的银行股\n"
                "      /选股 MACD金叉且成交量放大的科技股\n"
                "      /选股 净利润增长大于30%的医药股"
            )
            return

        condition = arg.strip()
        yield event.plain_result(f"🔍 正在筛选：{condition}...")

        prompt = (
            f"请使用 tool_smart_stock_picking 工具进行智能选股。\n\n"
            f"筛选条件：{condition}\n"
            f"市场类型：stock（A股）\n\n"
            f"将结果以清晰的表格形式呈现给用户。"
            f"如果结果为空，告知用户未找到匹配的股票并建议放宽条件。\n\n"
            f"最后必须附加风险提示：\n"
            f"「⚠️ 以上结果由智能选股系统生成，仅供参考，不构成投资建议。\n"
            f"市场有风险，投资需谨慎。」"
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
                    yield event.plain_result(f"❌ 无法识别「{ticker}」对应的股票。")
                    return
                yield event.plain_result(f"🔍 已识别「{ticker}」→ {resolved}")
                ticker = resolved

            market_info = StockUtils.get_market_info(ticker)
            if market_info.get('resolution_failed'):
                yield event.plain_result(f"❌ {market_info['resolution_message']}")
                return

            normalized = market_info['normalized_ticker']
            stock_name = StockUtils.get_stock_name(ticker)

            info_text = (
                f"**股票信息**\n\n"
                f"股票名称: {stock_name}\n"
                f"股票代码: {normalized}\n"
                f"所属市场: {market_info['market_name']}\n"
                f"交易所: {market_info['exchange']}\n"
                f"计价货币: {market_info['currency_name']}（{market_info['currency_symbol']}）\n"
            )
            yield event.plain_result(info_text)

        except Exception as e:
            logger.error(f"股票查询失败: {e}", exc_info=True)
            yield event.plain_result("查询服务暂时不可用，请稍后重试。")

    # ================================================================
    # 命令: /帮助
    # ================================================================
    @filter.command("帮助")
    async def show_help(self, event: AstrMessageEvent) -> MessageEventResult:
        """显示帮助信息。"""
        help_text = (
            "📊 **astrbot_plugin_stockAnasysis v2.0**\n\n"
            "**支持斜杠命令和自然语言两种方式：**\n\n"
            "1. **股票分析** — 完整多智能体分析（含多空辩论）\n"
            "   命令: /股票分析 <代码或名称>\n"
            "   自然语言: \"分析一下平安银行\"、\"茅台怎么样\"\n\n"
            "2. **快速分析** — 快速分析（跳过多空辩论）\n"
            "   命令: /快速分析 <代码或名称>\n"
            "   自然语言: \"快速看看腾讯\"、\"简单分析下AAPL\"\n\n"
            "3. **智能选股** — 自然语言条件筛选股票\n"
            "   命令: /选股 <条件>\n"
            "   自然语言: \"筛选市盈率小于20的银行股\"、\"有没有股息率高的蓝筹股\"\n\n"
            "4. **股票信息** — 查询股票基本信息\n"
            "   命令: /查股 <代码或名称>\n"
            "   自然语言: \"宁德时代是什么股票\"、\"AAPL代码是多少\"\n\n"
            "**支持市场:**\n"
            "- A股 (如: 000001, 600000, 平安银行)\n"
            "- 港股 (如: 0700.HK, 腾讯)\n"
            "- 美股 (如: AAPL, TSLA, NVDA)\n\n"
            "**数据来源:** 国信证券官方 API\n"
            "**架构:** AstrBot SubAgent 多智能体协作\n"
            "**风险提示:** 分析结果仅供参考，不构成投资建议。"
        )
        yield event.plain_result(help_text)

    # ================================================================
    # 自然语言入口：直接交给主智能体处理
    # ================================================================
    @filter.regex(r"^[^/].+")  # 匹配不以 / 开头的消息（自然语言）
    async def handle_natural_language(self, event: AstrMessageEvent) -> MessageEventResult:
        """处理自然语言输入。

        不自行做意图识别，而是把消息交给 AstrBot 主智能体。
        主智能体拥有全部工具（query_single_quote / smart_stock_picking 等）
        和 SubAgent transfer_to_* 能力，能自动判断用户意图并调用对应功能。
        """
        msg = event.message_str.strip()
        if not msg or msg.startswith('/'):
            return

        logger.info(f"[NL] 收到自然语言: {msg[:80]}")

        yield event.request_llm(
            "用户通过自然语言发来一条消息：「" + msg + "」\n\n"
            "请根据用户意图，使用对应的工具或子智能体来处理：\n"
            "- 如果是想分析某只股票（含 分析/看看/怎么样/能买吗 等关键词），"
            "请调用 query_historical_kline / query_financials 获取数据，"
            "然后调度 market_analyst / fundamentals_analyst / news_analyst 三个子智能体，"
            "接着走 bull_researcher / bear_researcher / research_manager 多空辩论，"
            "最后用 risk_judge 评估风险，汇总生成完整分析报告。\n"
            "- 如果是想快速了解（含 快速/简单/速览 等关键词），"
            "跳过多空辩论，直接分析师->风险评估->汇总。\n"
            "- 如果是想筛选股票（含 选/筛选/找/推荐/有没有 等关键词），"
            "请调用 smart_stock_picking 工具。\n"
            "- 如果是查询股票基本信息（含 是什么/代码/属于哪个市场 等关键词），"
            "请调用 query_single_quote 工具查询后回复。\n"
            "- 如果是问功能或帮助，请展示可用命令和示例。\n"
            "- 如果和股票/金融完全无关，请友好告知用户你的能力范围。"
        )

    # ================================================================
    # 内部方法
    # ================================================================

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

    @staticmethod
    def split_report_by_sections(report: str) -> list[str]:
        """将 Markdown 报告按 ## 标题拆分为多个段落。"""
        parts = re.split(r'\n(?=## )', report)
        sections = []
        for part in parts:
            text = part.strip()
            if not text:
                continue
            if sections and not text.startswith('#'):
                continue
            sections.append(text)
        return sections

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

    def _build_analysis_prompt(self, ticker: str, stock_name: str,
                               market_info: dict, quick_mode: bool = False) -> str:
        """构建主智能体的分析编排提示词。

        主智能体使用此提示词指导 AstrBot SubAgent 框架：
        - 调用 transfer_to_* 工具将任务分配给子智能体
        - 子智能体各自调用国信 API 工具获取数据
        - 主智能体收集结果并汇总报告
        """
        market = market_info.get('market_name', '未知')
        exchange = market_info.get('exchange', '未知')
        currency = market_info.get('currency_name', 'CNY')
        now = datetime.now().strftime('%Y-%m-%d %H:%M')

        prompt = f"""# 股票分析任务

请对以下股票进行全面的投资分析，生成完整的分析报告。

## 股票信息
- 股票名称: {stock_name}
- 股票代码: {ticker}
- 市场: {market}（{exchange}）
- 货币: {currency}

## 执行步骤

### 第一步：数据收集（并行）
使用以下工具同时获取基础数据：
- tool_query_historical_kline(code="{ticker}", days=60) —— 历史K线和均线
- tool_query_single_quote(code="{ticker}") —— 实时行情
- tool_query_fund_flow(code="{ticker}", period=30) —— 资金流向
- tool_query_financials(code="{ticker}") —— 财务报表
- tool_query_macro_data(query="中国最新PMI CPI 货币政策 行业政策") —— 宏观背景

### 第二步：并行调度子智能体分析
数据收集完成后，**同时**将以下三个任务分配给子智能体（可并行执行）：

1. transfer_to_market_analyst("请对 {stock_name}（{ticker}）进行技术面分析。市场: {market}，货币: {currency}。请先调用工具获取K线和实时行情数据，然后按格式输出分析报告。")

2. transfer_to_fundamentals_analyst("请对 {stock_name}（{ticker}）进行基本面分析。市场: {market}。请先调用工具获取财报数据，提取PE/PB/ROE/毛利率/净利率等关键指标，然后按格式输出分析报告。")

3. transfer_to_news_analyst("请对 {stock_name}（{ticker}）进行宏观和情绪面分析。市场: {market}。请先调用工具获取宏观经济数据和资金流向，评估市场情绪，然后按格式输出分析报告。")

以上三个子智能体**必须同时并行**调度，等待全部完成后继续。
"""

        if not quick_mode:
            prompt += f"""
### 第三步：多空辩论（并行）
分析师报告完成后，**同时**调度多方和空方研究员：

4. transfer_to_bull_researcher("请基于以下三份分析报告，深度挖掘 {stock_name}（{ticker}）的利好因素。市场: {market}。\n\n=== 市场技术面分析 ===\n{{{{market_analysis}}}}\n\n=== 基本面分析 ===\n{{{{fundamentals_analysis}}}}\n\n=== 新闻宏观分析 ===\n{{{{news_analysis}}}}")

5. transfer_to_bear_researcher("请基于以下三份分析报告，深度挖掘 {stock_name}（{ticker}）的利空因素。市场: {market}。\n\n=== 市场技术面分析 ===\n{{{{market_analysis}}}}\n\n=== 基本面分析 ===\n{{{{fundamentals_analysis}}}}\n\n=== 新闻宏观分析 ===\n{{{{news_analysis}}}}")

多方和空方**同时并行**调度，等待全部完成后继续。

### 第四步：辩论综合
6. transfer_to_research_manager("请综合多方和空方的研究报告，生成 {stock_name}（{ticker}）的辩论综合报告。市场: {market}。\n\n=== 多方研究报告 ===\n{{{{bull_report}}}}\n\n=== 空方研究报告 ===\n{{{{bear_report}}}}")
"""
        else:
            prompt += """
### 第三步：快速评估（跳过多空辩论）
本次为快速分析模式，跳过多空辩论环节，直接进行风险评估。
"""

        prompt += f"""
### 最后一步：风险评估
7. transfer_to_risk_judge("请综合所有分析报告，对 {stock_name}（{ticker}）进行最终风险评估。市场: {market}。请给出明确的风险等级和投资建议。\n\n=== 分析汇总 ===\n{{{{all_analysis}}}}")

### 最终步骤：汇总报告
所有子智能体完成后，请汇总结果，生成完整的投资分析报告。

报告格式：

# {stock_name}（{ticker}）投资分析报告

> 分析时间: {now}
> 市场: {market}（{exchange}）
> 数据来源: 国信证券官方 API

---

[逐段呈现各子智能体的分析结果，保持原有格式]

---

## ⚠️ 免责声明

本报告由 AI 多智能体系统自动生成，仅供参考，不构成投资建议。
市场有风险，投资需谨慎。投资者应独立做出投资决策并承担相应风险。
"""
        return prompt
