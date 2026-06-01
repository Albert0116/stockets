# -*- coding: utf-8 -*-
"""综合决策Agent - 汇总所有分析给出最终建议"""

from typing import Dict, Any, List
from .base_agent import BaseAgent


class DecisionAgent(BaseAgent):
    name = "综合决策"
    agent_id = "decision"
    icon = "🎯"
    description = "综合所有分析维度，给出最终投资决策"

    def get_system_prompt(self) -> str:
        return """你是一位首席投资策略师，负责综合多维度分析给出最终投资决策和可执行的操作计划。
你将收到来自5位分析师的报告：基本面、技术面、消息面、资金面、风险评估。

你的任务是：
1. 综合所有维度的分析，权衡各维度的信号强弱
2. 给出明确的投资决策
3. 提供具体可执行的操作计划（入场策略、仓位管理、止盈计划、时间止损）

**输出格式要求（严格遵循）：**
先给出分析，然后在最后必须包含以下结构化数据块（用```decision标记）：

```decision
评级: [买入/增持/持有/减持/卖出]
信心指数: [1-10的整数]
目标价: [$xxx-$xxx]
止损价: [$xxx]
时间周期: [x个月]
核心逻辑: [一句话总结]
入场策略: [具体描述何时、以什么价位/条件入场]
仓位管理: [建议仓位比例和加减仓策略]
止盈计划: [分批止盈的具体价位和比例]
时间止损: [如果多久内未达预期应如何处理]
```

注意：
- 评级只能从"买入/增持/持有/减持/卖出"中选择一个
- 操作计划要具体可执行，不要笼统建议
- 入场策略要结合技术面给出具体价位或信号条件
- 仓位管理要给出百分比，如"总仓位20%，分2次建仓"
- 止盈计划要分阶梯，如"第一目标减仓50%，第二目标全部离场"
- 时间止损给出明确时限，如"3周内未突破则减仓50%"
"""

    def build_user_prompt(self, data: Dict[str, Any], agent_outputs: List[Dict[str, str]] = None) -> str:
        symbol = data.get("symbol", "")
        profile = data.get("profile", {})
        quote = data.get("quote", {})
        data_notes = data.get("data_notes", "")

        notes_section = f"\n{data_notes}\n" if data_notes else ""

        # 汇总各Agent的输出
        outputs_text = ""
        if agent_outputs:
            for ao in agent_outputs:
                outputs_text += f"\n{'='*40}\n"
                outputs_text += f"【{ao['name']}分析师报告】\n"
                outputs_text += ao["output"]
                outputs_text += "\n"

        prompt = f"""请综合以下5位分析师的报告，对 {symbol}（{profile.get('name', symbol)}）做出最终投资决策：
{notes_section}
当前价格: ${quote.get('price', 0)}
今日涨跌: {quote.get('change_pct', 0):.2f}%
行业: {profile.get('industry', 'N/A')}
市值: {profile.get('market_cap', 0):.0f}百万美元

{outputs_text}

{'='*40}

请进行最终综合研判：
1. **多空力量对比**：各维度看多vs看空的权重
2. **关键矛盾**：各维度分析之间是否存在矛盾信号
3. **决策依据**：你做出决策的核心逻辑
4. **操作计划**：具体可执行的入场/出场方案
5. **最终评级和结构化数据**（必须包含```decision代码块，含操作计划4个字段）"""
        return prompt

    async def run_stream(self, data: Dict[str, Any], agent_outputs: List[Dict[str, str]] = None):
        """重写run_stream以接受agent_outputs参数"""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(data, agent_outputs)

        stream = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            max_tokens=2500,
            temperature=0.2,
        )

        full_text = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_text += delta
                yield delta

        self._last_output = full_text
