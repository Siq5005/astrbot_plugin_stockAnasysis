"""AstrBot 工具注册 —— 将国信 API 包装为 LLM 可调用工具。

每个工具包含:
- 函数实现（调用 data_sources/ 模块）
- 工具描述（LLM 用来理解何时调用）
- 参数类型注解（LLM 用来正确传参）

工具按用途分组，可在 WebUI SubAgent 编排中按需分配给子智能体：
- 行情工具 → 市场分析师、多空研究员
- 财报工具 → 基本面分析师
- 宏观工具 → 新闻/情绪分析师
- 选股工具 → 主智能体（/选股 命令）
"""
import asyncio
import json
import logging
from typing import Optional

try:
    from astrbot.api import logger
except ImportError:
    logger = logging.getLogger(__name__)


# ============================================================
# 内部辅助
# ============================================================

async def _run_sync(func, *args, **kwargs):
    """在线程池中执行同步函数（国信 API 调用），避免阻塞事件循环。"""
    return await asyncio.to_thread(func, *args, **kwargs)


def _format_result(result) -> str:
    """安全地将 API 响应格式化为字符串。"""
    if result is None:
        return "查询无返回数据"
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        try:
            return json.dumps(result, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(result)
    return str(result)


def _clean_code(code: str) -> str:
    """清理股票代码，去除市场后缀。"""
    for suffix in ('.HK', '.SH', '.SZ', '.BJ'):
        code = code.replace(suffix, '')
    return code


def _get_market_info_for_code(code: str) -> dict:
    """根据股票代码推断市场信息。"""
    from .utils.stock_utils import StockUtils
    return StockUtils.get_market_info(code)


# ============================================================
# 行情数据工具组
# ============================================================

async def tool_query_single_quote(code: str, market: str = "CN") -> str:
    """获取单只股票实时行情数据，包括最新价、涨跌幅、成交量、市盈率、总市值等。

    适用场景：需要一只股票的当前实时价格和交易数据时使用。

    Args:
        code: 股票代码。A股6位数字(如600519)，港股(如0700.HK)，美股(如AAPL)
        market: 市场类型，CN=A股, HK=港股, US=美股。默认CN
    """
    from .data_sources.market_data import query_single_quote, get_set_code

    set_code = get_set_code(code, market)
    target = 3 if market in ("HK", "US") else 0
    clean = _clean_code(code)
    result = await _run_sync(query_single_quote, clean, set_code, target)
    return _format_result(result)


async def tool_query_historical_kline(code: str, market: str = "CN",
                                      days: int = 60) -> str:
    """获取股票历史K线数据（近N个交易日），包含日期、开高低收、成交量、MA均线。

    适用场景：需要分析股价走势、技术形态、均线系统时使用。

    Args:
        code: 股票代码
        market: 市场类型 CN/HK/US
        days: 近几个交易日，默认60
    """
    from .data_sources.market_data import query_historical_kline, get_set_code

    set_code = get_set_code(code, market)
    target = 3 if market in ("HK", "US") else 0
    clean = _clean_code(code)
    result = await _run_sync(
        query_historical_kline, clean, set_code, days, target, "5,10,20,60"
    )
    return _format_result(result)


async def tool_query_fund_flow(code: str, market: str = "CN",
                               period: int = 30) -> str:
    """获取股票资金流向数据（主力/大户/散户净流入流出），最大60日。

    适用场景：分析主力资金动向、判断资金面情况时使用。

    Args:
        code: 股票代码
        market: 市场类型 CN/HK/US
        period: 查询天数，默认30
    """
    from .data_sources.market_data import query_fund_flow, get_set_code

    set_code = get_set_code(code, market)
    clean = _clean_code(code)
    result = await _run_sync(query_fund_flow, clean, set_code, min(period, 60))
    return _format_result(result)


async def tool_query_market_ranking(set_domain: int = 6, want_num: int = 10,
                                    sort_type: int = 1) -> str:
    """查询A股涨跌排名。

    适用场景：需要了解市场整体涨跌情况、寻找强势/弱势股票时使用。

    Args:
        set_domain: 0=上证A股, 2=深证A股, 6=沪深A股(默认), 14=创业板, 14515=北交所, 11005=ETF
        want_num: 返回数量，默认10，最多80
        sort_type: 1=涨幅(默认), 2=跌幅
    """
    from .data_sources.market_data import query_market_ranking
    result = await _run_sync(query_market_ranking, set_domain, want_num, sort_type)
    return _format_result(result)


# ============================================================
# 财报数据工具组
# ============================================================

async def tool_query_financials(code: str, market: str = "CN") -> str:
    """获取股票最新财务报表数据：资产负债表、利润表、现金流量表。

    通过三大报表可提取: PE, PB, ROE, ROA, 毛利率, 净利率, 营收增长率, 净利润增长率,
    资产负债率, 流动比率, 每股收益等核心财务指标。

    适用场景：分析公司基本面、估值水平、盈利能力、财务健康状况时使用。

    Args:
        code: 股票代码
        market: CN=A股, HK=港股
    """
    from .data_sources.financial_data import (
        query_a_stock_balance_sheet, query_a_stock_income_statement,
        query_a_stock_cash_flow, query_hk_stock_balance_sheet,
        query_hk_stock_income_statement, query_hk_stock_cash_flow,
    )

    clean = _clean_code(code)

    if market == "HK":
        bs, inc, cf = await asyncio.gather(
            _run_sync(query_hk_stock_balance_sheet, clean),
            _run_sync(query_hk_stock_income_statement, clean),
            _run_sync(query_hk_stock_cash_flow, clean),
            return_exceptions=True,
        )
    else:
        mkt = "SH" if code.startswith(('6', '9', '5')) else "SZ"
        bs, inc, cf = await asyncio.gather(
            _run_sync(query_a_stock_balance_sheet, clean, mkt),
            _run_sync(query_a_stock_income_statement, clean, mkt),
            _run_sync(query_a_stock_cash_flow, clean, mkt),
            return_exceptions=True,
        )

    return f"""## 财务报表数据

### 资产负债表
{_format_result(bs)}

### 利润表
{_format_result(inc)}

### 现金流量表
{_format_result(cf)}
"""


# ============================================================
# 工具组: 宏观经济
# ============================================================

async def tool_query_macro_data(query: str) -> str:
    """查询全球宏观经济指标数据。

    支持: GDP, CPI, PPI, PMI, M2, LPR, SHIBOR, 汇率, 进出口,
    美国非农/CPI/联邦基金利率, 商品期货(原油/黄金/铜/铝)等。

    适用场景：需要宏观经济背景分析、行业景气度判断时使用。

    Args:
        query: 中文自然语言查询，例如 "中国最新GDP增速", "近三个月COMEX黄金走势"
    """
    from .data_sources.macro_data import query_macro_data

    result = await _run_sync(query_macro_data, query)
    if isinstance(result, dict):
        return result.get("content", "") or result.get("error", "宏观经济数据查询失败")
    return str(result)


# ============================================================
# 工具组: 智能选股
# ============================================================

async def tool_smart_stock_picking(searchstring: str,
                                   searchtype: str = "stock") -> str:
    """根据自然语言条件筛选股票。

    支持: 财务指标(PE/PB/ROE/净利润增长等)、技术指标(MACD/KDJ/均线等)、
    行业板块、涨跌幅等多维度组合筛选。

    适用场景：用户描述选股条件时使用。
    例如: "市盈率小于20的银行股", "MACD金叉的科技股", "净利润增长大于30%的医药股"

    注意: 此工具只做筛选，筛选结果需要具体代码才能进一步分析。

    Args:
        searchstring: 中文自然语言筛选条件
        searchtype: stock=A股, fund=基金, HK_stock=港股, US_stock=美股, NEEQ=新三板, index=指数
    """
    from .data_sources.stock_picking import smart_stock_picking

    result = await _run_sync(smart_stock_picking, searchstring, searchtype)
    return _format_result(result)


# ============================================================
# 工具分组字典（供 WebUI SubAgent 编排参考）
# ============================================================

TOOL_GROUPS = {
    "market_analyst": {
        "tools": [
            tool_query_single_quote,
            tool_query_historical_kline,
            tool_query_fund_flow,
            tool_query_market_ranking,
        ],
        "description": (
            "行情数据工具组 —— 分配给市场技术面分析师子智能体。"
            "提供实时行情、历史K线、资金流向、涨跌排名。"
        ),
    },
    "fundamentals_analyst": {
        "tools": [
            tool_query_financials,
            tool_query_single_quote,
        ],
        "description": (
            "财报数据工具组 —— 分配给基本面分析师子智能体。"
            "提供资产负债表、利润表、现金流量表。"
        ),
    },
    "news_analyst": {
        "tools": [
            tool_query_macro_data,
            tool_query_single_quote,
            tool_query_fund_flow,
        ],
        "description": (
            "宏观/新闻工具组 —— 分配给新闻情绪分析师子智能体。"
            "提供宏观经济指标、资金流向判断市场情绪。"
        ),
    },
    "main_agent": {
        "tools": [
            tool_smart_stock_picking,
            tool_query_single_quote,
            tool_query_historical_kline,
            tool_query_fund_flow,
            tool_query_financials,
            tool_query_macro_data,
            tool_query_market_ranking,
        ],
        "description": (
            "主智能体工具组 —— 完整工具集，用于选股和综合协调。"
        ),
    },
    "debate_researcher": {
        "tools": [
            tool_query_single_quote,
            tool_query_historical_kline,
            tool_query_fund_flow,
        ],
        "description": (
            "多空研究员工具组 —— 行情数据，用于支撑多空论点。"
        ),
    },
}

# 所有工具的扁平列表（供 AstrBot 框架发现）
ALL_TOOLS = [
    tool_query_single_quote,
    tool_query_historical_kline,
    tool_query_fund_flow,
    tool_query_market_ranking,
    tool_query_financials,
    tool_query_macro_data,
    tool_smart_stock_picking,
]
