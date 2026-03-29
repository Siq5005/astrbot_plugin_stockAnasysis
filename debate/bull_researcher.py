"""
多方研究员 - 负责挖掘股票的利好因素
"""
from typing import Dict

from astrbot.api import logger


class BullResearcher:
    """多方研究员 - 寻找支撑股价上涨的证据"""
    
    def __init__(self, llm, data_fetcher):
        self.llm = llm
        self.data_fetcher = data_fetcher
    
    async def research(self, ticker: str, trade_date: str, context: Dict) -> str:
        """
        研究利好因素
        
        Args:
            ticker: 股票代码
            trade_date: 交易日期
            context: 包含市场分析、基本面分析等上下文
            
        Returns:
            多方研究报告
        """
        logger.info(f"多方研究员开始研究: {ticker}")
        
        from ..utils.stock_utils import StockUtils
        
        market_info = StockUtils.get_market_info(ticker)
        normalized_ticker = market_info['normalized_ticker']
        stock_name = StockUtils.get_stock_name(ticker)
        
        prompt = self._build_bull_prompt(
            ticker=normalized_ticker,
            stock_name=stock_name,
            trade_date=trade_date,
            market_info=market_info,
            context=context
        )
        
        response = await self.llm.ask(prompt)
        
        logger.info(f"多方研究员完成研究: {ticker}")
        
        return response
    
    def _build_bull_prompt(self, ticker: str, stock_name: str, trade_date: str, 
                          market_info: Dict, context: Dict) -> str:
        """构建多方研究提示词"""
        
        return f"""你是一位专业的研究员，负责分析股票的利好因素。

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
请从以下角度深入挖掘该股票的利好因素：

### 📈 利好因素分析

#### 1. 估值修复潜力
- 当前估值是否低于行业平均水平？
- 是否存在估值修复的机会？

#### 2. 业绩增长驱动
- 业绩是否有增长潜力？
- 新的增长点在哪里？

#### 3. 政策利好
- 是否有行业政策支持？
- 近期是否有利好政策出台？

#### 4. 市场情绪转暖
- 市场情绪是否在转暖？
- 资金是否开始关注该板块？

#### 5. 技术面支撑
- 技术指标是否显示多头信号？
- 是否有技术性买入机会？

#### 6. 竞争对手对比
- 相比竞争对手的优势在哪里？
- 是否存在市场份额提升空间？

## 输出要求
1. 客观分析利好因素，但不要过度乐观
2. 引用具体数据支持你的观点
3. 区分短期和长期利好因素
4. 给出支撑股价上涨的核心逻辑

---
重要提醒：
- 必须使用上述格式输出
- 要有具体的数据支撑
- 区分短期和长期因素
- 保持客观理性的分析态度
"""
