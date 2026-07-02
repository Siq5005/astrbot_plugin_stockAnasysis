"""国信证券财报数据 API —— A 股 + 港股财务报表。

仿照参考项目 gs-stock-financial-query/scripts/get_data.py。
提供: 资产负债表、利润表、现金流量表（A股/H股各3端点）。
"""
from typing import Dict, Any
from .http_client import make_request, DEFAULT_BASE_URL


def query_a_stock_balance_sheet(code: str, market: str = "SH",
                                report_type: str = "Q0",
                                report_year: str = "",
                                count: str = "1") -> Dict[str, Any]:
    """A 股资产负债表。

    Args:
        code: 股票代码（6位数字）
        market: SH=上海, SZ=深圳
        report_type: Q0=最新, Q4=年报, Q2=中报, Q3=三季报, Q1=一季报
        report_year: 财务年度（如 "2024"），空字符串=不限
        count: 获取期数（默认1期）
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/gsf10/financial/balanceSheet/1.0"
    params = {
        "code": code, "market": market,
        "reportType": report_type, "reportYear": report_year, "count": count,
    }
    return make_request(url, params)


def query_a_stock_income_statement(code: str, market: str = "SH",
                                   report_type: str = "Q0",
                                   report_year: str = "",
                                   count: str = "1") -> Dict[str, Any]:
    """A 股利润表。

    Args:
        code: 股票代码（6位数字）
        market: SH=上海, SZ=深圳
        report_type: Q0=最新, Q4=年报, Q2=中报, Q3=三季报, Q1=一季报
        report_year: 财务年度
        count: 获取期数
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/gsf10/financial/incomeStatement/1.0"
    params = {
        "code": code, "market": market,
        "reportType": report_type, "reportYear": report_year, "count": count,
    }
    return make_request(url, params)


def query_a_stock_cash_flow(code: str, market: str = "SH",
                            report_type: str = "Q0",
                            report_year: str = "",
                            count: str = "1") -> Dict[str, Any]:
    """A 股现金流量表。

    Args:
        code: 股票代码（6位数字）
        market: SH=上海, SZ=深圳
        report_type: Q0=最新, Q4=年报, Q2=中报, Q3=三季报, Q1=一季报
        report_year: 财务年度
        count: 获取期数
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/gsf10/financial/cashFlowStatement/1.0"
    params = {
        "code": code, "market": market,
        "reportType": report_type, "reportYear": report_year, "count": count,
    }
    return make_request(url, params)


def query_hk_stock_balance_sheet(code: str, report_year: str = "",
                                 report_type: str = "",
                                 count: str = "1") -> Dict[str, Any]:
    """港股资产负债表。

    market 固定为 HK。

    Args:
        code: 港股代码（如 "02020"）
        report_year: 报告日期（如 "2021-06-30"）
        report_type: Q1/Q2/Q3/Q4
        count: 获取期数
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/hkf10/financial/balanceSheet/1.0"
    params = {
        "code": code, "market": "HK",
        "reportYear": report_year, "reportType": report_type, "count": count,
    }
    return make_request(url, params)


def query_hk_stock_income_statement(code: str, report_year: str = "",
                                    report_type: str = "",
                                    count: str = "1") -> Dict[str, Any]:
    """港股利润表。

    Args:
        code: 港股代码
        report_year: 报告日期
        report_type: Q1/Q2/Q3/Q4
        count: 获取期数
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/hkf10/financial/incomeStatement/1.0"
    params = {
        "code": code, "market": "HK",
        "reportYear": report_year, "reportType": report_type, "count": count,
    }
    return make_request(url, params)


def query_hk_stock_cash_flow(code: str, report_year: str = "",
                             report_type: str = "",
                             count: str = "1") -> Dict[str, Any]:
    """港股现金流量表。

    Args:
        code: 港股代码
        report_year: 报告日期
        report_type: Q1/Q2/Q3/Q4
        count: 获取期数
    """
    url = f"{DEFAULT_BASE_URL}/gsnews/hkf10/financial/cashFlowStatement/1.0"
    params = {
        "code": code, "market": "HK",
        "reportYear": report_year, "reportType": report_type, "count": count,
    }
    return make_request(url, params)
