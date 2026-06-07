# -*- coding: utf-8 -*-
"""资金面分析Agent"""

import json
from typing import Dict, Any
from .base_agent import BaseAgent


class FlowAgent(BaseAgent):
    name = "资金面分析"
    agent_id = "flow"
    icon = "💰"
    description = "分析机构持仓变化、内部人交易和资金流向"

    def get_system_prompt(self) -> str:
        return """你是一位资金流向分析专家，擅长从机构持仓和内部人交易中判断聪明钱的动向。
你的任务是基于提供的持仓和交易数据，分析资金面状况。
要求：
1. 分析机构增减持趋势
2. 解读内部人交易的信号意义
3. 如果数据为空，请根据提示说明原因（如ETF无内部人交易、API限制等），而非简单说"暂无数据"
4. 给出明确的资金面评分（1-10分，10=大量资金流入）
5. 用中文回答，简洁专业
6. 最后用一句话总结资金面结论"""

    def build_user_prompt(self, data: Dict[str, Any]) -> str:
        symbol = data.get("symbol", "")
        profile = data.get("profile", {})
        holders = data.get("institutional_holders", [])
        insider = data.get("insider_transactions", [])
        tech = data.get("technical_indicators", {})
        data_notes = data.get("data_notes", "")

        notes_section = f"\n{data_notes}\n" if data_notes else ""

        # 格式化机构持仓
        holder_text = ""
        for h in holders[:6]:
            change_str = f"+{h['change']}" if h.get("change", 0) > 0 else str(h.get("change", 0))
            holder_text += f"  - {h.get('name', 'Unknown')}: 持股{h.get('share', 0):,}股, 占比{h.get('pct', 0):.2f}%, 变动{change_str}\n"
        if not holder_text:
            holder_text = "  暂无机构持仓数据"

        # 格式化内部人交易
        insider_text = ""
        for t in insider[:6]:
            insider_text += f"  - {t.get('name', 'Unknown')}: {t.get('transaction_type', '')} {t.get('change', 0):,}股 ({t.get('filing_date', '')})\n"
        if not insider_text:
            insider_text = "  暂无近期内部人交易数据"

        prompt = f"""请分析 {symbol}（{profile.get('name', symbol)}）的资金面：
{notes_section}
【机构持仓 Top Holders】
{holder_text}

【内部人交易（近期）】
{insider_text}

【成交量数据】
  - 量比(5日均量/20日均量): {tech.get('volume_ratio', 'N/A')}
  - 量能信号: {tech.get('volume_signal', 'N/A')}
  - 10日平均成交量: {data.get('financials', {}).get('10d_avg_volume', 'N/A')}百万股
  - 3月平均成交量: {data.get('financials', {}).get('3m_avg_volume', 'N/A')}百万股

【流通股数】
  - 总流通股: {profile.get('share_outstanding', 'N/A')}百万股

请从以下维度分析：
1. **机构动向**：主要机构是在增持还是减持
2. **内部人信号**：管理层/董事的交易行为暗示什么
3. **量价配合**：成交量变化是否配合价格走势
4. **资金面评分**：1-10分（10=大量聪明钱流入）

结尾用【结论】标记一句话总结。"""
        return prompt
