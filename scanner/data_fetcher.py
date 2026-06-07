# -*- coding: utf-8 -*-
"""市场数据获取 - 使用Sina API绕过企业代理（支持A股+美股）"""

import asyncio
import logging
import math
import re
import time
from typing import Optional, List

import akshare as ak
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_SINA_BATCH_SIZE = 400
_SINA_URL = "http://hq.sinajs.cn/list="
_SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# 美股精选扫描池（Top 200+ 市值最大的美股 + 热门ETF）
US_TOP_STOCKS = [
    # 科技巨头
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "ORCL", "CRM",
    "ADBE", "CSCO", "INTC", "AMD", "QCOM", "TXN", "INTU", "NOW", "IBM", "UBER",
    "SHOP", "SNOW", "PLTR", "CRWD", "DDOG", "ZS", "NET", "MDB", "TEAM", "WDAY",
    "ADSK", "FTNT", "PANW", "ANET", "DELL", "HPQ", "SMCI", "MU", "MRVL",
    # 金融
    "BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "SCHW",
    "AXP", "C", "PYPL", "SQ", "COIN", "BX", "KKR", "ICE", "CME",
    # 消费
    "WMT", "COST", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "TJX", "ROST",
    "DG", "DLTR", "ULTA", "LULU", "DHI", "LEN", "NVR",
    # 医疗
    "JNJ", "UNH", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "LLY",
    "AMGN", "GILD", "ISRG", "VRTX", "REGN", "CI", "CVS", "HUM", "ZTS",
    # 通信/媒体
    "DIS", "NFLX", "CMCSA", "VZ", "T", "TMUS", "CHTR", "SPOT", "SNAP", "PINS",
    # 工业/能源
    "XOM", "CVX", "COP", "EOG", "SLB", "OXY", "PXD", "HAL",
    "CAT", "GE", "BA", "RTX", "LMT", "HON", "UNP", "UPS", "FDX", "DE",
    # 其他
    "PG", "KO", "PEP", "PM", "MO", "MDLZ", "CL", "KMB",
    "SPGI", "MCO", "EQIX", "PLD", "AMT", "CCI", "WELL", "O",
    "SNPS", "CDNS", "KLAC", "AMAT", "LRCX",
    # 中概股
    "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI", "BILI", "TME",
    # 热门ETF
    "SPY", "QQQ", "QQQM", "IWM", "DIA", "VTI", "VOO", "ARKK", "SOXX", "SMH",
    "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "VNQ", "GLD", "TLT", "LQD",
]
US_TOP_STOCKS = list(dict.fromkeys(US_TOP_STOCKS))  # 去重


async def fetch_a_share_market_data() -> pd.DataFrame:
    """获取全A股实时行情数据（通过Sina API）"""
    logger.info("获取A股代码列表...")
    try:
        code_df = await asyncio.to_thread(ak.stock_info_a_code_name)
    except Exception as e:
        logger.error(f"获取股票代码列表失败: {e}")
        raise

    if code_df.empty:
        return pd.DataFrame()

    symbols = []
    for _, row in code_df.iterrows():
        code = str(row["code"]).zfill(6)
        if code.startswith("6") or code.startswith("5") or code.startswith("9"):
            sina_sym = f"sh{code}"
        else:
            sina_sym = f"sz{code}"
        symbols.append(sina_sym)

    logger.info(f"共 {len(symbols)} 只A股，批量获取行情...")
    return await _fetch_sina_batch(symbols, market="cn")


async def fetch_us_market_data() -> pd.DataFrame:
    """获取美股精选池实时行情（通过Sina API）"""
    symbols = [f"gb_{t.lower()}" for t in US_TOP_STOCKS]
    logger.info(f"共 {len(symbols)} 只美股，批量获取行情...")
    return await _fetch_sina_batch(symbols, market="us")


async def _fetch_sina_batch(symbols: List[str], market: str = "cn") -> pd.DataFrame:
    """通用Sina批量行情获取"""
    all_rows = []
    total_batches = math.ceil(len(symbols) / _SINA_BATCH_SIZE)

    for i in range(0, len(symbols), _SINA_BATCH_SIZE):
        batch = symbols[i:i + _SINA_BATCH_SIZE]
        batch_num = i // _SINA_BATCH_SIZE + 1

        try:
            url = _SINA_URL + ",".join(batch)
            resp = await asyncio.to_thread(
                requests.get, url,
                headers=_SINA_HEADERS, timeout=30,
                proxies={"http": None, "https": None}
            )
            resp.encoding = "gbk"
            text = resp.text

            for line in text.strip().split("\n"):
                if "=" not in line or '"' not in line:
                    continue
                try:
                    code_part = line.split("=")[0].replace("var hq_str_", "")
                    data_str = line.split('"')[1]
                    fields = data_str.split(",")

                    if market == "us":
                        if len(fields) < 14:
                            continue
                        code = code_part.replace("gb_", "").upper()
                        name = fields[0]
                        price = _safe_float(fields[1])
                        change_pct = _safe_float(fields[2])
                        volume = _safe_float(fields[10])
                        avg_volume = _safe_float(fields[11])
                        market_cap = _safe_float(fields[12])
                        pe = _safe_float(fields[13])
                        prev_close = _safe_float(fields[26]) if len(fields) > 26 else price - price * change_pct / 100
                    else:  # cn
                        if len(fields) < 10:
                            continue
                        code = re.sub(r'^[a-z]+', '', code_part)
                        name = fields[0]
                        price = _safe_float(fields[3])
                        prev_close = _safe_float(fields[2])
                        volume = _safe_float(fields[8])
                        market_cap = 0
                        pe = 999
                        avg_volume = 0
                        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0

                    if price <= 0:
                        continue

                    volume_ratio = round(volume / avg_volume, 2) if avg_volume > 0 else 0

                    all_rows.append({
                        "代码": code,
                        "名称": name,
                        "最新价": price,
                        "涨跌幅": change_pct,
                        "成交量": volume,
                        "成交额": 0,
                        "量比": volume_ratio,
                        "换手率": 0,
                        "市盈率-动态": pe if pe > 0 else 999,
                        "60日涨跌幅": 0,
                        "年初至今涨跌幅": 0,
                        "市值": market_cap,  # 美股才有的额外字段
                    })
                except Exception:
                    continue

            logger.info(f"  批次 {batch_num}/{total_batches}: {len(batch)} 请求, 累计 {len(all_rows)} 条")
        except Exception as e:
            logger.error(f"批次 {batch_num} 查询失败: {e}")
            continue

        if batch_num < total_batches:
            await asyncio.sleep(0.5)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    logger.info(f"Sina数据获取完成({market}): {len(df)} 只股票有效")
    return df


def _safe_float(val: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
