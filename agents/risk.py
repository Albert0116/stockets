# -*- coding: utf-8 -*-
"""风险评估Agent"""

from typing import Dict, Any
from .base_agent import BaseAgent


class RiskAgent(BaseAgent):
    name = "风险评估"
    agent_id = "risk"
    icon = "⚠️"
    description = "评估估值风险、行业风险和下行风险"

    def get_system_prompt(self) -> str:
        return """你是一位风险管理专家，专注于识别和量化投资风险。
你的任务是全面评估该股票的各类风险因素。
要求：
1. 客观分析风险，不要过度乐观
2. 给出具体的风险等级和止损建议
3. 给出明确的风险评分（1-10分，10=风险极低/非常安全）
4. 用中文回答，简洁专业
5. 最后用一句话总结风险结论"""

    def build_user_prompt(self, data: Dict[str, Any]) -> str:
        symbol = data.get("symbol", "")
        profile = data.get("profile", {})
        quote = data.get("quote", {})
        financials = data.get("financials", {})
        tech = data.get("technical_indicators", {})
        data_notes = data.get("data_notes", "")

        notes_section = f"\n{data_notes}\n" if data_notes else ""

        price = quote.get("price", 0)
        high_52w = financials.get("52w_high", 0)
        low_52w = financials.get("52w_low", 0)

        # 计算离52周高低点距离
        dist_from_high = round((price - high_52w) / high_52w * 100, 2) if high_52w else "N/A"
        dist_from_low = round((price - low_52w) / low_52w * 100, 2) if low_52w else "N/A"

        prompt = f"""请评估 {symbol}（{profile.get('name', symbol)}）的投资风险：
{notes_section}
【价格位置】
  - 当前价格: ${price}
  - 52周最高: ${high_52w} (距最高{dist_from_high}%)
  - 52周最低: ${low_52w} (距最低+{dist_from_low}%)
  - 近5日涨跌: {tech.get('trend_5d_pct', 'N/A')}%
  - 近20日涨跌: {tech.get('trend_20d_pct', 'N/A')}%

【估值指标】
  - PE: {financials.get('pe_ratio', 'N/A')}
  - PB: {financials.get('pb_ratio', 'N/A')}
  - PS: {financials.get('ps_ratio', 'N/A')}
  - Beta: {financials.get('beta', 'N/A')}

【财务风险】
  - 负债权益比: {financials.get('debt_to_equity', 'N/A')}
  - 净利率: {financials.get('net_margin', 'N/A')}

【技术风险信号】
  - RSI: {tech.get('rsi', 'N/A')} ({tech.get('rsi_signal', '')})
  - 布林带位置: {tech.get('bollinger_position', 'N/A')}
  - MACD: {tech.get('macd_signal', 'N/A')}

【行业信息】
  - 行业: {profile.get('industry', 'N/A')}
  - 国家: {profile.get('country', 'N/A')}

请从以下维度评估风险：
1. **估值风险**：当前估值是否偏高，泡沫风险
2. **技术风险**：是否处于超买/追高位置
3. **财务风险**：杠杆率、盈利稳定性
4. **行业/宏观风险**：行业周期、政策风险
5. **下行空间**：最大可能回撤幅度
6. **止损建议**：给出具体止损价位
7. **风险评分**：1-10分（10=风险极低）

结尾用【结论】标记一句话总结。"""
        return prompt
