# -*- coding: utf-8 -*-
"""内置扫描策略 - 基于Sina API可用字段（A股+美股）"""

from typing import Dict, Any
import pandas as pd


# ========== A股策略 ==========

def strategy_volume_surge(df: pd.DataFrame) -> pd.DataFrame:
    """放量上涨策略 - 涨幅>3%且成交量较大"""
    if df.empty:
        return df
    median_vol = df["成交量"].median() if not df["成交量"].empty else 0
    result = df[
        (df["涨跌幅"] > 3) &
        (df["最新价"] > 5) &
        (df["成交量"] > median_vol * 0.5) &
        (df["成交量"] > 0)
    ].copy()
    result = result.sort_values("涨跌幅", ascending=False)
    return result.head(20)


def strategy_strong_uptrend(df: pd.DataFrame) -> pd.DataFrame:
    """强势上攻策略 - 涨幅>5%的高价活跃股"""
    if df.empty:
        return df
    median_vol = df["成交量"].median() if not df["成交量"].empty else 0
    result = df[
        (df["涨跌幅"] > 5) &
        (df["最新价"] > 10) &
        (df["成交量"] > median_vol * 0.3)
    ].copy()
    result = result.sort_values("涨跌幅", ascending=False)
    return result.head(20)


def strategy_oversold_reversal(df: pd.DataFrame) -> pd.DataFrame:
    """超跌反弹策略 - 当日跌幅>5%，博反弹机会"""
    if df.empty:
        return df
    median_vol = df["成交量"].median() if not df["成交量"].empty else 0
    result = df[
        (df["涨跌幅"] < -5) &
        (df["最新价"] > 3) &
        (df["最新价"] < 50) &
        (df["成交量"] > median_vol * 0.5)
    ].copy()
    result = result.sort_values("涨跌幅", ascending=True)
    return result.head(20)


def strategy_steady_uptick(df: pd.DataFrame) -> pd.DataFrame:
    """稳健上涨策略 - 温和涨幅、中等价位的稳定标的"""
    if df.empty:
        return df
    result = df[
        (df["涨跌幅"] > 0) &
        (df["涨跌幅"] < 5) &
        (df["最新价"] > 10) &
        (df["最新价"] < 200)
    ].copy()
    result = result.sort_values("涨跌幅", ascending=False)
    return result.head(20)


# ========== 美股策略 ==========

def strategy_us_volume_breakout(df: pd.DataFrame) -> pd.DataFrame:
    """美股放量突破 - 量比>1.5且涨幅>2%"""
    if df.empty:
        return df
    result = df[
        (df["涨跌幅"] > 2) &
        (df["量比"] > 1.5) &
        (df["最新价"] > 5) &
        (df["成交量"] > 0)
    ].copy()
    result = result.sort_values("量比", ascending=False)
    return result.head(20)


def strategy_us_growth_value(df: pd.DataFrame) -> pd.DataFrame:
    """美股成长价值 - PE合理(5-40)、大市值、温和上涨"""
    if df.empty:
        return df
    pe_col = df["市盈率-动态"]
    result = df[
        (pe_col > 5) &
        (pe_col < 40) &
        (df.get("市值", pd.Series([0]*len(df))) > 10_000_000_000) &  # >100亿美元
        (df["涨跌幅"] > -1) &
        (df["最新价"] > 10)
    ].copy()
    if "市盈率-动态" in result.columns:
        result = result.sort_values("市盈率-动态", ascending=True)
    return result.head(20)


def strategy_us_strong_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """美股强势动量 - 涨幅>3%、量比>1的高动能标的"""
    if df.empty:
        return df
    result = df[
        (df["涨跌幅"] > 3) &
        (df["量比"] > 1) &
        (df["最新价"] > 10) &
        (df["成交量"] > 0)
    ].copy()
    result = result.sort_values("涨跌幅", ascending=False)
    return result.head(20)


def strategy_us_dip(df: pd.DataFrame) -> pd.DataFrame:
    """美股超跌机会 - 跌幅>3%、量比>0.5的恐慌抛售机会"""
    if df.empty:
        return df
    result = df[
        (df["涨跌幅"] < -3) &
        (df["量比"] > 0.5) &
        (df["最新价"] > 10) &
        (df["成交量"] > 0)
    ].copy()
    result = result.sort_values("涨跌幅", ascending=True)
    return result.head(20)


# 策略注册表
BUILTIN_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "volume_surge": {
        "name": "放量上涨",
        "description": "涨幅>3%、成交量活跃的放量上攻标的",
        "filter_fn": strategy_volume_surge,
        "market": "cn",
    },
    "strong_uptrend": {
        "name": "强势上攻",
        "description": "涨幅>5%的高价活跃强势股",
        "filter_fn": strategy_strong_uptrend,
        "market": "cn",
    },
    "oversold_reversal": {
        "name": "超跌反弹",
        "description": "当日跌幅>5%的低价股，关注反弹机会",
        "filter_fn": strategy_oversold_reversal,
        "market": "cn",
    },
    "steady_uptick": {
        "name": "稳健上涨",
        "description": "温和涨幅(0-5%)、中等价位的稳健标的",
        "filter_fn": strategy_steady_uptick,
        "market": "cn",
    },
    # 美股策略
    "us_volume_breakout": {
        "name": "美股·放量突破",
        "description": "量比>1.5且涨幅>2%的放量突破标的",
        "filter_fn": strategy_us_volume_breakout,
        "market": "us",
    },
    "us_growth_value": {
        "name": "美股·成长价值",
        "description": "PE 5-40、市值>100亿、温和上涨的价值标的",
        "filter_fn": strategy_us_growth_value,
        "market": "us",
    },
    "us_strong_momentum": {
        "name": "美股·强势动量",
        "description": "涨幅>3%、量比>1的高动能强势股",
        "filter_fn": strategy_us_strong_momentum,
        "market": "us",
    },
    "us_dip": {
        "name": "美股·超跌机会",
        "description": "跌幅>3%、量比>0.5的恐慌抛售机会",
        "filter_fn": strategy_us_dip,
        "market": "us",
    },
}
