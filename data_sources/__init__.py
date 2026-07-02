"""国信证券 API 数据源 —— 纯 Python stdlib 实现。

整合 4 个国信 skill 的 API 端点:
- market_data: 行情数据（实时行情、历史K线、资金流向、排名、板块）
- financial_data: 财报数据（资产负债表、利润表、现金流量表）
- macro_data: 宏观经济指标（自然语言查询）
- stock_picking: 智能选股（自然语言条件筛选）

所有 API 共用同一个 base URL 和认证方式。
"""
