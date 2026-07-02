"""国信证券行情数据 API —— 6 个端点。

仿照参考项目 gs-stock-market-query/scripts/get_data.py。
提供: 单股实时行情、多股行情、历史K线、资金流向、涨跌排名、关联板块。
"""
from typing import Dict, Any, List, Optional
from .http_client import make_request, DEFAULT_BASE_URL

# ============================================================
# 市场代码映射（来自参考项目）
# ============================================================
SET_CODE_MAP = {
    "深圳": 0, "上海": 1, "北交所": 2, "港股": -1, "美股": 74,
}

SET_DOMAIN_MAP = {
    "上证A股": 0, "深证A股": 2, "北交所": 14515,
    "沪深A股": 6, "创业板": 14, "沪深ETF基金": 11005,
}

# A 股市值前缀（判断上海/深圳/北京）
SH_PREFIXES = (
    '600', '601', '602', '603', '605',
    '688', '689',
    '510', '511', '512', '513', '514', '515', '516', '517', '518', '519',
    '900',
)

SZ_PREFIXES = (
    '000', '001', '002', '003', '004',
    '300', '301',
    '159',
    '200',
)

BJ_PREFIXES = ('8', '4')


def get_set_code(ticker: str, market: str) -> int:
    """根据股票代码和市场判断国信 setCode。

    Args:
        ticker: 标准化代码（如 "600519", "000001.SZ", "0700.HK", "AAPL"）
        market: "CN" | "HK" | "US"

    Returns:
        0=深圳, 1=上海, 2=北交所, -1=港股, 74=美股
    """
    if market == "HK":
        return -1
    if market == "US":
        return 74
    code = ticker.replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if any(code.startswith(p) for p in SH_PREFIXES):
        return 1
    if any(code.startswith(p) for p in BJ_PREFIXES):
        return 2
    return 0


def query_single_quote(code: str, set_code: int = 0, target: int = 0) -> Dict[str, Any]:
    """查询单只证券实时行情。

    Args:
        code: 证券代码（如 600519）
        set_code: 市场代码 0=深圳, 1=上海, 2=北交所, -1=港股, 74=美股
        target: 0=沪深京(默认), 3=港股美股

    Returns:
        {"result": [{"code": 0, "msg": "请求成功"}], "data": {...}}
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryHQInfo/1.0"
    params = {"code": code, "setCode": set_code, "target": target}
    return make_request(url, params)


def query_combined_quotes(codes: List[str], set_codes: List[int],
                          target: int = 0) -> Dict[str, Any]:
    """查询多只证券实时行情。

    Args:
        codes: 证券代码列表
        set_codes: 市场代码列表（与 codes 一一对应）
        target: 0=沪深京(默认), 3=港股美股
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryCombHQ/1.0"
    params = {
        "code": ",".join(codes),
        "setCode": ",".join(str(sc) for sc in set_codes),
        "target": target,
    }
    return make_request(url, params)


def query_fund_flow(code: str, set_code: int, period: int = 60) -> Dict[str, Any]:
    """查询资金流向（最大60日）。

    Args:
        code: 证券代码
        set_code: 市场代码
        period: 周期（日），最多60
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryFundFlow/1.0"
    params = {
        "code": code,
        "setCode": str(set_code),
        "period": str(period),
    }
    return make_request(url, params)


def query_market_ranking(set_domain: int, want_num: int = 10,
                         sort_type: int = 1, target: int = 0) -> Dict[str, Any]:
    """查询涨跌排名。

    Args:
        set_domain: 0=上证A股, 2=深证A股, 6=沪深A股, 14=创业板, 14515=北交所, 11005=ETF
        want_num: 返回数量（最多80）
        sort_type: 1=涨幅(默认), 2=跌幅
        target: 0=沪深(默认), 3=港股美股
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryMultiHQ/1.0"
    params = {
        "setDomain": set_domain,
        "wantNum": want_num,
        "sortType": sort_type,
        "target": target,
    }
    return make_request(url, params)


def query_related_sectors(code: str, set_code: int, target: int = 0) -> Dict[str, Any]:
    """查询个股关联板块/概念。

    Args:
        code: 证券代码
        set_code: 市场代码
        target: 0=沪深京(默认), 3=港股美股
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryRelatedCombHQ/1.0"
    params = {"code": code, "setCode": set_code, "target": target}
    return make_request(url, params)


def query_historical_kline(code: str, set_code: int, want_nums: int = 60,
                           target: int = 0, mas: Optional[str] = None) -> Dict[str, Any]:
    """查询近 n 个交易日 K 线数据。

    Args:
        code: 证券代码
        set_code: 市场代码
        want_nums: 近 n 个交易日（默认60）
        target: 0=沪深京(默认), 3=港股美股
        mas: MA 均线周期（如 "5,10,20,60"），可选
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/market/agentbot/queryPastHQInfo/1.0"
    params = {
        "code": code,
        "setCode": str(set_code),
        "wantNums": str(want_nums),
        "target": target,
    }
    if mas:
        params["mas"] = mas
    return make_request(url, params)
