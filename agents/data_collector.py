# -*- coding: utf-8 -*-
"""数据收集器 - 一次性收集所有数据供各Agent使用"""

import time
import requests
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Any

from .technical import compute_all_indicators


def _add_sentiment_pre_analysis(data: Dict[str, Any]) -> Dict[str, Any]:
    """使用关键词情绪分析为新闻打分，作为 Agent 的预判数据"""
    news = data.get("news", [])
    if not news:
        data["sentiment_pre_analysis"] = {}
        return data

    try:
        from sentiment.analyzer import SentimentAnalyzer
        from sentiment.sources import NewsArticle

        # 将 dict 新闻列表转为 NewsArticle 对象
        articles = []
        for n in news:
            article = NewsArticle(
                title=n.get("headline", ""),
                summary=n.get("summary", ""),
                source=n.get("source", ""),
            )
            articles.append(article)

        analyzer = SentimentAnalyzer()
        articles = analyzer.analyze_articles(articles)
        aggregate = analyzer.aggregate_sentiment(articles)

        # 注入 sentiment_score 回原始 news 列表
        for i, n in enumerate(news):
            if i < len(articles):
                n["sentiment_score"] = articles[i].sentiment_score

        data["sentiment_pre_analysis"] = {
            "score": aggregate["score"],
            "label": aggregate["label"],
            "positive_ratio": aggregate["positive_ratio"],
            "negative_ratio": aggregate["negative_ratio"],
            "total_articles": aggregate["total_articles"],
            "summary": _build_sentiment_summary(data["symbol"], aggregate),
        }
    except Exception:
        data["sentiment_pre_analysis"] = {}

    return data


def _build_sentiment_summary(symbol: str, aggregate: Dict[str, Any]) -> str:
    """生成一句话情绪摘要"""
    score = aggregate.get("score", 0)
    total = aggregate.get("total_articles", 0)
    if total == 0:
        return "暂无新闻"
    if score > 0.3:
        return f"整体偏正面 ({score:+.2f})，共{total}条"
    elif score > 0.05:
        return f"整体偏中性 ({score:+.2f})，共{total}条"
    elif score > -0.3:
        return f"整体偏负面 ({score:+.2f})，共{total}条"
    else:
        return f"整体偏负面 ({score:+.2f})，共{total}条"


def collect_stock_data(symbol: str, finnhub_client, market: str = "us", **kwargs) -> Dict[str, Any]:
    """
    收集股票的所有可用数据
    Args:
        symbol: 股票代码
        finnhub_client: Finnhub API客户端
        market: 市场类型 - "us" 美股, "cn" A股
    Returns: StockData dict with all collected info
    """
    if market == "cn":
        return _add_sentiment_pre_analysis(_collect_a_share_data(symbol))
    return _add_sentiment_pre_analysis(_collect_us_data(symbol, finnhub_client))


