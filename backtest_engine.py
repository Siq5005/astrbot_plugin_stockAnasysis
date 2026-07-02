"""历史回测引擎 —— 基于国信日K线数据模拟交易。

策略：MACD金叉/死叉、均线交叉、RSI超买超卖、KDJ金叉/死叉
模拟：每笔交易使用可用资金的80%（可配），买入全仓、卖出清零
"""
from __future__ import annotations
from typing import Any, Callable

try:
    from .signal_calculator import _safe_float, _ema, _sma
except ImportError:
    from signal_calculator import _safe_float, _ema, _sma


# ---- 策略函数签名: (kline_data: list[dict]) -> list[int] ----
# 返回与 kline_data 等长的信号数组: 1=买入, -1=卖出, 0=不动


def strategy_macd_cross(data: list[dict]) -> list[int]:
    """MACD 金叉买入、死叉卖出。"""
    n = len(data)
    if n < 26:
        return [0] * n
    closes = [_safe_float(d["close"]) for d in data]
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif = [ema12[i] - ema26[i] for i in range(n)]
    dea = _ema(dif, 9)

    signals = [0] * n
    for i in range(1, n):
        if dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
            signals[i] = 1
        elif dif[i] < dea[i] and dif[i - 1] >= dea[i - 1]:
            signals[i] = -1
    return signals


def strategy_ma_cross(data: list[dict]) -> list[int]:
    """MA5 上穿 MA20 买入、下穿卖出。"""
    n = len(data)
    signals = [0] * n
    for i in range(1, n):
        ma5_now = _safe_float(data[i].get("ma5", 0))
        ma20_now = _safe_float(data[i].get("ma20", 0))
        ma5_prev = _safe_float(data[i - 1].get("ma5", 0))
        ma20_prev = _safe_float(data[i - 1].get("ma20", 0))
        if ma5_now and ma20_now:
            if ma5_now > ma20_now and ma5_prev <= ma20_prev:
                signals[i] = 1
            elif ma5_now < ma20_now and ma5_prev >= ma20_prev:
                signals[i] = -1
    return signals


def strategy_rsi(data: list[dict]) -> list[int]:
    """RSI(14) < 30 超卖买入、> 70 超买卖出。"""
    n = len(data)
    if n < 14:
        return [0] * n
    closes = [_safe_float(d["close"]) for d in data]
    gains, losses = [], []
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(-diff if diff < 0 else 0)

    rsi = [50.0] * (14 + 1)
    avg_gain = sum(gains[:14]) / 14
    avg_loss = sum(losses[:14]) / 14
    for i in range(14, len(gains)):
        avg_gain = (avg_gain * 13 + gains[i]) / 14
        avg_loss = (avg_loss * 13 + losses[i]) / 14
        rsi.append(100 - 100 / (1 + avg_gain / avg_loss) if avg_loss > 0 else 100)

    signals = [0] * n
    for i in range(1, n):
        if i < len(rsi):
            if rsi[i] < 30 and rsi[i - 1] >= 30:
                signals[i] = 1
            elif rsi[i] > 70 and rsi[i - 1] <= 70:
                signals[i] = -1
    return signals


def strategy_kdj_cross(data: list[dict]) -> list[int]:
    """KDJ K线上穿D线买入、下穿卖出。"""
    n = len(data)
    if n < 9:
        return [0] * n
    closes = [_safe_float(d["close"]) for d in data]
    highs = [_safe_float(d.get("max", d["close"])) for d in data]
    lows = [_safe_float(d.get("min", d["close"])) for d in data]

    rsv = []
    for i in range(n):
        hh = max(highs[max(0, i - 8): i + 1])
        ll = min(lows[max(0, i - 8): i + 1])
        rsv.append((closes[i] - ll) / (hh - ll) * 100 if hh > ll else 50.0)

    k_vals = _sma(rsv, 3, 1)
    d_vals = _sma(k_vals, 3, 1)

    signals = [0] * n
    for i in range(1, n):
        if k_vals[i] > d_vals[i] and k_vals[i - 1] <= d_vals[i - 1]:
            signals[i] = 1
        elif k_vals[i] < d_vals[i] and k_vals[i - 1] >= d_vals[i - 1]:
            signals[i] = -1
    return signals


STRATEGIES = {
    "macd": ("MACD金叉死叉", strategy_macd_cross),
    "ma": ("MA5上穿MA20", strategy_ma_cross),
    "rsi": ("RSI超买超卖", strategy_rsi),
    "kdj": ("KDJ金叉死叉", strategy_kdj_cross),
}


