# -*- coding: utf-8 -*-
"""关键词情绪分析引擎

设计原则:
    - 零外部 NLP 依赖 —— 纯词典 + 规则匹配
    - 中英文双语支持
    - 快速 (<1ms/article)，适合批量处理
    - 输出标准化情绪分数 [-1, +1] 和分类标签
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from .sources import NewsArticle

# ─── 中英文情绪词典 ──────────────────────────────

# 正面关键词（英文 + 中文）
POSITIVE_WORDS = {
    # 英文
    "beat", "beats", "beat estimates", "upgrade", "upgraded", "outperform",
    "strong", "growth", "record", "surge", "surges", "soar", "soars", "rally",
    "breakthrough", "bullish", "positive", "optimistic", "raised guidance",
    "buyback", "dividend increase", "approval", "approved", "launch",
    "partnership", "acquisition", "expansion", "momentum", "recovery",
    "recovered", "bottom", "undervalued", "catalyst", "upside",
    "profit", "profitable", "profitability", "earnings beat",
    "revenue growth", "margin expansion", "market share gain",
    # 中文
    "涨停", "大涨", "暴涨", "利好", "突破", "增长", "增速",
    "超预期", "业绩大增", "扭亏", "盈利", "回购", "增持",
    "中标", "签约", "合作", "获批", "量产", "放量",
    "订单", "扩产", "分红", "高送转", "龙头", "领先",
    "创新高", "突破新高", "政策利好", "补贴", "扶持",
    "需求旺盛", "供不应求", "涨价", "毛利率提升",
    "净利增", "营收增", "扣非增", "超预期增长",
}

# 负面关键词
NEGATIVE_WORDS = {
    # 英文
    "miss", "misses", "missed estimates", "downgrade", "downgraded",
    "underperform", "weak", "decline", "drop", "plunge", "plunges",
    "crash", "bearish", "negative", "pessimistic", "lowered guidance",
    "layoff", "layoffs", "restructuring", "lawsuit", "investigation",
    "fine", "penalty", "recall", "debt", "default", "bankruptcy",
    "delisting", "warning", "risk", "risks", "concern", "headwind",
    "headwinds", "slowdown", "contraction", "loss", "losses",
    "revenue decline", "margin pressure", "market share loss",
    "selloff", "sell-off", "correction", "bubble", "overvalued",
    # 中文
    "跌停", "大跌", "暴跌", "利空", "下滑", "下降", "减少",
    "不及预期", "亏损", "减持", "套现", "暴雷", "违约",
    "调查", "处罚", "罚款", "整改", "停产", "召回",
    "诉讼", "仲裁", "退市", "警示", "风险提示",
    "业绩下滑", "净利降", "营收降", "毛利降",
    "需求疲软", "供过于求", "降价", "产能过剩",
    "大股东减持", "质押", "商誉减值", "计提",
    "监管", "约谈", "限产", "环保", "停工",
}

# 程度副词（增强/减弱信号）
INTENSIFIERS = {
    "非常": 1.5, "极其": 2.0, "大幅": 1.5, "显著": 1.3,
    "持续": 1.2, "连续": 1.2, "略": 0.7, "微": 0.5,
    "小幅": 0.7, "稍微": 0.6, "略微": 0.6,
    "very": 1.3, "strongly": 1.5, "significantly": 1.5,
    "slightly": 0.6, "marginally": 0.5, "modestly": 0.7,
}

# 反转词（将正面→负面，负面→正面）
NEGATORS = {
    "不", "没", "无", "未", "难以", "无法", "不会",
    "not", "no", "never", "cannot", "unlikely", "failed",
}

# ─── 分析引擎 ────────────────────────────────────


class SentimentAnalyzer:
    """关键词情绪分析器"""

    @staticmethod
    def score_text(text: str) -> Tuple[float, Dict[str, int]]:
        """对单条文本打分

        Args:
            text: 新闻标题/摘要文本

        Returns:
            (score, details) 其中 score ∈ [-1.0, +1.0]，details 包含命中统计
        """
        if not text:
            return 0.0, {"positive_hits": 0, "negative_hits": 0, "word_count": 0}

        text_lower = text.lower()
        # 混合语言 word count: 英文按空格分词，中文按字符估算
        words = text_lower.split()
        cn_chars = len(re.sub(r'[a-zA-Z0-9\s]', '', text_lower))
        word_count = max(len(words) + cn_chars // 2, 1)

        pos_score = 0.0
        neg_score = 0.0
        pos_hits = 0
        neg_hits = 0

        # 扫描正面词
        for word in POSITIVE_WORDS:
            if word in text_lower:
                weight = 1.0
                # 检查程度修饰词
                for intensifier, factor in INTENSIFIERS.items():
                    if intensifier in text_lower:
                        dist = text_lower.find(intensifier) - text_lower.find(word)
                        if -10 <= dist <= 10:
                            weight *= factor
                            break
                pos_score += weight
                pos_hits += 1

        # 扫描负面词
        for word in NEGATIVE_WORDS:
            if word in text_lower:
                weight = 1.0
                for intensifier, factor in INTENSIFIERS.items():
                    if intensifier in text_lower:
                        dist = text_lower.find(intensifier) - text_lower.find(word)
                        if -10 <= dist <= 10:
                            weight *= factor
                            break
                neg_score += weight
                neg_hits += 1

        # 计算总分的多种方案，选最合理的
        total_hits = pos_hits + neg_hits
        if total_hits == 0:
            return 0.0, {"positive_hits": 0, "negative_hits": 0, "word_count": word_count}

        # 标准化: 正分平均 - 负分平均，映射到 [-1, +1]
        raw = (pos_score / word_count - neg_score / word_count) * 10
        score = max(-1.0, min(1.0, raw))

        return round(score, 3), {
            "positive_hits": pos_hits,
            "negative_hits": neg_hits,
            "word_count": word_count,
        }

    @staticmethod
    def analyze_articles(articles: List[NewsArticle]) -> List[NewsArticle]:
        """批量分析文章，填充 sentiment_score"""
        for article in articles:
            # 标题 + 摘要综合评分（标题权重更高）
            title_score, _ = SentimentAnalyzer.score_text(article.title)
            summary_score, _ = SentimentAnalyzer.score_text(article.summary)

            # 加权: 标题 60% + 摘要 40%
            article.sentiment_score = round(title_score * 0.6 + summary_score * 0.4, 3)

        return articles

    @staticmethod
    def aggregate_sentiment(articles: List[NewsArticle]) -> Dict[str, Any]:
        """聚合一堆文章的情绪为整体指标

        Returns:
            {
                "score": float,        # 综合情绪分 [-1, +1]
                "label": str,           # "强烈看多" / "看多" / "中性" / "看空" / "强烈看空"
                "positive_ratio": float, # 正面文章占比
                "negative_ratio": float, # 负面文章占比
                "neutral_ratio": float,  # 中性文章占比
                "total_articles": int,
                "top_positive": [...],   # 最正面的文章 top 3
                "top_negative": [...],   # 最负面的文章 top 3
                "keyword_cloud": [...],  # 高频关键词（简化版）
            }
        """
        if not articles:
            return {
                "score": 0.0,
                "label": "无数据",
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "neutral_ratio": 1.0,
                "total_articles": 0,
                "top_positive": [],
                "top_negative": [],
                "keyword_cloud": [],
            }

        scores = [a.sentiment_score for a in articles]
        avg_score = round(sum(scores) / len(scores), 3)

        pos_count = sum(1 for s in scores if s > 0.1)
        neg_count = sum(1 for s in scores if s < -0.1)
        neu_count = len(scores) - pos_count - neg_count

        # 标签映射
        if avg_score > 0.4:
            label = "强烈看多"
        elif avg_score > 0.1:
            label = "偏多"
        elif avg_score >= -0.1:
            label = "中性"
        elif avg_score > -0.4:
            label = "偏空"
        else:
            label = "强烈看空"

        # Top positive/negative
        sorted_articles = sorted(articles, key=lambda a: a.sentiment_score, reverse=True)
        top_pos = [a.to_dict() for a in sorted_articles[:3] if a.sentiment_score > 0]
        top_neg = [a.to_dict() for a in sorted_articles[-3:] if a.sentiment_score < 0]
        top_neg.reverse()

        return {
            "score": avg_score,
            "label": label,
            "positive_ratio": round(pos_count / len(scores), 2),
            "negative_ratio": round(neg_count / len(scores), 2),
            "neutral_ratio": round(neu_count / len(scores), 2),
            "total_articles": len(articles),
            "top_positive": top_pos,
            "top_negative": top_neg,
            "keyword_cloud": [],  # 后续可扩展
        }