def _collect_us_data(symbol: str, finnhub_client) -> Dict[str, Any]:
    """收集美股数据（原逻辑）"""
    symbol = symbol.upper()
    data: Dict[str, Any] = {"symbol": symbol, "market": "us"}

    # 1. 基本报价
    try:
        quote = finnhub_client.quote(symbol)
        data["quote"] = {
            "price": quote["c"],
            "change": quote["d"],
            "change_pct": quote["dp"],
            "open": quote["o"],
            "high": quote["h"],
            "low": quote["l"],
            "prev_close": quote["pc"],
        }
    except Exception:
        data["quote"] = {}

    # 2. 公司概况
    try:
        profile = finnhub_client.company_profile2(symbol=symbol)
        name = profile.get("name", "")
        # ETF等产品 Finnhub 可能返回空profile，用 Yahoo Finance 兜底
        if not name:
            try:
                ticker = yf.Ticker(symbol)
                yf_info = ticker.info
                name = yf_info.get("longName") or yf_info.get("shortName") or symbol
                data["profile"] = {
                    "name": name,
                    "industry": yf_info.get("industry") or yf_info.get("category") or "",
                    "market_cap": yf_info.get("marketCap", 0) / 1e6 if yf_info.get("marketCap") else 0,
                    "exchange": yf_info.get("exchange", ""),
                    "country": yf_info.get("country", ""),
                    "ipo": yf_info.get("ipoTradeDate", ""),
                    "share_outstanding": yf_info.get("sharesOutstanding", 0) / 1e8 if yf_info.get("sharesOutstanding") else 0,
                    "currency": yf_info.get("currency", "USD"),
                    "instrument_type": yf_info.get("quoteType", ""),  # ETF/COMMON_STOCK
                }
            except Exception:
                data["profile"] = {"name": symbol, "currency": "USD", "instrument_type": ""}
        else:
            data["profile"] = {
                "name": name,
                "industry": profile.get("finnhubIndustry", ""),
                "market_cap": profile.get("marketCapitalization", 0),
                "exchange": profile.get("exchange", ""),
                "country": profile.get("country", ""),
                "ipo": profile.get("ipo", ""),
                "share_outstanding": profile.get("shareOutstanding", 0),
                "currency": profile.get("currency", "USD"),
                "instrument_type": "EQUITY",
            }
    except Exception:
        data["profile"] = {"name": symbol, "currency": "USD"}

    # 3. 基本财务指标
    try:
        financials = finnhub_client.company_basic_financials(symbol, "all")
        metric = financials.get("metric", {})
        data["financials"] = {
            "pe_ratio": metric.get("peBasicExclExtraTTM"),
            "pb_ratio": metric.get("pbQuarterly"),
            "ps_ratio": metric.get("psAnnual"),
            "roe": metric.get("roeTTM"),
            "roa": metric.get("roaTTM"),
            "eps_ttm": metric.get("epsBasicExclExtraItemsTTM"),
            "revenue_growth": metric.get("revenueGrowthQuarterlyYoy"),
            "net_margin": metric.get("netProfitMarginTTM"),
            "debt_to_equity": metric.get("totalDebt/totalEquityQuarterly"),
            "dividend_yield": metric.get("dividendYieldIndicatedAnnual"),
            "beta": metric.get("beta"),
            "52w_high": metric.get("52WeekHigh"),
            "52w_low": metric.get("52WeekLow"),
            "52w_high_date": metric.get("52WeekHighDate"),
            "52w_low_date": metric.get("52WeekLowDate"),
            "10d_avg_volume": metric.get("10DayAverageTradingVolume"),
            "3m_avg_volume": metric.get("3MonthAverageTradingVolume"),
        }
    except Exception:
        data["financials"] = {}

    # 4. 分析师推荐趋势
    try:
        recs = finnhub_client.recommendation_trends(symbol)
        if recs:
            latest = recs[0]
            data["recommendations"] = {
                "period": latest.get("period", ""),
                "strong_buy": latest.get("strongBuy", 0),
                "buy": latest.get("buy", 0),
                "hold": latest.get("hold", 0),
                "sell": latest.get("sell", 0),
                "strong_sell": latest.get("strongSell", 0),
            }
        else:
            data["recommendations"] = {}
    except Exception:
        data["recommendations"] = {}

    # 5. 新闻
    try:
        to_date = datetime.today().strftime("%Y-%m-%d")
        from_date = (datetime.today() - timedelta(days=14)).strftime("%Y-%m-%d")
        news = finnhub_client.company_news(symbol, _from=from_date, to=to_date)
        data["news"] = [
            {
                "headline": n.get("headline", ""),
                "summary": n.get("summary", ""),
                "source": n.get("source", ""),
                "datetime": n.get("datetime", 0),
            }
            for n in news[:10]
        ]
    except Exception:
        data["news"] = []

    # 6. 内部人交易
    try:
        insider = finnhub_client.stock_insider_transactions(symbol, "2024-01-01", datetime.today().strftime("%Y-%m-%d"))
        transactions = insider.get("data", [])[:10]
        data["insider_transactions"] = [
            {
                "name": t.get("name", ""),
                "share": t.get("share", 0),
                "change": t.get("change", 0),
                "transaction_type": t.get("transactionType", ""),
                "filing_date": t.get("filingDate", ""),
            }
            for t in transactions
        ]
    except Exception:
        data["insider_transactions"] = []

    # 7. 机构持仓
    try:
        ownership = finnhub_client.ownership(symbol, limit=10)
        holders = ownership.get("ownership", [])
        data["institutional_holders"] = [
            {
                "name": h.get("name", ""),
                "share": h.get("share", 0),
                "change": h.get("change", 0),
                "pct": h.get("percentage", 0),
            }
            for h in holders[:8]
        ]
    except Exception:
        data["institutional_holders"] = []

    # 8. 同行对比
    try:
        peers = finnhub_client.company_peers(symbol)
        data["peers"] = peers[:6] if peers else []
    except Exception:
        data["peers"] = []

    # 9. K线数据 + 技术指标
    try:
        candles = _fetch_candles_yahoo(symbol)
        data["candles_summary"] = {
            "total_days": len(candles),
            "latest_5": candles[-5:] if len(candles) >= 5 else candles,
        }
        data["technical_indicators"] = compute_all_indicators(candles)
    except Exception:
        data["candles_summary"] = {}
        data["technical_indicators"] = {}

    # 10. 生成数据可用性说明
    data["data_notes"] = _generate_data_notes(data)

    return data


