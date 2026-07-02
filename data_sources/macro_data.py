"""国信证券宏观经济数据 API —— 自然语言查询。

仿照参考项目 gs-economy-query/scripts/get_data.py。
支持: GDP, CPI, PPI, M2, LPR, PMI, 汇率, 商品期货等全球宏观经济指标。
"""
from typing import Dict, Any
from .http_client import make_request, DEFAULT_BASE_URL


def query_macro_data(query: str) -> Dict[str, Any]:
    """自然语言查询宏观经济数据。

    Args:
        query: 中文自然语言查询字符串。
               例如: "中国近五年GDP同比增速", "美国最新CPI数据", "COMEX黄金近三个月走势"

    Returns:
        {"content": "markdown 格式的经济数据...", "error": None}  或
        {"content": "", "error": "错误信息"}
    """
    url = f"{DEFAULT_BASE_URL}/agent/adapter/query"
    params = {"text": query}
    result = make_request(url, params)

    # 处理错误情况
    if "error" in result:
        return {"content": "", "error": result["error"]}

    # 处理 STREAM_MESSAGE 响应格式（与参考项目保持一致）
    try:
        if (result.get("result", [{}])[0].get("code") == 0
                and "data" in result):
            contents = []
            for item in result["data"]:
                if isinstance(item, dict) and item.get("type") == "STREAM_MESSAGE":
                    contents.append(item.get("content", ""))
            return {"content": "\n".join(contents), "error": None}
        else:
            msg = result.get("result", [{}])[0].get("msg", "未知错误")
            return {"content": "", "error": msg}
    except Exception as e:
        return {"content": "", "error": str(e)}
