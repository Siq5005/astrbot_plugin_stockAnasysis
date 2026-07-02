"""国信证券 API 数据源 —— 纯 Python stdlib 实现。

整合 4 个国信 skill 的 API 端点:
- market_data: 行情数据（实时行情、历史K线、资金流向、排名、板块）
- financial_data: 财报数据（资产负债表、利润表、现金流量表）
- macro_data: 宏观经济指标（自然语言查询）
- stock_picking: 智能选股（自然语言条件筛选）

所有 API 共用同一个 base URL 和认证方式。
"""

from .http_client import make_request, is_available, get_api_key

# 行情
from .market_data import (
    query_single_quote, query_combined_quotes, query_fund_flow,
    query_market_ranking, query_related_sectors, query_historical_kline,
    get_set_code, SET_CODE_MAP, SET_DOMAIN_MAP,
)

# 财报
from .financial_data import (
    query_a_stock_balance_sheet, query_a_stock_income_statement,
    query_a_stock_cash_flow, query_hk_stock_balance_sheet,
    query_hk_stock_income_statement, query_hk_stock_cash_flow,
)

# 宏观
from .macro_data import query_macro_data

# 选股
from .stock_picking import smart_stock_picking