def _generate_data_notes(data: Dict[str, Any]) -> str:
    """根据已收集数据生成可用性说明，帮助Agent解释缺失原因"""
    notes = []
    instrument_type = data.get("profile", {}).get("instrument_type", "")
    is_etf = "ETF" in str(instrument_type).upper()
    market = data.get("market", "us")

    if is_etf:
        notes.append("【重要：该标的为ETF，需特别注意以下数据限制】")
        notes.append("- ETF没有传统的PE/PB/ROE等估值指标，这些字段为空是正常的")
        notes.append("- ETF不涉及内部人交易，内部人交易数据为空是正常的")
        notes.append("- Finnhub免费版不提供ETF机构持仓数据，机构持仓为空是数据源限制")
        notes.append("- 分析ETF时应关注费率、追踪误差、规模(AUM)、流动性等特有指标")
    elif market == "cn":
        cn_notes = []
        if not data.get("financials"):
            cn_notes.append("- 未获取到财务指标数据，请重点关注技术面和消息面分析")
        if not data.get("recommendations"):
            cn_notes.append("- A股暂不提供分析师推荐数据，请基于财务指标自行判断")
        if cn_notes:
            notes.append("【A股数据可用性说明】")
            notes.extend(cn_notes)

    # 通用缺失说明
    if not data.get("financials") and not is_etf and market != "cn":
        notes.append("【数据可用性说明】")
        notes.append("- 未获取到财务指标数据（PE/PB/ROE等），可能是ETF产品或数据源限制")
    if not data.get("institutional_holders") and not is_etf and market != "cn":
        if not data.get("financials"):  # 还没加过标题
            notes.append("【数据可用性说明】")
        notes.append("- 未获取到机构持仓数据，可能是数据源限制")
    if not data.get("insider_transactions") and not is_etf and market != "cn":
        if not data.get("financials") and not data.get("institutional_holders"):
            notes.append("【数据可用性说明】")
        notes.append("- 未获取到内部人交易数据，可能是数据源限制或无近期内幕交易")

    return "\n".join(notes) if notes else ""


