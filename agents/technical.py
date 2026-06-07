# -*- coding: utf-8 -*-
"""技术指标计算模块 - 纯Python实现"""

from typing import List, Dict, Any


def compute_ma(closes: List[float], period: int) -> List[float]:
    """计算移动平均线"""
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(round(sum(closes[i - period + 1:i + 1]) / period, 2))
    return result


def compute_rsi(closes: List[float], period: int = 14) -> float:
    """计算RSI (最新值)"""
    if len(closes) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))

    # 使用最后 period 个数据
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]
    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_macd(closes: List[float], fast=12, slow=26, signal=9) -> Dict[str, float]:
    """计算MACD (最新值)"""
    if len(closes) < slow + signal:
        return {"macd": 0, "signal": 0, "histogram": 0}

    def ema(data, period):
        multiplier = 2 / (period + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append((data[i] - result[-1]) * multiplier + result[-1])
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line[slow - 1:], signal)

    macd_val = macd_line[-1]
    signal_val = signal_line[-1] if signal_line else 0
    histogram = macd_val - signal_val

    return {
        "macd": round(macd_val, 4),
        "signal": round(signal_val, 4),
        "histogram": round(histogram, 4),
    }


def compute_bollinger(closes: List[float], period: int = 20, std_mult: float = 2.0) -> Dict[str, float]:
    """计算布林带 (最新值)"""
    if len(closes) < period:
        return {"upper": 0, "middle": 0, "lower": 0}

    recent = closes[-period:]
    middle = sum(recent) / period
    variance = sum((x - middle) ** 2 for x in recent) / period
    std = variance ** 0.5

    return {
        "upper": round(middle + std_mult * std, 2),
        "middle": round(middle, 2),
        "lower": round(middle - std_mult * std, 2),
    }


# ─── 序列版函数（供图表叠加使用）───────────────────────

def compute_rsi_series(closes: List[float], period: int = 14) -> List[float]:
    """计算 RSI 完整序列"""
    result: List[float] = [None] * period  # type: ignore
    if len(closes) < period + 1:
        return result
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    # Wilder smoothing
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(round(100 - 100 / (1 + rs), 2))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(round(100 - 100 / (1 + rs), 2))
    return result


def compute_macd_series(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """计算 MACD 完整序列 → (macd_line, signal_line, histogram)"""
    if len(closes) < slow + signal:
        n = len(closes)
        return [None] * n, [None] * n, [None] * n

    def ema(data, p):
        m = 2 / (p + 1)
        r = [data[0]]
        for i in range(1, len(data)):
            r.append((data[i] - r[-1]) * m + r[-1])
        return r

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line_full = [f - s for f, s in zip(ema_fast, ema_slow)]
    # signal line starts after slow-1
    signal_part = ema(macd_line_full[slow - 1:], signal)
    # align back
    macd_out: List[float] = [None] * (slow - 1)  # type: ignore
    signal_out: List[float] = [None] * (slow - 1)  # type: ignore
    hist_out: List[float] = [None] * (slow - 1)  # type: ignore
    for i, s_val in enumerate(signal_part):
        m_val = macd_line_full[slow - 1 + i]
        macd_out.append(round(m_val, 4))
        signal_out.append(round(s_val, 4))
        hist_out.append(round(m_val - s_val, 4))
    return macd_out, signal_out, hist_out


def compute_bollinger_series(closes: List[float], period: int = 20, std_mult: float = 2.0):
    """计算布林带完整序列 → (upper, middle, lower)"""
    upper: List[float] = [None] * (period - 1)  # type: ignore
    middle: List[float] = [None] * (period - 1)  # type: ignore
    lower: List[float] = [None] * (period - 1)  # type: ignore
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        m = sum(window) / period
        var = sum((x - m) ** 2 for x in window) / period
        std = var ** 0.5
        middle.append(round(m, 2))
        upper.append(round(m + std_mult * std, 2))
        lower.append(round(m - std_mult * std, 2))
    return upper, middle, lower


def compute_all_indicators(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算所有技术指标"""
    if not candles or len(candles) < 5:
        return {"error": "数据不足"}

    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    # 移动平均线
    ma5 = compute_ma(closes, 5)
    ma10 = compute_ma(closes, 10)
    ma20 = compute_ma(closes, 20)
    ma60 = compute_ma(closes, 60)

    # 成交量均线
    vol_ma5 = compute_ma(volumes, 5)
    vol_ma20 = compute_ma(volumes, 20)

    # 当前价格与均线关系
    current_price = closes[-1]
    ma_status = {}
    for name, ma_vals in [("MA5", ma5), ("MA10", ma10), ("MA20", ma20), ("MA60", ma60)]:
        val = ma_vals[-1]
        if val:
            ma_status[name] = {
                "value": val,
                "position": "above" if current_price > val else "below",
                "distance_pct": round((current_price - val) / val * 100, 2),
            }

    # RSI
    rsi = compute_rsi(closes, 14)

    # MACD
    macd = compute_macd(closes)

    # 布林带
    bollinger = compute_bollinger(closes)

    # 近期高低点
    recent_20 = candles[-20:]
    recent_high = max(c["high"] for c in recent_20)
    recent_low = min(c["low"] for c in recent_20)

    # 成交量变化
    avg_vol_5 = vol_ma5[-1] if vol_ma5[-1] else 0
    avg_vol_20 = vol_ma20[-1] if vol_ma20[-1] else 1
    volume_ratio = round(avg_vol_5 / avg_vol_20, 2) if avg_vol_20 else 1

    # 涨跌趋势 (近5日)
    if len(closes) >= 5:
        trend_5d = round((closes[-1] - closes[-5]) / closes[-5] * 100, 2)
    else:
        trend_5d = 0

    # 涨跌趋势 (近20日)
    if len(closes) >= 20:
        trend_20d = round((closes[-1] - closes[-20]) / closes[-20] * 100, 2)
    else:
        trend_20d = 0

    return {
        "current_price": current_price,
        "ma_status": ma_status,
        "rsi": rsi,
        "rsi_signal": "超买" if rsi > 70 else "超卖" if rsi < 30 else "中性",
        "macd": macd,
        "macd_signal": "金叉/多头" if macd["histogram"] > 0 else "死叉/空头",
        "bollinger": bollinger,
        "bollinger_position": (
            "上轨之上(超买)" if current_price > bollinger["upper"] else
            "下轨之下(超卖)" if current_price < bollinger["lower"] else
            "中轨之上" if current_price > bollinger["middle"] else "中轨之下"
        ),
        "recent_20d_high": recent_high,
        "recent_20d_low": recent_low,
        "volume_ratio": volume_ratio,
        "volume_signal": "放量" if volume_ratio > 1.5 else "缩量" if volume_ratio < 0.7 else "正常",
        "trend_5d_pct": trend_5d,
        "trend_20d_pct": trend_20d,
    }
