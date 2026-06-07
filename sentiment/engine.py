# -*- coding: utf-8 -*-
"""舆情分析引擎 —— 整合多源新闻采集 + 情绪分析

使用方式:
    engine = SentimentEngine()
    result = engine.analyze("AAPL", market="us", finnhub_client=client)
    # result 包含: score, label, articles, aggregate, 等
"""

from typing import Any, Dict, List, Optional

from .sources import collect_all_news, NewsArticle
from .analyzer import SentimentAnalyzer


class SentimentResult:
    """完整的舆情分析结果"""
    __slots__ = (
        "symbol", "market", "score", "label", "articles",
        "aggregate", "summary_text",
    )

    def __init__(
        self,
        symbol: str = "",
        market: str = "us",
        score: float = 0.0,
        label: str = "中性",
        articles: Optional[List[NewsArticle]] = None,
        aggregate: Optional[Dict[str, Any]] = None,
        summary_text: str = "",
    ):
        self.symbol = symbol
        self.market = market
        self.score = score
        self.label = label
        self.articles = articles or []
        self.aggregate = aggregate or {}
        self.summary_text = summary_text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "market": self.market,
            "score": self.score,
            "label": self.label,
            "summary": self.summary_text,
            "aggregate": self.aggregate,
            "articles": [a.to_dict() for a in self.articles[:10]],
        }


class SentimentEngine:
    """舆情分析引擎"""

    def __init__(self):
        self.analyzer = SentimentAnalyzer()

    def analyze(
        self,
        symbol: str,
        market: str = "us",
        finnhub_client=None,
        max_articles: int = 15,
    ) -> SentimentResult:
        """获取并分析舆情

        Args:
            symbol: 股票代码
            market: "us" / "cn"
            finnhub_client: Finnhub 客户端（美股必传）
            max_articles: 最大文章数

        Returns:
            SentimentResult
        """
        # 1. 采集新闻
        articles = collect_all_news(
            symbol=symbol,
            market=market,
            finnhub_client=finnhub_client,
            max_articles=max_articles,
        )

        if not articles:
            return SentimentResult(
                symbol=symbol,
                market=market,
                label="无数据",
                summary_text=f"未获取到 {symbol} 的相关新闻",
            )

        # 2. 情绪打分
        articles = self.analyzer.analyze_articles(articles)

        # 3. 聚合
        aggregate = self.analyzer.aggregate_sentiment(articles)

        # 4. 生成自然语言摘要
        summary_text = self._build_summary(symbol, aggregate)

        return SentimentResult(
            symbol=symbol,
            market=market,
            score=aggregate["score"],
            label=aggregate["label"],
            articles=articles,
            aggregate=aggregate,
            summary_text=summary_text,
        )

    def quick_score(
        self,
        symbol: str,
        market: str = "us",
        finnhub_client=None,
    ) -> Dict[str, Any]:
        """快速评分 —— 只返回核心指标，适合股票列表批量调用"""
        result = self.analyze(symbol, market, finnhub_client, max_articles=8)
        return {
            "symbol": result.symbol,
            "score": result.score,
            "label": result.label,
            "article_count": len(result.articles),
            "positive_ratio": result.aggregate.get("positive_ratio", 0),
        }

    def _build_summary(self, symbol: str, aggregate: Dict[str, Any]) -> str:
        """构建人类可读的摘要文本"""
        label = aggregate["label"]
        score = aggregate["score"]
        total = aggregate["total_articles"]
        pos_r = aggregate["positive_ratio"]
        neg_r = aggregate["negative_ratio"]

        if total == 0:
            return f"{symbol} 暂无相关新闻"

        intensity = "强烈" if abs(score) > 0.4 else "" if abs(score) > 0.1 else "略微"

        if score > 0.1:
            sentiment_word = "看多"
        elif score < -0.1:
            sentiment_word = "看空"
        else:
            sentiment_word = "中性"

        parts = [
            f"{symbol} 近14天共{total}条新闻，",
            f"整体情绪{intensity}{sentiment_word}（{score:+.2f}），",
            f"正面占比{pos_r:.0%}，负面占比{neg_r:.0%}。",
        ]

        # 添加强力信号
        top_pos = aggregate.get("top_positive", [])
        top_neg = aggregate.get("top_negative", [])
        if top_pos and score > 0.2:
            parts.append(f"主要利好: 「{top_pos[0].get('title', '')[:50]}」")
        if top_neg and score < -0.2:
            parts.append(f"主要担忧: 「{top_neg[0].get('title', '')[:50]}」")

        return "".join(parts)


# 单例
_engine_instance: Optional[SentimentEngine] = None


def get_sentiment_engine() -> SentimentEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SentimentEngine()
    return _engine_instance
