"""
新闻分析师 - 负责消息面分析
"""
from typing import Dict

from astrbot.api import logger

from .base import BaseAnalyst


class NewsAnalyst(BaseAnalyst):
    """新闻分析师 - 复刻原始项目的新闻分析师角色"""
    
    def __init__(self, llm, data_fetcher):
        super().__init__(llm, data_fetcher)
    
    def _get_system_prompt(self) -> str:
        return """你是一位专业的财经新闻分析师，负责分析新闻和事件对股票价格的影响。

## 职责
1. 评估新闻的时效性和可信度
2. 分析新闻对股价的短期影响（1-3天）
3. 区分利好新闻和利空新闻
4. 分析市场情绪变化
5. 识别可能影响股价的关键信息点
6. 评估新闻对投资者信心的影响

## 输出格式
请使用以下格式输出分析报告：

### 新闻分析报告

## 📰 近期重要新闻
[列出近期重要新闻并标注类型]

## 📢 利好因素
[分析对股价有正面影响的新闻]

## ⚠️ 利空因素
[分析对股价有负面影响的新闻]

## 🎯 关键信息点
[识别新闻中的关键信息点]

## 📊 市场情绪评估
[评估当前市场情绪（乐观/中性/悲观）]

## 💭 新闻面投资建议
[基于新闻面对股价的影响给出建议]

---
重要提醒：
- 必须使用上述格式输出
- 区分利好和利空因素
- 关注新闻的时效性
- 评估新闻对短期股价的影响
"""
    
    async def analyze(self, ticker: str, trade_date: str) -> str:
        """执行新闻分析（自行获取数据）"""
        market_info, normalized_ticker, stock_name = self._resolve_ticker_info(ticker)
        logger.info(f"新闻分析师开始分析: {ticker}")

        news_data = await self.data_fetcher.get_news(normalized_ticker, trade_date)
        sentiment_data = await self.data_fetcher.get_sentiment(normalized_ticker, trade_date)

        prompt = self._build_analysis_prompt(
            ticker=normalized_ticker,
            trade_date=trade_date,
            market_info=market_info,
            news_data=news_data,
            sentiment_data=sentiment_data,
            extra_context=self._get_extra_context(stock_name, normalized_ticker, market_info)
        )

        report = await self._call_llm(prompt)
        logger.info(f"新闻分析师完成分析: {ticker}, 报告长度: {len(report)}")
        return report

    async def analyze_with_data(self, ticker: str, trade_date: str,
                                 news_data_raw: str, sentiment_data_raw: str) -> str:
        """使用预获取的新闻和情绪数据执行分析"""
        market_info, normalized_ticker, stock_name = self._resolve_ticker_info(ticker)
        logger.info(f"新闻分析师开始分析（预取数据）: {ticker}")

        prompt = self._build_analysis_prompt(
            ticker=normalized_ticker,
            trade_date=trade_date,
            market_info=market_info,
            news_data=news_data_raw,
            sentiment_data=sentiment_data_raw,
            extra_context=self._get_extra_context(stock_name, normalized_ticker, market_info)
        )

        report = await self._call_llm(prompt)
        logger.info(f"新闻分析师完成分析: {ticker}, 报告长度: {len(report)}")
        return report
    
    def _get_extra_context(self, stock_name: str, ticker: str, market_info: Dict) -> str:
        """获取额外上下文"""
        return f"""## 分析要求
请重点关注以下新闻面分析要点：

1. **时效性评估**：新闻发布时间距现在多久
2. **影响力评估**：新闻对股价的潜在影响程度
3. **利好/利空判断**：明确标注利好和利空因素
4. **情绪变化**：分析新闻导致的投资者情绪变化
5. **历史类比**：与历史类似新闻的市场反应对比

## 市场特点
- 市场类型：{market_info['market_name']}
- 货币单位：{market_info['currency_name']}（{market_info['currency_symbol']}）

请基于上述数据，进行专业的新闻面分析。
"""
