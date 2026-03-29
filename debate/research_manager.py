"""
研究主管 - 负责协调多方和空方研究，生成综合辩论报告
"""
from typing import Dict

from astrbot.api import logger


class ResearchManager:
    """研究主管 - 管理辩论研究流程"""
    
    def __init__(self, llm, data_fetcher, bull_researcher, bear_researcher):
        self.llm = llm
        self.data_fetcher = data_fetcher
        self.bull_researcher = bull_researcher
        self.bear_researcher = bear_researcher
    
    async def conduct_debate(self, ticker: str, trade_date: str, context: Dict) -> str:
        """
        执行多空辩论
        
        Args:
            ticker: 股票代码
            trade_date: 交易日期
            context: 包含市场分析、基本面分析、新闻分析等上下文
            
        Returns:
            辩论综合报告
        """
        logger.info(f"研究主管开始协调辩论: {ticker}")
        
        # 并行执行多方和空方研究
        bull_task = self.bull_researcher.research(ticker, trade_date, context)
        bear_task = self.bear_researcher.research(ticker, trade_date, context)
        
        bull_report, bear_report = await self._run_parallel(bull_task, bear_task)

        # 处理并行执行中的异常
        import asyncio
        if isinstance(bull_report, Exception):
            logger.error(f"多方研究异常: {bull_report}")
            bull_report = f"多方研究失败: {type(bull_report).__name__}: {bull_report}"
        if isinstance(bear_report, Exception):
            logger.error(f"空方研究异常: {bear_report}")
            bear_report = f"空方研究失败: {type(bear_report).__name__}: {bear_report}"
        
        # 生成综合辩论报告
        debate_report = await self._synthesize_debate(
            ticker, trade_date, context, bull_report, bear_report
        )
        
        logger.info(f"研究主管完成辩论协调: {ticker}")
        
        return debate_report
    
    async def _run_parallel(self, *tasks):
        """并行运行多个任务"""
        import asyncio
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def _synthesize_debate(self, ticker: str, trade_date: str, 
                                 context: Dict, bull_report: str, bear_report: str) -> str:
        """综合多方和空方观点，生成辩论报告"""
        
        from ..utils.stock_utils import StockUtils
        
        market_info = StockUtils.get_market_info(ticker)
        normalized_ticker = market_info['normalized_ticker']
        stock_name = StockUtils.get_stock_name(ticker)
        
        prompt = f"""你是一位资深的研究主管，负责综合多方和空方的研究报告，生成客观的辩论综合报告。

## 股票信息
- 股票名称：{stock_name}
- 股票代码：{ticker}
- 市场：{market_info['market_name']}
- 交易日期：{trade_date}

## 多方研究报告
{bull_report}

## 空方研究报告
{bear_report}

## 已有分析背景
### 市场技术面分析
{context.get('market_analysis', '暂无市场技术面分析')}

### 基本面分析
{context.get('fundamentals_analysis', '暂无基本面分析')}

### 新闻面分析
{context.get('news_analysis', '暂无新闻面分析')}

## 你的任务
请综合多空双方的观点，生成一份客观的辩论综合报告：

### 🎯 辩论综合报告

## 📊 多空力量对比
[对比多空双方的核心观点]

## ⚖️ 双方共识
[多空双方都认可的观点]

## 🔥 核心分歧
[多空双方存在分歧的关键点]

## 📈 多方核心逻辑
[多方最重要的支撑理由]

## 📉 空方核心逻辑
[空方最重要的风险理由]

## 🎯 综合评估
[基于多空辩论的综合评估]

## 💡 投资建议
[综合多空观点的投资建议]

---
重要提醒：
- 必须使用上述格式输出
- 客观平衡地呈现多空双方观点
- 明确指出双方共识和分歧
- 给出基于辩论的综合投资建议
"""
        
        import asyncio
        try:
            response = await asyncio.wait_for(
                self.llm.ask(prompt),
                timeout=120,
            )
        except asyncio.TimeoutError:
            logger.error("辩论综合报告生成超时（120s）")
            response = "⚠️ 辩论综合报告生成超时，请稍后重试。"
        
        return response
