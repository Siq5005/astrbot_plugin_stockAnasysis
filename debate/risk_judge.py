"""
风险裁判 - 负责评估整体投资风险并给出风险等级
"""
import logging
from typing import Dict

logger = logging.getLogger("debate.risk_judge")


class RiskJudge:
    """风险裁判 - 评估整体投资风险"""
    
    def __init__(self, llm, data_fetcher):
        self.llm = llm
        self.data_fetcher = data_fetcher
    
    async def assess_risk(self, ticker: str, trade_date: str, context: Dict, 
                         debate_report: str) -> str:
        """
        评估投资风险
        
        Args:
            ticker: 股票代码
            trade_date: 交易日期
            context: 包含市场分析、基本面分析、新闻分析等上下文
            debate_report: 辩论综合报告
            
        Returns:
            风险评估报告
        """
        logger.info(f"风险裁判开始评估风险: {ticker}")
        
        from ..utils.stock_utils import StockUtils
        
        market_info = StockUtils.get_market_info(ticker)
        normalized_ticker = market_info['normalized_ticker']
        stock_name = StockUtils.get_stock_name(ticker)
        
        # 获取市场数据用于风险评估
        market_data = await self.data_fetcher.get_market_data(
            normalized_ticker, trade_date
        )
        
        prompt = self._build_risk_prompt(
            ticker=normalized_ticker,
            stock_name=stock_name,
            trade_date=trade_date,
            market_info=market_info,
            market_data=market_data,
            context=context,
            debate_report=debate_report
        )
        
        response = await self.llm.ask(prompt)
        
        logger.info(f"风险裁判完成风险评估: {ticker}")
        
        return response
    
    async def assess_risk_with_data(self, ticker: str, trade_date: str, context: Dict,
                                     debate_report: str, market_data_raw) -> str:
        """
        使用预获取的市场数据评估投资风险（不再重新获取数据）

        Args:
            ticker: 股票代码
            trade_date: 交易日期
            context: 包含市场分析、基本面分析、新闻分析等上下文
            debate_report: 辩论综合报告
            market_data_raw: 预获取的市场数据

        Returns:
            风险评估报告
        """
        logger.info(f"风险裁判开始评估风险（预取数据）: {ticker}")

        from ..utils.stock_utils import StockUtils

        market_info = StockUtils.get_market_info(ticker)
        normalized_ticker = market_info['normalized_ticker']
        stock_name = StockUtils.get_stock_name(ticker)

        prompt = self._build_risk_prompt(
            ticker=normalized_ticker,
            stock_name=stock_name,
            trade_date=trade_date,
            market_info=market_info,
            market_data=market_data_raw,
            context=context,
            debate_report=debate_report
        )

        response = await self.llm.ask(prompt)

        logger.info(f"风险裁判完成风险评估: {ticker}")

        return response
    
    def _build_risk_prompt(self, ticker: str, stock_name: str, trade_date: str,
                          market_info: Dict, market_data: Dict, 
                          context: Dict, debate_report: str) -> str:
        """构建风险评估提示词"""
        
        # 提取市场数据的关键风险指标
        volatility = "未知"
        volume_ratio = "未知"
        
        if market_data and 'data' in market_data:
            data = market_data.get('data', {})
            if 'volatility' in data:
                volatility = data.get('volatility', '未知')
            if 'volume_ratio' in data:
                volume_ratio = data.get('volume_ratio', '未知')
        
        return f"""你是一位资深的风险管理专家，负责评估股票的整体投资风险。

## 股票信息
- 股票名称：{stock_name}
- 股票代码：{ticker}
- 市场：{market_info['market_name']}
- 交易日期：{trade_date}

## 市场数据摘要
- 波动率：{volatility}
- 量比：{volume_ratio}
- 市场：{market_info['market_name']}

## 辩论综合报告
{debate_report}

## 已有分析背景
### 市场技术面分析
{context.get('market_analysis', '暂无市场技术面分析')}

### 基本面分析
{context.get('fundamentals_analysis', '暂无基本面分析')}

### 新闻面分析
{context.get('news_analysis', '暂无新闻面分析')}

## 你的任务
请进行全面的风险评估：

### ⚠️ 风险评估报告

## 🎯 风险等级
[综合评估：极高风险/高风险/中等风险/低风险/极低风险]

## 📊 风险因素分解

### 🔴 高风险因素
[列出主要的高风险因素]

### 🟡 中等风险因素
[列出中等风险因素]

### 🟢 低风险因素
[列出低风险因素]

## 💰 风险收益比
[评估风险收益比是否合理]

## 🛡️ 风险缓解建议
[提供降低风险的建议]

## ⚡ 紧急风险提示
[如果有需要特别关注的紧急风险]

## 📋 投资风险总结
[总结整体风险状况和投资建议]

---
重要提醒：
- 必须使用上述格式输出
- 给出明确的风险等级
- 区分不同级别的风险因素
- 提供具体的风险缓解建议
"""