def run_backtest(kline_json: dict, strategy_name: str = "macd",
                 capital: float = 100000, position_pct: float = 0.8) -> dict:
    """执行回测。

    Args:
        kline_json: query_historical_kline() 返回值
        strategy_name: macd / ma / rsi / kdj
        capital: 初始资金
        position_pct: 每次买入使用资金比例

    Returns:
        {
            "total_return": 0.0842,   # 收益率
            "final_capital": 108420,
            "trades": [...],
            "win_rate": 0.63,
            "max_drawdown": -0.052,
            "buy_hold_return": 0.03,  # 买入持有策略收益率（对比用）
        }
    """
    items = kline_json.get("object", {}).get("dailyHQList", [])
    if not items or len(items) < 26:
        return {"error": f"数据不足，需要≥26个交易日，当前{len(items)}条"}

    strategy = STRATEGIES.get(strategy_name)
    if not strategy:
        return {"error": f"未知策略: {strategy_name}，可选: {list(STRATEGIES.keys())}"}

    signals = strategy[1](items)

    cash = capital
    shares = 0
    trades = []
    peak = capital
    max_dd = 0.0

    first_close = _safe_float(items[0]["close"])
    last_close = _safe_float(items[-1]["close"])
    buy_hold_shares = int(capital * 0.95 / first_close) if first_close > 0 else 0
    buy_hold_return = (buy_hold_shares * last_close - capital) / capital if first_close > 0 else 0

    for i, signal in enumerate(signals):
        price = _safe_float(items[i]["close"])
        if price <= 0:
            continue

        if signal == 1 and shares == 0:
            # 买入
            amt = cash * position_pct
            shares = int(amt / price)
            if shares > 0:
                cash -= shares * price
                trades.append({"date": items[i]["date"], "action": "买入",
                               "price": price, "shares": shares,
                               "cost": shares * price, "cash": cash})

        elif signal == -1 and shares > 0:
            # 卖出
            cash += shares * price
            trades.append({"date": items[i]["date"], "action": "卖出",
                           "price": price, "shares": shares,
                           "revenue": shares * price, "cash": cash})
            shares = 0

        # 跟踪最大回撤
        equity = cash + shares * price
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd

    # 平仓
    if shares > 0:
        cash += shares * last_close
        trades.append({"date": items[-1]["date"], "action": "平仓",
                       "price": last_close, "shares": shares,
                       "revenue": shares * last_close, "cash": cash})

    wins = 0
    for j in range(0, len(trades) - 1, 2):
        if j + 1 < len(trades):
            buy_trade = trades[j]
            sell_trade = trades[j + 1]
            if buy_trade["action"] == "买入" and sell_trade["action"] in ("卖出", "平仓"):
                buy_cost = buy_trade.get("cost", 0)
                sell_rev = sell_trade.get("revenue", 0)
                if sell_rev > buy_cost:
                    wins += 1

    completed_pairs = len([t for t in trades if t["action"] == "卖出" or t["action"] == "平仓"])
    win_rate = wins / max(completed_pairs, 1)

    total_return = (cash - capital) / capital

    return {
        "total_return": round(total_return, 4),
        "final_capital": round(cash, 2),
        "trades": trades,
        "win_rate": round(win_rate, 4),
        "max_drawdown": round(max_dd, 4),
        "buy_hold_return": round(buy_hold_return, 4),
        "strategy": strategy[0],
        "initial_capital": capital,
    }


def format_backtest(ticker: str, stock_name: str, result: dict) -> str:
    """格式化回测结果。"""
    if result.get("error"):
        return f"📊 {stock_name}（{ticker}）回测\n\n❌ {result['error']}"

    trades = result["trades"]
    ret = result["total_return"]
    color = "📈" if ret > 0 else "📉"

    msg = (
        f"📊 {stock_name}（{ticker}）回测结果\n"
        f"策略: {result['strategy']}\n\n"
        f"初始资金: {result['initial_capital']:,.0f}\n"
        f"最终资金: {result['final_capital']:,.0f}\n"
        f"收益率:   {color} {ret:+.2%}\n"
        f"胜率:     {result['win_rate']:.0%}\n"
        f"最大回撤: {result['max_drawdown']:+.2%}\n"
        f"买入持有: {result['buy_hold_return']:+.2%}（同期对比）\n\n"
    )

    if trades:
        msg += f"交易记录（{len(trades)}笔）:\n"
        for t in trades[:10]:
            if t["action"] == "买入":
                msg += f"  {t['date']} 买入 {t['shares']}股 @ {t['price']:.2f}\n"
            elif t["action"] in ("卖出", "平仓"):
                rev = t.get("revenue", 0)
                msg += f"  {t['date']} {t['action']} {t['shares']}股 @ {t['price']:.2f} 收入{rev:,.0f}\n"
        if len(trades) > 10:
            msg += f"  ... 共{len(trades)}笔\n"

    msg += "\n⚠ 回测基于历史数据，不代表未来收益。"
    return msg
