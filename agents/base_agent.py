# -*- coding: utf-8 -*-
"""Agent基类"""

import json
from typing import Dict, Any, AsyncGenerator
from openai import OpenAI


class BaseAgent:
    """所有分析Agent的基类"""

    name: str = "Base Agent"
    agent_id: str = "base"
    icon: str = "🤖"
    description: str = ""

    def __init__(self, deepseek_client: OpenAI):
        self.client = deepseek_client

    def get_system_prompt(self) -> str:
        """返回Agent的系统提示词"""
        raise NotImplementedError

    def build_user_prompt(self, data: Dict[str, Any]) -> str:
        """根据数据构建用户提示词"""
        raise NotImplementedError

    async def run_stream(self, data: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """流式执行分析，生成文本块"""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(data)

        stream = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            max_tokens=1500,
            temperature=0.3,
        )

        full_text = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_text += delta
                yield delta

        # Store the full output for later use by DecisionAgent
        self._last_output = full_text

    def get_last_output(self) -> str:
        """获取最后一次运行的完整输出"""
        return getattr(self, "_last_output", "")

    def format_data_section(self, title: str, data: Any) -> str:
        """格式化数据段为提示词"""
        if isinstance(data, dict):
            lines = [f"【{title}】"]
            for k, v in data.items():
                if v is not None and v != "" and v != 0:
                    lines.append(f"  - {k}: {v}")
            return "\n".join(lines)
        elif isinstance(data, list):
            lines = [f"【{title}】"]
            for item in data[:5]:
                if isinstance(item, dict):
                    lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
                else:
                    lines.append(f"  - {item}")
            return "\n".join(lines)
        return f"【{title}】\n  {data}"
