"""
TradingAgents-AstrBot - 基于国信API + AstrBot SubAgent 的多智能体金融分析插件。

v2.0 重大架构变更:
- 数据源: 纯国信证券 API（4个skill），零第三方爬取依赖
- 编排: AstrBot SubAgent 框架替代 LangGraph
- 依赖: 大幅简化（移除 langgraph/akshare/yfinance/curl-cffi/pandas/aiohttp/langchain-core）
"""

__version__ = "2.0.0"
