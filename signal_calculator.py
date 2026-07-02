"""技术信号评分 —— 纯数学计算，零 LLM 消耗。

基于国信 K 线 JSON 数据（dailyHQList），计算 MACD/KDJ/RSI/均线/量能五项指标，
各赋予加权分数，汇总为 0-100 的综合评分。
"""
from __future__ import annotations
from typing import Any


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _ema(data: list[float], period: int) -> list[float]:
    """指数移动平均。"""
    if len(data) < period:
        return [0.0] * len(data)
    k = 2.0 / (period + 1)
    result = [0.0] * len(data)
    result[period - 1] = sum(data[:period]) / period
    for i in range(period, len(data)):
        result[i] = data[i] * k + result[i - 1] * (1 - k)
    return result


def _sma(data: list[float], n: int, m: int = 1) -> list[float]:
    """简单移动平均（KDJ 用的加权 SMA）。"""
    result = [0.0] * len(data)
    if len(data) < n:
        return result
    result[n - 1] = sum(data[:n]) / n
    for i in range(n, len(data)):
        result[i] = (data[i] * m + result[i - 1] * (n - m)) / n
    return result


def calc_score(kline_json: dict) -> dict:
    """基于国信 K 线 API 响应计算技术信号评分。

    Args:
        kline_json: query_historical_kline() 返回值（完整 JSON）

    Returns:
        {
            "total": 62,           # 0-100 总分
            "level": "中性偏多",    # 极空/偏空/中性/偏多/极多
            "signal": "持有",       # 买入/持有/卖出
            "macd":   {"score": 20, "detail": "DIF>DEA，趋势向上"},
            "ma":     {"score": 15, "detail": "MA5上穿MA10但MA20压制"},
            "kdj":    {"score": 10, "detail": "K=58，中性区间"},
            "rsi":    {"score": 12, "detail": "RSI=42，接近超卖"},
            "volume": {"score": 5,  "detail": "量能与5日均量持平"},
        }
    """
    items = kline_json.get("object", {}).get("dailyHQList", [])
    if not items or len(items) < 26:
        return {"total": 0, "level": "数据不足", "signal": "无法判断",
                "error": f"需要至少26个交易日数据，当前{len(items)}条"}

    # 提取数据
    closes = [_safe_float(d["close"]) for d in items]
    highs = [_safe_float(d.get("max", d["close"])) for d in items]
    lows = [_safe_float(d.get("min", d["close"])) for d in items]
    opens = [_safe_float(d.get("open", d["close"])) for d in items]
    vols = []
    for d in items:
        v = str(d.get("vol", "0"))
        multi = 1.0
        if "亿" in v:
            multi = 100000000
            v = v.replace("亿", "")
        elif "万" in v:
            multi = 10000
            v = v.replace("万", "")
        vols.append(_safe_float(v.replace(",", "")) * multi)

    n = len(closes)
    last = closes[-1]

    # ---- MACD (30分) ----
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif = [ema12[i] - ema26[i] for i in range(n)]
    dea = _ema(dif, 9)
    macd_bar = [(dif[i] - dea[i]) * 2 for i in range(n)]

    dif_now, dea_now = dif[-1], dea[-1]
    dif_prev, dea_prev = dif[-2], dea[-2]
    macd_score = 0
    macd_detail = ""

    if dif_now > dea_now:
        if dif_prev <= dea_prev:
            macd_score = 30
            macd_detail = "MACD金叉，信号强烈看多"
        elif dif_now > dif_prev:
            macd_score = 25
            macd_detail = "DIF>DEA且柱线增长，趋势向好"
        else:
            macd_score = 20
            macd_detail = "DIF>DEA，趋势向上但柱线缩短"
    else:
        if dif_prev >= dea_prev:
            macd_score = 0
            macd_detail = "MACD死叉，信号看空"
        elif dif_now < dif_prev:
            macd_score = 5
            macd_detail = "DIF<DEA且持续下行"
        else:
            macd_score = 10
            macd_detail = "DIF在DEA下方但柱线收窄"

    # ---- 均线 (25分) ----
    ma5_now = _safe_float(items[-1].get("ma5", 0))
    ma10_now = _safe_float(items[-1].get("ma10", 0))
    ma20_now = _safe_float(items[-1].get("ma20", 0))
    ma60_now = _safe_float(items[-1].get("ma60", 0))

    ma_score, ma_detail = 0, ""
    if ma5_now and ma10_now and ma20_now and ma60_now:
        if ma5_now > ma10_now > ma20_now > ma60_now:
            ma_score, ma_detail = 25, "多头排列（MA5>MA10>MA20>MA60）"
        elif last > ma5_now and last > ma10_now:
            if ma5_now > ma10_now:
                ma_score, ma_detail = 20, "短中期均线向上，股价在均线上方"
            else:
                ma_score, ma_detail = 15, "股价在均线上方，等待MA5上穿MA10"
        elif last > ma60_now and ma5_now < ma10_now:
            ma_score, ma_detail = 10, "长期均线支撑，短期均线走平"
        elif last < ma60_now:
            if ma5_now < ma10_now:
                ma_score, ma_detail = 0, "空头排列，股价在所有均线下方"
            else:
                ma_score, ma_detail = 5, "短期反弹但长期均线压制"
        else:
            ma_score, ma_detail = 8, "均线交织，方向不明"
    else:
        ma_score, ma_detail = 12, "均线数据不完整，降权评分"

    # ---- KDJ (20分) ----
    rsv_list: list[float] = []
    for i in range(n):
        hh = max(highs[max(0, i - 8): i + 1])
        ll = min(lows[max(0, i - 8): i + 1])
        rsv = ((closes[i] - ll) / (hh - ll) * 100) if hh > ll else 50.0
        rsv_list.append(rsv)

    k_vals = _sma(rsv_list, 3, 1)
    d_vals = _sma(k_vals, 3, 1)
    j_vals = [3 * k_vals[i] - 2 * d_vals[i] for i in range(n)]

    k_now, d_now, j_now = k_vals[-1], d_vals[-1], j_vals[-1]
    k_prev, d_prev = k_vals[-2], d_vals[-2]

    kdj_score, kdj_detail = 0, ""
    if k_now > d_now:
        if k_prev <= d_prev:
            kdj_score, kdj_detail = 20, "KDJ金叉，超卖反弹信号"
        elif k_now < 20:
            kdj_score, kdj_detail = 18, f"K={k_now:.0f}，超卖区，反弹概率大"
        elif k_now > 80:
            kdj_score, kdj_detail = 5, f"K={k_now:.0f}，超买区，注意回调"
        elif k_now > 50:
            kdj_score, kdj_detail = 12, f"K={k_now:.0f}，多方占优"
        else:
            kdj_score, kdj_detail = 10, f"K={k_now:.0f}，中性偏弱"
    else:
        if k_prev >= d_prev:
            kdj_score, kdj_detail = 0, "KDJ死叉，看空信号"
        elif k_now > 80:
            kdj_score, kdj_detail = 3, f"K={k_now:.0f}，超买死叉，风险较高"
        else:
            kdj_score, kdj_detail = 5, f"K={k_now:.0f}，弱势区间"

    # ---- RSI (15分) ----
    rsi_period = 14
    gains, losses = [], []
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(-diff if diff < 0 else 0)

    avg_gain = sum(gains[:rsi_period]) / rsi_period
    avg_loss = sum(losses[:rsi_period]) / rsi_period

    rsi_list = [0.0] * (rsi_period + 1)
    for i in range(rsi_period, len(gains)):
        avg_gain = (avg_gain * (rsi_period - 1) + gains[i]) / rsi_period
        avg_loss = (avg_loss * (rsi_period - 1) + losses[i]) / rsi_period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi_list.append(100 - 100 / (1 + rs))

    rsi_now = rsi_list[-1] if rsi_list else 50

    rsi_score, rsi_detail = 0, ""
    if rsi_now < 25:
        rsi_score, rsi_detail = 15, f"RSI={rsi_now:.0f}，严重超卖，反弹概率大"
    elif rsi_now < 35:
        rsi_score, rsi_detail = 12, f"RSI={rsi_now:.0f}，超卖区，可关注买入"
    elif 35 <= rsi_now <= 65:
        rsi_score, rsi_detail = 10, f"RSI={rsi_now:.0f}，中性区间"
    elif rsi_now < 75:
        rsi_score, rsi_detail = 6, f"RSI={rsi_now:.0f}，偏强但未超买"
    elif rsi_now < 85:
        rsi_score, rsi_detail = 3, f"RSI={rsi_now:.0f}，超买区，谨慎追高"
    else:
        rsi_score, rsi_detail = 0, f"RSI={rsi_now:.0f}，严重超买，回调风险高"

    # ---- 量能 (10分) ----
    vol_now = vols[-1]
    vol_ma5 = sum(vols[-6:-1]) / 5 if n >= 6 else vol_now

    vol_score, vol_detail = 0, ""
    vol_ratio = vol_now / vol_ma5 if vol_ma5 > 0 else 1
    price_up = closes[-1] > closes[-2] if n >= 2 else False

    if vol_ratio > 2.0 and price_up:
        vol_score, vol_detail = 10, f"放量上涨（量比{vol_ratio:.1f}x），强势信号"
    elif vol_ratio > 1.5 and price_up:
        vol_score, vol_detail = 8, f"温和放量上涨（量比{vol_ratio:.1f}x）"
    elif vol_ratio > 1.5 and not price_up:
        vol_score, vol_detail = 2, f"放量下跌（量比{vol_ratio:.1f}x），注意风险"
    elif 0.8 <= vol_ratio <= 1.2:
        vol_score, vol_detail = 5, f"量能与5日均量持平（量比{vol_ratio:.1f}x）"
    elif vol_ratio < 0.5:
        vol_score, vol_detail = 3, f"严重缩量（量比{vol_ratio:.1f}x），观望"
    else:
        vol_score, vol_detail = 5, f"量比{vol_ratio:.1f}x"

    # ---- 综合 ----
    total = macd_score + ma_score + kdj_score + rsi_score + vol_score

    if total >= 80:
        level, signal = "极多 🟢", "强烈买入"
    elif total >= 65:
        level, signal = "偏多", "买入"
    elif total >= 45:
        level, signal = "中性", "持有观望"
    elif total >= 30:
        level, signal = "偏空", "卖出"
    else:
        level, signal = "极空 🔴", "强烈卖出"

    return {
        "total": total,
        "level": level,
        "signal": signal,
        "macd":   {"score": macd_score, "detail": macd_detail},
        "ma":     {"score": ma_score, "detail": ma_detail},
        "kdj":    {"score": kdj_score, "detail": kdj_detail},
        "rsi":    {"score": rsi_score, "detail": rsi_detail},
        "volume": {"score": vol_score, "detail": vol_detail},
    }


def format_signal(ticker: str, stock_name: str, result: dict) -> str:
    """将评分结果格式化为可读文本。"""
    if result.get("error"):
        return f"📊 {stock_name}（{ticker}）信号评分\n\n❌ {result['error']}"

    return (
        f"📊 {stock_name}（{ticker}）技术信号评分\n\n"
        f"总分: {result['total']}/100 {result['level']}\n"
        f"建议: {result['signal']}\n\n"
        f"MACD:   {result['macd']['score']:>2}/30  {result['macd']['detail']}\n"
        f"均线:   {result['ma']['score']:>2}/25  {result['ma']['detail']}\n"
        f"KDJ:    {result['kdj']['score']:>2}/20  {result['kdj']['detail']}\n"
        f"RSI:    {result['rsi']['score']:>2}/15  {result['rsi']['detail']}\n"
        f"量能:   {result['volume']['score']:>2}/10  {result['volume']['detail']}\n\n"
        f"⚠ 技术信号仅反映市场走势，不构成投资建议。"
    )
