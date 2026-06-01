# -*- coding: utf-8 -*-
"""技术面分析Agent"""

from typing import Dict, Any
from .base_agent import BaseAgent


class TechnicalAgent(BaseAgent):
    name = "技术面分析"
    agent_id = "technical_analysis"
    icon = "📈"
    description = "分析K线形态、技术指标和趋势信号"

    def get_system_prompt(self) -> str:
        return """你是一位专业的技术分析师，精通K线形态、技术指标和趋势判断。
你的任务是基于提供的技术指标数据，对股票的技术面进行深度分析。
要求：
1. 引用具体的技术指标数值
2. 明确指出支撑位和压力位
3. 给出明确的技术面评分（1-10分）和方向判断
4. 用中文回答，简洁专业
5. 最后用一句话总结技术面结论"""

    def build_user_prompt(self, data: Dict[str, Any]) -> str:
        symbol = data.get("symbol", "")
        profile = data.get("profile", {})
        tech = data.get("technical_indicators", {})
        quote = data.get("quote", {})
        financials = data.get("financials", {})
        data_notes = data.get("data_notes", "")

        notes_section = f"\n{data_notes}\n" if data_notes else ""

        ma_status = tech.get("ma_status", {})
        ma_text = "\n".join([
            f"  - {k}: {v.get('value')} (股价在其{'上方' if v.get('position')=='above' else '下方'}, 偏离{v.get('distance_pct')}%)"
            for k, v in ma_status.items()
        ]) if ma_status else "  无数据"

        prompt = f"""请分析 {symbol}（{profile.get('name', symbol)}）的技术面：
{notes_section}
当前价格: ${quote.get('price', 0)}

【均线系统】
{ma_text}

【RSI指标】
  - RSI(14): {tech.get('rsi', 'N/A')}
  - 信号: {tech.get('rsi_signal', 'N/A')}

【MACD指标】
  - MACD线: {tech.get('macd', {}).get('macd', 'N/A')}
  - 信号线: {tech.get('macd', {}).get('signal', 'N/A')}
  - 柱状图: {tech.get('macd', {}).get('histogram', 'N/A')}
  - 信号: {tech.get('macd_signal', 'N/A')}

【布林带】
  - 上轨: {tech.get('bollinger', {}).get('upper', 'N/A')}
  - 中轨: {tech.get('bollinger', {}).get('middle', 'N/A')}
  - 下轨: {tech.get('bollinger', {}).get('lower', 'N/A')}
  - 位置: {tech.get('bollinger_position', 'N/A')}

【趋势与量能】
  - 5日涨跌: {tech.get('trend_5d_pct', 'N/A')}%
  - 20日涨跌: {tech.get('trend_20d_pct', 'N/A')}%
  - 量比(5日/20日): {tech.get('volume_ratio', 'N/A')}
  - 量能信号: {tech.get('volume_signal', 'N/A')}
  - 20日最高: ${tech.get('recent_20d_high', 'N/A')}
  - 20日最低: ${tech.get('recent_20d_low', 'N/A')}

【52周数据】
  - 52周最高: ${financials.get('52w_high', 'N/A')}
  - 52周最低: ${financials.get('52w_low', 'N/A')}

请从以下维度分析：
1. **趋势判断**：当前处于上升/下降/震荡趋势
2. **均线分析**：多头/空头排列，金叉/死叉
3. **动量指标**：RSI/MACD综合信号
4. **支撑压力**：给出具体的支撑位和压力位价格
5. **技术面评分**：1-10分

结尾用【结论】标记一句话总结。"""
        return prompt
