"""AstrBot 金融助手插件入口 —— 国信 API + SubAgent 架构。

命令：
- /股票分析 <code>: 启动完整分析流程（主智能体编排子智能体）
- /快速分析 <code>: 跳过多空辩论的快速分析
- /选股 <条件>: 自然语言智能选股
- /查股 <名称>: 股票名称→代码解析
- /帮助: 显示帮助信息

架构说明：
- 数据源：纯国信证券 API（4 个 skill），零第三方爬取依赖
- 编排：AstrBot SubAgent 框架（主智能体 + 7 个子智能体并行协作）
- 报告：Markdown/TXT/PDF 多格式输出
"""
import os
import re
from datetime import datetime

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api import logger, AstrBotConfig
from astrbot.api.star import Context, Star

from .utils.stock_utils import StockUtils
from .utils.report_utils import (
    extract_conclusion, save_report_pdf, save_report_md,
    save_report_txt, check_pdf_available,
)
from .data_sources.http_client import is_available as guosen_available


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
    # 命令: /股票分析 <code>
    # ================================================================
    @filter.command("股票分析")
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
            "📊 **TradingAgents-AstrBot v2.0**\n\n"
            "**可用命令：**\n\n"
            "1. **股票分析** — 完整多智能体分析（含多空辩论）\n"
            "   命令: /股票分析 <代码或名称>\n"
            "   示例: /股票分析 000001\n"
            "         /股票分析 平安银行\n"
            "         /股票分析 AAPL\n\n"
            "2. **快速分析** — 快速分析（跳过多空辩论，速度更快）\n"
            "   命令: /快速分析 <代码或名称>\n"
            "   示例: /快速分析 600519\n\n"
            "3. **智能选股** — 自然语言条件筛选股票\n"
            "   命令: /选股 <条件>\n"
            "   示例: /选股 市盈率小于20的银行股\n"
            "         /选股 MACD金叉的科技股\n\n"
            "4. **股票信息** — 查询股票基本信息\n"
            "   命令: /查股 <代码或名称>\n"
            "   示例: /查股 000001\n\n"
            "5. **快捷命令** — /股票 <代码>（等同于/股票分析）\n\n"
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
        """解析股票名称 → 代码。

        策略：
        1. 本地查找（akshare A股列表精确/模糊匹配）
        2. LLM 解析（港股/美股名称等本地无法处理的场景）
        """
        # 步骤1：本地查找
        try:
            local_result = StockUtils.resolve_stock_name(raw_input)
            if local_result:
                logger.info(f"本地解析: '{raw_input}' → '{local_result}'")
                return local_result
        except Exception as e:
            logger.warning(f"本地名称解析异常: {e}")

        # 步骤2：LLM 解析（利用 AstrBot 的 LLM）
        prompt = (
            "你是一个股票代码查询助手。用户会输入一个股票名称或关键词，"
            "你需要返回对应的**标准股票代码**。\n\n"
            "返回格式要求：\n"
            "- A股返回6位纯数字代码，例如：平安银行→000001，厦门港务→000905\n"
            "- 港股返回数字.HK格式，例如：腾讯控股→0700.HK，美团→3690.HK\n"
            "- 美股返回大写字母代码，例如：苹果→AAPL，特斯拉→TSLA\n\n"
            "重要规则：\n"
            "1. 只返回一个最匹配的股票代码，不要有任何多余文字、解释或标点\n"
            "2. 如果输入同时有A股和其他市场，优先返回A股代码\n"
            "3. 如果输入不是股票名称（例如是普通词语、指令等），直接回复 UNKNOWN\n"
            "4. 如果完全无法识别对应的股票，直接回复 UNKNOWN\n\n"
            f"用户输入：{raw_input}"
        )

        try:
            result = await self.context.call_llm(prompt)
            result = result.strip().strip('`').strip()
            if result.upper() == 'UNKNOWN' or not result:
                logger.warning(f"LLM无法解析: '{raw_input}'")
                return None
            logger.info(f"LLM解析: '{raw_input}' → '{result}'")
            return result
        except Exception as e:
            logger.error(f"LLM解析失败: {e}")
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
