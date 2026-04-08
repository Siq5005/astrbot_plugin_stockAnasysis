"""
基本面分析师 - 负责基本面分析
"""
from typing import Dict

from astrbot.api import logger

from .base import BaseAnalyst


class FundamentalsAnalyst(BaseAnalyst):
    """基本面分析师 - 复刻原始项目的基本面分析师角色"""
    
    def __init__(self, llm, data_fetcher):
        super().__init__(llm, data_fetcher)
    
    def _get_system_prompt(self) -> str:
        return """你是一位专业的金融基本面分析师，负责分析股票的基本面情况。

## 职责
1. 分析公司盈利能力（净利润、毛利率、净利率）
2. 分析估值水平（PE、PB、PS等）
3. 分析资产负债结构
4. 分析现金流状况
5. 分析成长性（营收增长、利润增长）
6. 与行业平均水平对比

## 输出格式
请使用以下格式输出分析报告：

### 基本面分析报告

## 📊 公司概况
- 公司名称：XXX
- 股票代码：XXX
- 所属行业：XXX

## 💼 盈利能力分析
[分析公司的盈利能力和盈利质量]

## 📈 成长性分析
[分析公司的营收和利润增长情况]

## 💰 估值分析
[分析当前的估值水平是否合理]

## 📉 财务风险
[分析公司的负债水平和财务风险]

## 📋 关键财务数据
[列出关键财务指标]

## 💭 基本面投资建议
[给出基于基本面的投资建议]

---
重要提醒：
- 必须使用上述格式输出
- 重点关注PE、PB、ROE、净利润增长率等核心指标
- 与行业平均水平进行对比
- 注意财务风险和负债结构
"""

    def _get_etf_system_prompt(self) -> str:
        """ETF基本面分析专用系统提示词"""
        return """你是一位专业的ETF基金分析师，负责分析ETF基金的基本面情况。

## 职责
1. 分析基金基本信息（基金类型、成立时间、基金规模、基金管理人）
2. 分析净值表现（单位净值、累计净值、净值增长率）
3. 分析折溢价情况（二级市场交易价格与IOPV的偏离度）
4. 分析跟踪效果（跟踪指数、跟踪误差）
5. 分析资金流向（份额变动、主力资金进出）
6. 分析费率结构（管理费、托管费）

## 输出格式
请使用以下格式输出分析报告：

### ETF基本面分析报告

## 📊 基金概况
- 基金名称：XXX
- 基金代码：XXX
- 基金类型：XXX
- 跟踪指数：XXX
- 基金规模：XXX

## 💰 净值分析
[分析基金净值走势和增长率]

## 📈 折溢价分析
[分析折溢价水平及其含义]

## 🔄 资金流向分析
[分析ETF份额变动和资金流向]

## 📋 关键基金指标
[列出净值、折价率、规模等关键指标]

## ⚖️ 费率与成本分析
[分析管理费、托管费等成本]

## 💭 ETF投资建议
[给出基于基本面的ETF投资建议]

---
重要提醒：
- ETF没有PE、PB、ROE等传统公司财务指标
- 重点关注净值走势、折溢价率、跟踪误差、资金流向
- 注意ETF与跟踪指数的偏离程度
- 关注份额变化反映的机构投资者动向
"""
    
    async def analyze(self, ticker: str, trade_date: str) -> str:
        """执行基本面分析（自行获取数据）"""
        market_info, normalized_ticker, stock_name = self._resolve_ticker_info(ticker)
        logger.info(f"基本面分析师开始分析: {ticker}")

        fundamentals_data = await self.data_fetcher.get_fundamentals(normalized_ticker, trade_date)

        is_etf = market_info.get('is_etf', False)
        prompt = self._build_analysis_prompt(
            ticker=normalized_ticker,
            trade_date=trade_date,
            market_info=market_info,
            fundamentals_data=fundamentals_data,
            extra_context=self._get_extra_context(stock_name, normalized_ticker, market_info),
            is_etf=is_etf
        )

        report = await self._call_llm(prompt)
        logger.info(f"基本面分析师完成分析: {ticker}, 报告长度: {len(report)}")
        return report

    async def analyze_with_data(self, ticker: str, trade_date: str, fundamentals_data_raw: str) -> str:
        """使用预获取的基本面数据执行分析"""
        market_info, normalized_ticker, stock_name = self._resolve_ticker_info(ticker)
        logger.info(f"基本面分析师开始分析（预取数据）: {ticker}")

        is_etf = market_info.get('is_etf', False)
        prompt = self._build_analysis_prompt(
            ticker=normalized_ticker,
            trade_date=trade_date,
            market_info=market_info,
            fundamentals_data=fundamentals_data_raw,
            extra_context=self._get_extra_context(stock_name, normalized_ticker, market_info),
            is_etf=is_etf
        )

        report = await self._call_llm(prompt)
        logger.info(f"基本面分析师完成分析: {ticker}, 报告长度: {len(report)}")
        return report

    def _get_extra_context(self, stock_name: str, ticker: str, market_info: Dict) -> str:
        """获取额外上下文"""
        is_etf = market_info.get('is_etf', False)
        if is_etf:
            return f"""## 分析要求
请重点关注 {stock_name}（{ticker}）的ETF基本面分析要点：

1. **净值表现**：单位净值、累计净值的走势和增长率
2. **折溢价水平**：二级市场交易价格与IOPV（基金参考净值）的偏离程度
3. **跟踪效果**：基金净值与跟踪指数的偏离度和跟踪误差
4. **资金流向**：ETF份额变化、主力资金进出情况
5. **基金规模**：最新AUM（管理规模）及其变化趋势
6. **费率结构**：管理费、托管费等对长期收益的影响

## 市场特点
- 市场类型：{market_info['market_name']}
- 货币单位：{market_info['currency_name']}（{market_info['currency_symbol']}）
- 投资品种：ETF（交易所交易基金）

⚠️ 注意：ETF无PE、PB、ROE等传统财务指标，请重点分析净值、折溢价、跟踪误差等基金特有指标。
"""
        return f"""## 分析要求
请重点关注 {stock_name}（{ticker}）的基本面分析要点：

1. **估值水平**：PE、PB是否处于历史低位/高位
2. **盈利能力**：ROE、毛利率、净利率是否稳定
3. **成长性**：营收和利润增长率
4. **财务健康**：资产负债率、现金流状况
5. **行业对比**：与行业平均水平的比较

## 市场特点
- 市场类型：{market_info['market_name']}
- 货币单位：{market_info['currency_name']}（{market_info['currency_symbol']}）

请基于上述数据，进行专业的基本面分析。
"""
