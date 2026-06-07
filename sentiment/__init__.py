# -*- coding: utf-8 -*-
"""舆情分析模块 —— 多源新闻采集 + 关键词情绪分析"""

from .engine import SentimentEngine, SentimentResult, get_sentiment_engine
from .sources import NewsArticle, collect_all_news

__all__ = [
    "SentimentEngine",
    "SentimentResult",
    "get_sentiment_engine",
    "NewsArticle",
    "collect_all_news",
]
