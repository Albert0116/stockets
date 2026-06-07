# -*- coding: utf-8 -*-
"""多源舆情数据采集

支持:
    - Finnhub 新闻 (美股)
    - Sina/东方财富 新闻 (A股，通过AKShare)
    - 通用 HTTP 新闻抓取 (绕过代理)

设计原则:
    - 无外部 NLP 依赖
    - 所有 HTTP 请求走 proxies=None 绕过企业代理
"""

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

# ─── 新闻文章数据结构 ────────────────────────────


class NewsArticle:
    """统一新闻结构"""
    __slots__ = ("title", "summary", "source", "url", "published_at", "sentiment_score")

    def __init__(
        self,
        title: str = "",
        summary: str = "",
        source: str = "",
        url: str = "",
        published_at: str = "",
        sentiment_score: float = 0.0,
    ):
        self.title = title
        self.summary = summary
        self.source = source
        self.url = url
        self.published_at = published_at
        self.sentiment_score = sentiment_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at,
            "sentiment_score": self.sentiment_score,
        }


# ─── 数据源 ──────────────────────────────────────


def fetch_finnhub_news(
    symbol: str,
    finnhub_client,
    days: int = 14,
    max_articles: int = 12,
) -> List[NewsArticle]:
    """Finnhub 美股新闻"""
    try:
        to_date = datetime.today().strftime("%Y-%m-%d")
        from_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        news = finnhub_client.company_news(symbol.upper(), _from=from_date, to=to_date)
        results = []
        for n in news[:max_articles]:
            ts = n.get("datetime", 0)
            pub_time = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            results.append(NewsArticle(
                title=n.get("headline", ""),
                summary=n.get("summary", ""),
                source=n.get("source", "Finnhub"),
                url=n.get("url", ""),
                published_at=pub_time,
            ))
        return results
    except Exception:
        return []


def fetch_sina_cn_news(symbol: str, max_articles: int = 10) -> List[NewsArticle]:
    """A股东方财富新闻 (通过 AKShare)

    注意: AKShare 的 stock_news_em 在公司代理下可能不稳定，
    降级到直接 HTTP 请求（不使用代理）。
    """
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol=symbol)
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.head(max_articles).iterrows():
            pub_time = str(row.get("发布时间", ""))
            results.append(NewsArticle(
                title=str(row.get("新闻标题", "")),
                summary=str(row.get("新闻内容", ""))[:300],
                source=str(row.get("文章来源", "东方财富")),
                url=str(row.get("新闻链接", "")),
                published_at=pub_time[:19] if pub_time else "",
            ))
        return results
    except Exception:
        return []


# ─── 新浪财经新闻 ────────────────────────────────


def fetch_sina_stock_news(symbol: str, max_articles: int = 10) -> List[NewsArticle]:
    """通过新浪财经接口获取个股新闻（适用于A股，绕过代理）

    新浪接口: https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{code}.phtml
    直接解析 HTML 获取新闻标题
    """
    try:
        # 确定新浪代码格式
        if symbol.startswith("6") or symbol.startswith("5") or symbol.startswith("9"):
            sina_code = f"sh{symbol}"
        else:
            sina_code = f"sz{symbol}"

        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{sina_code}.phtml"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        resp = requests.get(url, headers=headers, timeout=15,
                           proxies={"http": None, "https": None})
        resp.encoding = "gb2312"
        html = resp.text

        # 简易 HTML 解析（不依赖 bs4）
        results = []
        # 匹配新闻标题行: <a ... target="_blank">标题</a> <span>日期</span>
        pattern = re.compile(
            r'<a\s+[^>]*target="_blank"[^>]*>\s*(.+?)\s*</a>\s*<span[^>]*>\s*(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})',
            re.DOTALL,
        )
        matches = pattern.findall(html)
        for title, pub_time in matches[:max_articles]:
            title = re.sub(r'<[^>]+>', '', title).strip()
            if title and len(title) > 5:
                results.append(NewsArticle(
                    title=title,
                    summary="",
                    source="新浪财经",
                    url=url,
                    published_at=pub_time.strip(),
                ))
        return results
    except Exception:
        return []


# ─── 聚合入口 ────────────────────────────────────


def collect_all_news(
    symbol: str,
    market: str = "us",
    finnhub_client=None,
    max_articles: int = 15,
) -> List[NewsArticle]:
    """聚合所有可用数据源的新闻

    Args:
        symbol: 股票代码
        market: "us" 美股 / "cn" A股
        finnhub_client: Finnhub 客户端 (美股必传)
        max_articles: 每种来源最大文章数

    Returns:
        去重后的 NewsArticle 列表
    """
    all_articles: List[NewsArticle] = []

    if market == "us":
        if finnhub_client:
            all_articles.extend(fetch_finnhub_news(symbol, finnhub_client, max_articles=max_articles))
    elif market == "cn":
        # 优先 Sina，降级到 AKShare
        sina_news = fetch_sina_stock_news(symbol, max_articles=max_articles)
        if sina_news:
            all_articles.extend(sina_news)
        else:
            all_articles.extend(fetch_sina_cn_news(symbol, max_articles=max_articles))

    # 去重（按标题相似度）
    seen_titles = set()
    unique: List[NewsArticle] = []
    for a in all_articles:
        key = a.title[:40] if a.title else ""
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(a)
    return unique
