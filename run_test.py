"""插件模块导入和功能测试（使用相对导入）。

用法:
    python run_test.py                     # 默认测试 AAPL
    python run_test.py --ticker 000905     # 测试指定股票
    python run_test.py --ticker 000905 --output report.md  # 指定输出文件名
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# 将插件包的父目录加入 sys.path，使 Python 可以将当前目录识别为一个包
PLUGIN_PARENT = str(Path(__file__).resolve().parent.parent)
if PLUGIN_PARENT not in sys.path:
    sys.path.insert(0, PLUGIN_PARENT)

# 默认 API 配置 — 从环境变量读取，请勿在代码中硬编码密钥
_DEFAULT_API_KEY = os.environ.get("TRADING_ASSISTANT_API_KEY", "")
_DEFAULT_API_BASE = os.environ.get("TRADING_ASSISTANT_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
_DEFAULT_MODEL = os.environ.get("TRADING_ASSISTANT_MODEL", "glm-4-flash")
_DEFAULT_TICKER = "AAPL"


def parse_args():
    parser = argparse.ArgumentParser(description="AstrBot 金融助手插件测试")
    parser.add_argument("--ticker", default=_DEFAULT_TICKER, help="测试股票代码 (默认: AAPL)")
    parser.add_argument("--output", default=None, help="报告输出文件名 (默认: test_report_{TICKER}.md)")
    return parser.parse_args()


def setup_env():
    """设置 API 环境变量"""
    os.environ.setdefault("TRADING_ASSISTANT_API_KEY", _DEFAULT_API_KEY)
    os.environ.setdefault("TRADING_ASSISTANT_API_BASE", _DEFAULT_API_BASE)
    os.environ.setdefault("TRADING_ASSISTANT_MODEL", _DEFAULT_MODEL)
    os.environ.setdefault("TRADING_ASSISTANT_REASONING", "true")


def build_llm():
    from astrbot_plugin_tradingassistant.llm_client import OpenAICompatibleLLM
    reasoning = os.environ.get("TRADING_ASSISTANT_REASONING", "true").lower() in {"1", "true", "yes", "on"}
    return OpenAICompatibleLLM(
        api_key=os.environ["TRADING_ASSISTANT_API_KEY"],
        api_base=os.environ["TRADING_ASSISTANT_API_BASE"],
        model=os.environ["TRADING_ASSISTANT_MODEL"],
        reasoning=reasoning,
        max_tokens=4000,
        timeout_seconds=120,
    )


async def test_imports():
    """测试所有模块的相对导入"""
    print("=" * 60)
    print("[1/5] 模块导入测试")
    print("=" * 60)

    modules = [
        ("astrbot_plugin_tradingassistant.utils.stock_utils", "StockUtils"),
        ("astrbot_plugin_tradingassistant.data_fetcher", "DataFetcher"),
        ("astrbot_plugin_tradingassistant.llm_client", "OpenAICompatibleLLM"),
        ("astrbot_plugin_tradingassistant.analysts.base", "BaseAnalyst"),
        ("astrbot_plugin_tradingassistant.analysts.market_analyst", "MarketAnalyst"),
        ("astrbot_plugin_tradingassistant.analysts.fundamentals_analyst", "FundamentalsAnalyst"),
        ("astrbot_plugin_tradingassistant.analysts.news_analyst", "NewsAnalyst"),
        ("astrbot_plugin_tradingassistant.debate.bull_researcher", "BullResearcher"),
        ("astrbot_plugin_tradingassistant.debate.bear_researcher", "BearResearcher"),
        ("astrbot_plugin_tradingassistant.debate.research_manager", "ResearchManager"),
        ("astrbot_plugin_tradingassistant.debate.risk_judge", "RiskJudge"),
        ("astrbot_plugin_tradingassistant.trading_graph_langgraph", "TradingGraphLangGraph"),
    ]

    all_ok = True
    for mod_path, cls_name in modules:
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            print(f"  ✅ {cls_name} ({mod_path})")
        except Exception as e:
            print(f"  ❌ {cls_name} ({mod_path}): {e}")
            all_ok = False

    assert all_ok, "存在导入失败的模块"
    print()


async def test_stock_utils():
    """测试股票工具类"""
    print("=" * 60)
    print("[2/5] StockUtils 测试")
    print("=" * 60)

    from astrbot_plugin_tradingassistant.utils.stock_utils import StockUtils

    test_cases = [
        ("000001", "中国A股"),
        ("0700.HK", "港股"),
        ("AAPL", "美股"),
    ]

    for ticker, expected_market in test_cases:
        info = StockUtils.get_market_info(ticker)
        name = StockUtils.get_stock_name(ticker)
        status = "✅" if expected_market in info["market_name"] else "❌"
        print(f"  {status} {ticker}: {info['market_name']} / {info['normalized_ticker']} / {name}")

    print()


async def test_data_fetcher(ticker: str = "AAPL"):
    """测试数据获取"""
    print("=" * 60)
    print("[3/5] DataFetcher 测试")
    print("=" * 60)

    from astrbot_plugin_tradingassistant.data_fetcher import DataFetcher

    df = DataFetcher()
    trade_date = datetime.now().strftime("%Y-%m-%d")

    # 测试指定股票
    try:
        market = await df.get_market_data(ticker, trade_date)
        print(f"  {'✅' if market and '失败' not in market else '⚠️'} market_data ({ticker}): {len(market)} chars")
    except Exception as e:
        print(f"  ⚠️ market_data: {e}")

    try:
        fund = await df.get_fundamentals(ticker, trade_date)
        print(f"  {'✅' if fund else '⚠️'} fundamentals: {len(fund) if fund else 0} chars")
    except Exception as e:
        print(f"  ⚠️ fundamentals: {e}")

    try:
        news = await df.get_news(ticker, trade_date)
        print(f"  {'✅' if news else '⚠️'} news: {len(news) if news else 0} chars")
    except Exception as e:
        print(f"  ⚠️ news: {e}")

    print()


async def test_llm():
    """测试 LLM 连通性"""
    print("=" * 60)
    print("[4/5] LLM 连通性测试")
    print("=" * 60)

    llm = build_llm()
    try:
        result = await llm.ask("请仅回复 OK")
        ok = "OK" in result.upper()
        print(f"  {'✅' if ok else '⚠️'} LLM 响应: {result[:100]}")
    except Exception as e:
        print(f"  ❌ LLM 调用失败: {e}")

    print()


async def test_full_analysis(ticker: str, output_name: str = None):
    """测试完整的分析流程"""
    from astrbot_plugin_tradingassistant.utils.stock_utils import StockUtils

    display_name = StockUtils.get_stock_name(ticker)
    print("=" * 60)
    print(f"[5/5] 完整分析流程测试 ({ticker} - {display_name})")
    print("=" * 60)

    from astrbot_plugin_tradingassistant.data_fetcher import DataFetcher
    from astrbot_plugin_tradingassistant.trading_graph_langgraph import TradingGraphLangGraph

    llm = build_llm()
    df = DataFetcher()
    graph = TradingGraphLangGraph(llm, df)

    trade_date = datetime.now().strftime("%Y-%m-%d")

    try:
        report = await graph.analyze(ticker, trade_date)
        print(f"  ✅ 分析完成，报告长度: {len(report)} chars")

        # 保存报告
        report_dir = Path(__file__).resolve().parent / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        filename = output_name or f"test_report_{ticker}.md"
        report_file = report_dir / filename
        report_file.write_text(report, encoding="utf-8")
        print(f"  📄 报告已保存: {report_file}")

        # 打印报告摘要
        lines = report.split("\n")
        print("\n  --- 报告前 20 行 ---")
        for line in lines[:20]:
            print(f"  {line}")
        print("  ...")
    except Exception as e:
        print(f"  ❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()

    print()


async def main():
    args = parse_args()
    setup_env()
    ticker = args.ticker

    print(f"\n🧪 AstrBot 金融助手插件 - 完整测试 (股票: {ticker})\n")

    await test_imports()
    await test_stock_utils()
    await test_data_fetcher(ticker)
    await test_llm()
    await test_full_analysis(ticker, args.output)

    print("=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
