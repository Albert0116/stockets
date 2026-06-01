# -*- coding: utf-8 -*-
"""基本面分析Agent"""

from typing import Dict, Any
from .base_agent import BaseAgent


class FundamentalAgent(BaseAgent):
    name = "基本面分析"
    agent_id = "fundamental"
    icon = "📊"
    description = "分析公司财务指标、盈利能力和估值水平"

    def get_system_prompt(self) -> str:
        return """你是一位资深的基本面分析师，专注于公司财务数据分析。
你的任务是基于提供的财务数据，对公司的基本面进行深度分析。
要求：
1. 分析要具体，引用实际数据
2. 如果数据缺失，请根据提示说明具体原因（如ETF产品本身没有PE/PB），不要简单说"暂无数据"
3. 如果是ETF，关注费率、规模(AUM)、流动性等特有指标
4. 给出明确的基本面评分（1-10分）
5. 用中文回答，简洁专业
6. 最后用一句话总结基本面结论"""

    def build_user_prompt(self, data: Dict[str, Any]) -> str:
        symbol = data.get("symbol", "")
        profile = data.get("profile", {})
        financials = data.get("financials", {})
        quote = data.get("quote", {})
        data_notes = data.get("data_notes", "")

        notes_section = f"\n{data_notes}\n" if data_notes else ""

        prompt = f"""请分析 {symbol}（{profile.get('name', symbol)}）的基本面：
{notes_section}
{self.format_data_section("公司概况", {
    "行业": profile.get("industry"),
    "市值(百万美元)": profile.get("market_cap"),
    "上市交易所": profile.get("exchange"),
    "IPO日期": profile.get("ipo"),
})}

{self.format_data_section("财务指标", {
    "市盈率(PE)": financials.get("pe_ratio"),
    "市净率(PB)": financials.get("pb_ratio"),
    "市销率(PS)": financials.get("ps_ratio"),
    "ROE(净资产收益率)": financials.get("roe"),
    "ROA(总资产收益率)": financials.get("roa"),
    "EPS(每股收益TTM)": financials.get("eps_ttm"),
    "营收增长率(YoY)": financials.get("revenue_growth"),
    "净利率": financials.get("net_margin"),
    "负债权益比": financials.get("debt_to_equity"),
    "股息率": financials.get("dividend_yield"),
    "Beta系数": financials.get("beta"),
})}

当前股价: ${quote.get('price', 0)}，今日涨跌: {quote.get('change_pct', 0):.2f}%

请从以下维度分析：
1. **估值水平**：PE/PB/PS是否合理，与行业对比
2. **盈利能力**：ROE/净利率/EPS趋势
3. **成长性**：营收增长是否强劲
4. **财务健康**：负债率、现金流状况
5. **基本面评分**：1-10分，并说明理由

结尾用【结论】标记一句话总结。"""
        return prompt
