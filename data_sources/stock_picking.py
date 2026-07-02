"""国信证券智能选股 API —— 自然语言条件筛选。

仿照参考项目 gs-smart-stock-picking/scripts/gs_stock_picking.py。
支持: 财务指标、技术指标、行业等多维度组合筛选。
"""
from typing import Dict, Any
from .http_client import make_request, DEFAULT_BASE_URL


def smart_stock_picking(searchstring: str, searchtype: str = "stock") -> Dict[str, Any]:
    """自然语言智能选股。

    Args:
        searchstring: 中文自然语言筛选条件。
                      例如: "市盈率小于20的银行股", "MACD金叉且成交量放大的科技股"
        searchtype: 资产类型。
                    stock=A股, fund=基金, HK_stock=港股, US_stock=美股,
                    NEEQ=新三板, index=指数

    Returns:
        {"result": [{"code": 0, "msg": "请求成功"}], "data": {"tables": [...]}}
    """
    url = f"{DEFAULT_BASE_URL}/agent/mcp/smart_stock_picking"
    params = {
        "searchstring": searchstring,
        "searchtype": searchtype,
    }
    return make_request(url, params)