def _collect_a_share_data(symbol: str) -> Dict[str, Any]:
    """收集A股数据（通过 AKShare - 腾讯+新浪数据源）"""
    import akshare as ak

    data: Dict[str, Any] = {"symbol": symbol, "market": "cn"}
    exchange = "上交所" if symbol.startswith("6") else "深交所"

    # 1. 基本报价 - 新浪实时API
    try:
        sina_sym = f"sh{symbol}" if (symbol.startswith("6") or symbol.startswith("5") or symbol.startswith("9")) else f"sz{symbol}"
        url = f"http://hq.sinajs.cn/list={sina_sym}"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10, proxies={"http": None, "https": None})
        resp.encoding = "gbk"
        text = resp.text
        if "=" in text:
            data_str = text.split('"')[1] if '"' in text else text.split("=", 1)[1]
            parts = data_str.split(",")
            if len(parts) >= 6:
                name = parts[0]
                open_p = float(parts[1])
                prev_c = float(parts[2])
                current = float(parts[3])
                high_p = float(parts[4])
                low_p = float(parts[5])
                chg = round(current - prev_c, 2)
                chg_pct = round((chg / prev_c) * 100, 2) if prev_c > 0 else 0
                data["quote"] = {
                    "price": current,
                    "change": chg,
                    "change_pct": chg_pct,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "prev_close": prev_c,
                }
                default_name = name
            else:
                data["quote"] = {}
                default_name = symbol
        else:
            data["quote"] = {}
            default_name = symbol
    except Exception:
        data["quote"] = {}
        default_name = symbol

    # 2. 公司概况（A股可用数据有限，使用spot中的信息）
    data["profile"] = {
        "name": default_name,
        "industry": "",
        "market_cap": 0,
        "exchange": exchange,
        "country": "CN",
        "ipo": "",
        "share_outstanding": 0,
        "currency": "CNY",
    }

    # 3. 财务指标（AKShare stock_financial_abstract）
    data["financials"] = {}
    try:
        fin_df = ak.stock_financial_abstract(symbol=symbol)
        if not fin_df.empty:
            # 列结构: 选项, 指标, 日期列(最新→最旧)
            date_cols = [c for c in fin_df.columns if c not in ("选项", "指标")]
            annual_col = date_cols[1] if len(date_cols) > 1 else date_cols[0]  # 最新年报
            prev_annual = None
            for c in date_cols:
                if str(c).endswith("1231") and c != annual_col:
                    prev_annual = c
                    break
            if not prev_annual:
                prev_annual = date_cols[5] if len(date_cols) > 5 else None  # 4个季度前

            def _fin_val(row_idx, col=annual_col):
                """安全获取财务指标值"""
                try:
                    v = fin_df.iloc[row_idx][col]
                    return float(v) if v and str(v) != "nan" else None
                except Exception:
                    return None

            eps = _fin_val(8)           # 基本每股收益
            bvps = _fin_val(9)          # 每股净资产
            rev_ps = _fin_val(31)       # 每股营业收入
            roe = _fin_val(11)          # ROE
            roa = _fin_val(12)          # ROA
            gross_margin = _fin_val(13)  # 毛利率
            net_margin = _fin_val(14)   # 销售净利率
            debt_ratio = _fin_val(16)   # 资产负债率

            # 成长率 (年度同比)
            rev_growth = None
            net_growth = None
            if prev_annual:
                rev_cur = _fin_val(51, annual_col)   # 营业收入绝对值
                rev_prev = _fin_val(51, prev_annual)
                if rev_cur and rev_prev and rev_prev > 0:
                    rev_growth = round((rev_cur - rev_prev) / rev_prev * 100, 2)
                
                net_cur = _fin_val(50, annual_col)   # 归母净利润绝对值
                net_prev = _fin_val(50, prev_annual)
                if net_cur and net_prev and abs(net_prev) > 0:
                    net_growth = round((net_cur - net_prev) / abs(net_prev) * 100, 2)

            price = data.get("quote", {}).get("price", 0)
            pe = round(price / eps, 2) if eps and eps > 0 and price > 0 else None
            pb = round(price / bvps, 2) if bvps and bvps > 0 and price > 0 else None
            ps = round(price / rev_ps, 2) if rev_ps and rev_ps > 0 and price > 0 else None

            data["financials"] = {
                "pe_ratio": pe,
                "pb_ratio": pb,
                "ps_ratio": ps,
                "roe": roe,
                "roa": roa,
                "eps_ttm": eps,
                "revenue_growth": rev_growth or net_growth,  # 优先营收增长, 其次利润增长
                "net_margin": net_margin,
                "debt_to_equity": debt_ratio,
                "dividend_yield": None,
                "beta": None,
                "52w_high": None,
                "52w_low": None,
            }
            # 从K线数据计算52周高/低（稍后在K线采集完成后更新）
    except Exception as e:
        data["financials"] = {}

    # 4. 分析师推荐趋势（A股无此数据）
    data["recommendations"] = {}

    # 5. 新闻
    try:
        news_df = ak.stock_news_em(symbol=symbol)
        if not news_df.empty:
            data["news"] = [
                {
                    "headline": str(n.get("新闻标题", "")),
                    "summary": str(n.get("新闻内容", ""))[:200],
                    "source": str(n.get("文章来源", "")),
                    "datetime": int(datetime.strptime(str(n.get("发布时间", "2024-01-01 00:00:00"))[:19], "%Y-%m-%d %H:%M:%S").timestamp()) if n.get("发布时间") else 0,
                }
                for _, n in news_df.head(10).iterrows()
            ]
        else:
            data["news"] = []
    except Exception:
        data["news"] = []

    # 6. 内部人交易（无）
    data["insider_transactions"] = []

    # 7. 机构持仓（无）
    data["institutional_holders"] = []

    # 8. 同行对比（无）
    data["peers"] = []

    # 9. K线数据 + 技术指标 - 新浪数据源
    try:
        # 新浪源格式: sz000001 或 sh600519
        if symbol.startswith("6") or symbol.startswith("5") or symbol.startswith("9"):
            sina_sym = f"sh{symbol}"
        else:
            sina_sym = f"sz{symbol}"

        end_date = datetime.today().strftime("%Y%m%d")
        start_date = (datetime.today() - timedelta(days=200)).strftime("%Y%m%d")
        hist = ak.stock_zh_a_daily(symbol=sina_sym, start_date=start_date, end_date=end_date, adjust="qfq")
        if not hist.empty:
            candles = []
            for _, r in hist.iterrows():
                candles.append({
                    "date": str(r["date"])[:10],
                    "open": round(float(r["open"]), 2),
                    "high": round(float(r["high"]), 2),
                    "low": round(float(r["low"]), 2),
                    "close": round(float(r["close"]), 2),
                    "volume": int(r["volume"]),
                })
            data["candles_summary"] = {
                "total_days": len(candles),
                "latest_5": candles[-5:] if len(candles) >= 5 else candles,
            }
            data["technical_indicators"] = compute_all_indicators(candles)
            # 从K线计算52周高低
            if candles and data.get("financials"):
                highs = [c["high"] for c in candles if c.get("high")]
                lows = [c["low"] for c in candles if c.get("low")]
                if highs:
                    data["financials"]["52w_high"] = round(max(highs), 2)
                    data["financials"]["52w_high_date"] = max(candles, key=lambda x: x.get("high", 0)).get("date", "")
                if lows:
                    data["financials"]["52w_low"] = round(min(lows), 2)
                    data["financials"]["52w_low_date"] = min(candles, key=lambda x: x.get("low", float("inf"))).get("date", "")
        else:
            data["candles_summary"] = {}
            data["technical_indicators"] = {}
    except Exception:
        data["candles_summary"] = {}
        data["technical_indicators"] = {}

    data["data_notes"] = _generate_data_notes(data)
    return data


def _parse_float(val) -> float:
    """安全解析浮点数"""
    if val is None or val == "" or val == "-" or val == "--":
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _fetch_candles_yahoo(symbol: str, days: int = 180):
    """从Yahoo Finance HTTP API获取K线数据"""
    period2 = int(time.time())
    period1 = int((datetime.now() - timedelta(days=days)).timestamp())

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"period1": period1, "period2": period2, "interval": "1d", "includePrePost": "false"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp_data = resp.json()
    chart = resp_data.get("chart", {}).get("result", [])
    if not chart:
        return []

    timestamps = chart[0].get("timestamp", [])
    ohlcv = chart[0].get("indicators", {}).get("quote", [{}])[0]

    result = []
    for i, ts in enumerate(timestamps):
        o = ohlcv.get("open", [None])[i]
        h = ohlcv.get("high", [None])[i]
        l = ohlcv.get("low", [None])[i]
        c = ohlcv.get("close", [None])[i]
        v = ohlcv.get("volume", [None])[i]
        if o is None or c is None:
            continue
        result.append({
            "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
            "open": round(o, 2),
            "high": round(h, 2),
            "low": round(l, 2),
            "close": round(c, 2),
            "volume": int(v) if v else 0,
        })
    return result
