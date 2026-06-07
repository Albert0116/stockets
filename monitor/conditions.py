# -*- coding: utf-8 -*-
"""预警条件检查器"""

from typing import Dict, Any, Optional


def check_alert_conditions(rule: Dict[str, Any], quote: Dict[str, Any]) -> Optional[str]:
    """
    检查单条预警规则是否触发
    Args:
        rule: 预警规则 (condition_type, condition_value, symbol)
        quote: 实时行情 (price, change_pct, volume, avg_volume)
    Returns:
        触发消息文本，未触发返回None
    """
    ctype = rule["condition_type"]
    try:
        threshold = float(rule["condition_value"])
    except (ValueError, TypeError):
        return None

    price = quote.get("price", 0)
    change_pct = quote.get("change_pct", 0)
    volume = quote.get("volume", 0)
    avg_volume = quote.get("avg_volume", 1)
    symbol = rule.get("symbol", "")

    if ctype == "price_above" and price > 0 and price >= threshold:
        return f"📈 {symbol} 股价突破 {threshold}，当前 {price:.2f}"

    elif ctype == "price_below" and price > 0 and price <= threshold:
        return f"📉 {symbol} 股价跌破 {threshold}，当前 {price:.2f}"

    elif ctype == "change_pct_above" and change_pct >= threshold:
        return f"🚀 {symbol} 涨幅达到 {change_pct:.2f}%，超过预警值 {threshold}%"

    elif ctype == "change_pct_below" and change_pct <= -abs(threshold):
        return f"⚠️ {symbol} 跌幅达到 {change_pct:.2f}%，超过预警值 -{abs(threshold)}%"

    elif ctype == "volume_spike" and avg_volume > 0:
        ratio = volume / avg_volume
        if ratio >= threshold:
            return f"💥 {symbol} 成交量放大 {ratio:.1f}倍，超过预警值 {threshold}倍"

    return None
