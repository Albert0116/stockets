# -*- coding: utf-8 -*-
"""消息面分析Agent —— 集成多源舆情引擎"""

import json
from datetime import datetime
from typing import Dict, Any
from .base_agent import BaseAgent


class SentimentAgent(BaseAgent):
    name = "消息面分析"
    agent_id = "sentiment"
    icon = "📰"
    description = "分析新闻情绪、分析师推荐和市场热度"

    def get_system_prompt(self) -> str:
        return """你是一位市场情绪分析专家，擅长从新闻、分析师观点中判断市场情绪。
你的任务是基于提供的新闻、关键词情绪打分和分析师推荐数据，分析当前的市场情绪。

输入说明:
- 【关键词情绪预判】: 由算法对新闻标题进行关键词匹配得出的情绪分数 (-1到+1)，仅作参考
- 【近期新闻】: 原始新闻标题列表，含来源和时间
- 【分析师推荐】: 分析师共识数据

要求：
1. 结合预判分数和实际新闻内容，综合判断情绪
2. 解读分析师推荐变化
3. 给出明确的情绪评分（1-10分，10=极度看多）
4. 用中文回答，简洁专业
5. 最后用一句话总结情绪结论"""

    def build_user_prompt(self, data: Dict[str, Any]) -> str:
        symbol = data.get("symbol", "")
        profile = data.get("profile", {})
        news = data.get("news", [])
        recs = data.get("recommendations", {})
        sentiment_pre = data.get("sentiment_pre_analysis", {})

        # 格式化新闻（含情绪标签）
        news_text = ""
        for i, n in enumerate(news[:12]):
            dt = datetime.fromtimestamp(n.get("datetime", 0)).strftime("%m-%d") if n.get("datetime") else ""
            score = n.get("sentiment_score", 0)
            tag = "🔴" if score < -0.2 else ("🟢" if score > 0.2 else "⚪")
            news_text += f"  - [{dt}] {tag} {n.get('headline', '')} ({n.get('source', '')})\n"

        if not news_text:
            news_text = "  暂无近期新闻"

        # 格式化推荐
        rec_text = "暂无数据"
        if recs:
            total = recs.get("strong_buy", 0) + recs.get("buy", 0) + recs.get("hold", 0) + recs.get("sell", 0) + recs.get("strong_sell", 0)
            rec_text = f"""  期间: {recs.get('period', 'N/A')}
  强力买入: {recs.get('strong_buy', 0)}
  买入: {recs.get('buy', 0)}
  持有: {recs.get('hold', 0)}
  卖出: {recs.get('sell', 0)}
  强力卖出: {recs.get('strong_sell', 0)}
  总分析师数: {total}"""

        # 关键词情绪预判
        pre_text = "暂无"
        if sentiment_pre:
            pre_text = f"""  综合评分: {sentiment_pre.get('score', 0):+.2f} ({sentiment_pre.get('label', 'N/A')})
  正面占比: {sentiment_pre.get('positive_ratio', 0):.0%}
  负面占比: {sentiment_pre.get('negative_ratio', 0):.0%}
  分析文章数: {sentiment_pre.get('total_articles', 0)}
  预判摘要: {sentiment_pre.get('summary', '')}"""

        prompt = f"""请分析 {symbol}（{profile.get('name', symbol)}）的消息面和市场情绪：

【关键词情绪预判】（算法初步打分，仅供参考）
{pre_text}

【近期新闻】
{news_text}

【分析师推荐】
{rec_text}

【同行公司】
  {', '.join(data.get('peers', [])[:5]) or '暂无数据'}

请从以下维度分析：
1. **新闻情绪**：结合预判和标题，近期新闻整体偏正面还是负面，有无重大事件
2. **分析师观点**：华尔街分析师的共识方向
3. **市场热度**：当前市场对该股的关注程度
4. **催化剂**：是否有即将到来的催化事件（财报、新品发布等）
5. **情绪评分**：1-10分（10=极度看多）

结尾用【结论】标记一句话总结。"""
        return prompt
