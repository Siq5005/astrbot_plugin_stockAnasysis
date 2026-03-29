"""
空方研究员 - 负责挖掘股票的利空因素
"""
from typing import Dict, List

from astrbot.api import logger


class BearResearcher:
    """空方研究员 - 寻找导致股价下跌的风险因素"""
    
    def __init__(self, llm, data_fetcher):
        self.llm = llm
        self.data_fetcher = data_fetcher
    
    async def research(self, ticker: str, trade_date: str, context: Dict) -> str:
        """
        研究利空因素
        
        Args:
            ticker: 股票代码
            trade_date: 交易日期
            context: 包含市场分析、基本面分析等上下文
            
        Returns:
            空方研究报告
        """
        logger.info(f"空方研究员开始研究: {ticker}")
        
        from ..utils.stock_utils import StockUtils
        
        market_info = StockUtils.get_market_info(ticker)
        normalized_ticker = market_info['normalized_ticker']
        stock_name = StockUtils.get_stock_name(ticker)
        
        prompt = self._build_bear_prompt(
            ticker=normalized_ticker,
            stock_name=stock_name,
            trade_date=trade_date,
            market_info=market_info,
            context=context
        )
        
        response = await self.llm.ask(prompt)
        
        logger.info(f"空方研究员完成研究: {ticker}")
        
        return response
    
    def _build_bear_prompt(self, ticker: str, stock_name: str, trade_date: str, 
                          market_info: Dict, context: Dict) -> str:
        """构建空方研究提示词"""
        
        return f"""你是一位专业的研究员，负责分析股票的利空因素。

## 股票信息
- 股票名称：{stock_name}
- 股票代码：{ticker}
- 市场：{market_info['market_name']}
- 交易日期：{trade_date}

## 已有分析信息
以下是其他分析师提供的信息：

### 市场技术面分析
{context.get('market_analysis', '暂无市场技术面分析')}

### 基本面分析
{context.get('fundamentals_analysis', '暂无基本面分析')}

### 新闻面分析
{context.get('news_analysis', '暂无新闻面分析')}

## 你的任务
请从以下角度深入挖掘该股票的利空因素：

### 📉 利空因素分析

#### 1. 估值泡沫风险
- 当前估值是否过高？
- 是否存在估值回归的风险？

#### 2. 业绩下滑风险
- 业绩是否有下滑压力？
- 增长是否已经放缓？

#### 3. 政策风险
- 是否面临行业监管收紧？
- 是否有政策不利变化？

#### 4. 市场竞争加剧
- 竞争对手是否有更强的动作？
- 市场份额是否受到挤压？

#### 5. 技术面压力
- 技术指标是否显示空头信号？
- 是否存在技术性卖出压力？

#### 6. 资金流向
- 资金是否在持续流出？
- 机构投资者是否在减仓？

#### 7. 宏观经济风险
- 宏观环境是否对该股票不利？
- 行业周期是否处于下行阶段？

## 输出要求
1. 客观分析利空因素，但不要过度悲观
2. 引用具体数据支持你的观点
3. 区分短期和长期利空因素
4. 给出股价可能下跌的风险因素

---
重要提醒：
- 必须使用上述格式输出
- 要有具体的数据支撑
- 区分短期和长期因素
- 保持客观理性的分析态度
"""
