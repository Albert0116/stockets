# -*- coding: utf-8 -*-
"""内置扫描策略 - 数据层过滤（0 tokens消耗）"""

from typing import Dict, Any, List, Callable
import akshare as ak
import pandas as pd


def strategy_volume_breakout(df: pd.DataFrame) -> pd.DataFrame:
    """放量突破策略 - 筛选今日成交量>5日均量2倍且涨幅>3%的股票"""
    if df.empty:
        return df
    result = df[
        (df["涨跌幅"] > 3) &
        (df["量比"] > 2) &
        (df["换手率"] > 2) &
        (df["最新价"] > 5)  # 排除低价股
    ].copy()
    result = result.sort_values("量比", ascending=False)
    return result.head(20)


def strategy_oversold_bounce(df: pd.DataFrame) -> pd.DataFrame:
    """超跌反弹策略 - 近期大跌后出现反弹信号"""
    if df.empty:
        return df
    # 当日涨幅>2%，但60日涨跌幅<-20%（超跌后反弹）
    result = df[
        (df["涨跌幅"] > 2) &
        (df.get("60日涨跌幅", pd.Series([0]*len(df))) < -20) &
        (df["最新价"] > 3) &
        (df["换手率"] > 1)
    ].copy()
    result = result.sort_values("涨跌幅", ascending=False)
    return result.head(20)


def strategy_steady_growth(df: pd.DataFrame) -> pd.DataFrame:
    """稳健成长策略 - 市盈率合理、涨幅稳定"""
    if df.empty:
        return df
    result = df[
        (df.get("市盈率-动态", pd.Series([999]*len(df))) > 0) &
        (df.get("市盈率-动态", pd.Series([999]*len(df))) < 30) &
        (df["最新价"] > 10) &
        (df["涨跌幅"] > 0) &
        (df["涨跌幅"] < 5) &
        (df["换手率"] > 0.5) &
        (df["换手率"] < 10)
    ].copy()
    if "市盈率-动态" in result.columns:
        result = result.sort_values("市盈率-动态", ascending=True)
    return result.head(20)


def strategy_new_high(df: pd.DataFrame) -> pd.DataFrame:
    """创新高策略 - 股价接近或创52周新高"""
    if df.empty:
        return df
    result = df[
        (df["涨跌幅"] > 1) &
        (df["最新价"] > 10) &
        (df.get("年初至今涨跌幅", pd.Series([0]*len(df))) > 20) &
        (df["换手率"] > 1)
    ].copy()
    if "年初至今涨跌幅" in result.columns:
        result = result.sort_values("年初至今涨跌幅", ascending=False)
    return result.head(20)


# 策略注册表
BUILTIN_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "volume_breakout": {
        "name": "放量突破",
        "description": "成交量放大2倍以上且涨幅>3%，突破信号强",
        "filter_fn": strategy_volume_breakout,
        "market": "cn",
    },
    "oversold_bounce": {
        "name": "超跌反弹",
        "description": "60日跌幅超20%后出现2%以上反弹",
        "filter_fn": strategy_oversold_bounce,
        "market": "cn",
    },
    "steady_growth": {
        "name": "稳健成长",
        "description": "PE<30、涨幅温和、换手适中的优质标的",
        "filter_fn": strategy_steady_growth,
        "market": "cn",
    },
    "new_high": {
        "name": "创新高",
        "description": "年初至今涨幅>20%且仍在上涨的强势股",
        "filter_fn": strategy_new_high,
        "market": "cn",
    },
}
