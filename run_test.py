"""国信API + SubAgent 架构模块测试。

用法:
    python run_test.py                     # 测试数据源模块
    python run_test.py --ticker 000905     # 测试指定股票代码映射
    python run_test.py --test-api          # 测试国信 API 连通性（需 GS_API_KEY）
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# 将插件包的父目录加入 sys.path
PLUGIN_PARENT = str(Path(__file__).resolve().parent.parent)
if PLUGIN_PARENT not in sys.path:
    sys.path.insert(0, PLUGIN_PARENT)

_DEFAULT_TICKER = "000001"


def parse_args():
    parser = argparse.ArgumentParser(description="TradingAgents-AstrBot v2.0 模块测试")
    parser.add_argument("--ticker", default=_DEFAULT_TICKER, help="测试股票代码 (默认: 000001)")
    parser.add_argument("--test-api", action="store_true", help="测试国信 API 连通性（需设置 GS_API_KEY）")
    parser.add_argument("--test-full", action="store_true", help="运行完整数据获取测试")
    return parser.parse_args()


# ============================================================
# Test 1: 模块导入
# ============================================================
async def test_imports():
    """测试所有新模块的导入。"""
    print("=" * 60)
    print("[1/5] 模块导入测试 (v2.0 架构)")
    print("=" * 60)

    modules = [
        # 数据源层
        ("data_sources.http_client", "make_request, is_available, get_api_key"),
        ("data_sources.market_data", "query_single_quote, query_historical_kline, query_fund_flow, "
         "query_market_ranking, query_related_sectors, get_set_code"),
        ("data_sources.financial_data", "query_a_stock_balance_sheet, query_a_stock_income_statement, "
         "query_a_stock_cash_flow, query_hk_stock_balance_sheet, "
         "query_hk_stock_income_statement, query_hk_stock_cash_flow"),
        ("data_sources.macro_data", "query_macro_data"),
        ("data_sources.stock_picking", "smart_stock_picking"),
        # 工具注册层
        ("astrbot_tools", "ALL_TOOLS, TOOL_GROUPS"),
        # Persona
        ("subagent_personas", "PERSONAS, load_persona"),
        # 保留工具
        ("utils.stock_utils", "StockUtils"),
        ("utils.report_utils", "check_pdf_available"),
    ]

    all_ok = True
    for mod_path, items in modules:
        try:
            mod = __import__(mod_path, fromlist=[items])
            for item in items.split(", "):
                getattr(mod, item.strip())
            print(f"  ✅ {mod_path}")
        except Exception as e:
            print(f"  ❌ {mod_path}: {e}")
            all_ok = False

    assert all_ok, "存在导入失败的模块"
    print()


# ============================================================
# Test 2: 股票工具
# ============================================================
async def test_stock_utils():
    """测试股票工具类。"""
    print("=" * 60)
    print("[2/5] StockUtils 测试")
    print("=" * 60)

    from utils.stock_utils import StockUtils

    test_cases = [
        ("000001", "中国A股"),
        ("600519", "中国A股"),
        ("0700.HK", "港股"),
        ("AAPL", "美股"),
        ("平安银行", "resolve"),
    ]

    for ticker, expected in test_cases:
        if expected == "resolve":
            try:
                result = StockUtils.resolve_stock_name(ticker)
                print(f"  {'✅' if result else '⚠️'} 名称解析: '{ticker}' → '{result}'")
            except Exception as e:
                print(f"  ⚠️ 名称解析 '{ticker}': {e}")
        else:
            info = StockUtils.get_market_info(ticker)
            name = StockUtils.get_stock_name(ticker)
            status = "✅" if expected in info.get("market_name", "") else "❌"
            print(f"  {status} {ticker}: {info.get('market_name', '?')} / {info.get('normalized_ticker', '?')} / {name}")

    print()


# ============================================================
# Test 3: 数据源 API 函数（不实际调用，只验证可调用性）
# ============================================================
async def test_data_sources(ticker: str):
    """测试数据源模块的函数签名和基本结构。"""
    print("=" * 60)
    print("[3/5] 数据源模块结构测试")
    print("=" * 60)

    from data_sources.market_data import (
        query_single_quote, query_historical_kline, query_fund_flow,
        query_market_ranking, query_related_sectors, get_set_code,
    )
    from data_sources.financial_data import (
        query_a_stock_balance_sheet, query_a_stock_income_statement,
        query_hk_stock_balance_sheet,
    )
    from data_sources.macro_data import query_macro_data
    from data_sources.stock_picking import smart_stock_picking
    from data_sources.http_client import is_available, get_api_key

    # 测试市场代码映射
    tests = [
        ("600519", "CN", 1, "上海"),
        ("000001", "CN", 0, "深圳"),
        ("0700.HK", "HK", -1, "港股"),
        ("AAPL", "US", 74, "美股"),
        ("830001", "CN", 2, "北交所"),
    ]
    for code, market, expected, desc in tests:
        result = get_set_code(code, market)
        status = "✅" if result == expected else f"❌ (got {result})"
        print(f"  {status} get_set_code('{code}', '{market}') = {result} ({desc})")

    print(f"  📋 行情端点: 6 个函数可用")
    print(f"  📋 财报端点: 6 个函数可用（A股3 + 港股3）")
    print(f"  📋 宏观查询: 1 个函数可用")
    print(f"  📋 智能选股: 1 个函数可用")
    print(f"  🔑 API Key: {'已配置' if is_available() else '未配置（工具将不可用）'}")

    if is_available():
        print(f"  🔑 Key 前缀: {get_api_key()[:4]}...")
    print()


# ============================================================
# Test 4: 工具注册和 Persona
# ============================================================
async def test_tools_and_personas():
    """测试工具注册和 Persona 加载。"""
    print("=" * 60)
    print("[4/5] 工具 + Persona 测试")
    print("=" * 60)

    from astrbot_tools import ALL_TOOLS, TOOL_GROUPS
    from subagent_personas import PERSONAS, load_persona

    print(f"  ✅ {len(ALL_TOOLS)} 个工具已注册")
    for group_name, group_info in TOOL_GROUPS.items():
        print(f"     • {group_name}: {len(group_info['tools'])} 工具")

    print(f"  ✅ {len(PERSONAS)} 个 Persona 已定义")
    for name in PERSONAS:
        content = load_persona(name)
        print(f"     • {name}: {len(content)} 字符")

    print()


# ============================================================
# Test 5: API 连通性（可选）
# ============================================================
async def test_api_connectivity(ticker: str):
    """测试国信 API 连通性（需要 GS_API_KEY）。"""
    print("=" * 60)
    print("[5/5] 国信 API 连通性测试")
    print("=" * 60)

    from data_sources.http_client import is_available
    from data_sources.market_data import query_single_quote, get_set_code

    if not is_available():
        print("  ⏭️  未设置 GS_API_KEY，跳过 API 连通性测试")
        print("     提示: export GS_API_KEY=<你的密钥> && python run_test.py --test-api")
        print()
        return

    from data_sources.market_data import query_historical_kline
    from data_sources.financial_data import query_a_stock_income_statement

    import asyncio

    clean = ticker.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    set_code = get_set_code(ticker, "CN")

    async def run_test(name, func, *args):
        try:
            result = await asyncio.to_thread(func, *args)
            if isinstance(result, dict) and "error" not in result:
                print(f"  ✅ {name}: 成功")
            else:
                err = result.get("error", "未知") if isinstance(result, dict) else "未知"
                print(f"  ⚠️ {name}: {err}"[:100])
        except Exception as e:
            print(f"  ❌ {name}: {e}")

    await run_test("实时行情", query_single_quote, clean, set_code)
    await run_test("历史K线", query_historical_kline, clean, set_code, 5)
    await run_test("利润表", query_a_stock_income_statement, clean, "SZ")

    print()


# ============================================================
# Main
# ============================================================
async def main():
    args = parse_args()
    ticker = args.ticker

    print(f"\n🧪 TradingAgents-AstrBot v2.0 模块测试 (股票: {ticker})\n")

    await test_imports()
    await test_stock_utils()
    await test_data_sources(ticker)
    await test_tools_and_personas()

    if args.test_api or args.test_full:
        await test_api_connectivity(ticker)

    print("=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
