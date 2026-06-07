# -*- coding: utf-8 -*-
"""消息面分析Agent"""

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
你的任务是基于提供的新闻和分析师推荐数据，分析当前的市场情绪。
要求：
1. 分析新闻的正面/负面倾向
2. 解读分析师推荐变化
3. 给出明确的情绪评分（1-10分，10=极度看多）
4. 用中文回答，简洁专业
5. 最后用一句话总结情绪结论"""

    def build_user_prompt(self, data: Dict[str, Any]) -> str:
        symbol = data.get("symbol", "")
        profile = data.get("profile", {})
        news = data.get("news", [])
        recs = data.get("recommendations", {})

        # 格式化新闻
        news_text = ""
        for n in news[:8]:
            dt = datetime.fromtimestamp(n.get("datetime", 0)).strftime("%m-%d") if n.get("datetime") else ""
            news_text += f"  - [{dt}] {n.get('headline', '')} ({n.get('source', '')})\n"

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

        prompt = f"""请分析 {symbol}（{profile.get('name', symbol)}）的消息面和市场情绪：

【近期新闻】
{news_text}

【分析师推荐】
{rec_text}

【同行公司】
  {', '.join(data.get('peers', [])[:5]) or '暂无数据'}

请从以下维度分析：
1. **新闻情绪**：近期新闻整体偏正面还是负面，有无重大事件
2. **分析师观点**：华尔街分析师的共识方向
3. **市场热度**：当前市场对该股的关注程度
4. **催化剂**：是否有即将到来的催化事件（财报、新品发布等）
5. **情绪评分**：1-10分（10=极度看多）

结尾用【结论】标记一句话总结。"""
        return prompt
