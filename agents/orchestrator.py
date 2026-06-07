# -*- coding: utf-8 -*-
"""多Agent编排器 - 并行执行分析Agent并流式输出"""

import asyncio
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, AsyncGenerator
from openai import OpenAI

from .data_collector import collect_stock_data
from .fundamental import FundamentalAgent
from .technical_agent import TechnicalAgent
from .sentiment import SentimentAgent
from .flow import FlowAgent
from .risk import RiskAgent
from .decision import DecisionAgent

# 全局线程池，5个agent并行
_executor = ThreadPoolExecutor(max_workers=5)


class MultiAgentOrchestrator:
    """编排6个分析Agent：前5个并行执行，决策Agent最后汇总"""

    def __init__(self, deepseek_client: OpenAI, finnhub_client):
        self.deepseek_client = deepseek_client
        self.finnhub_client = finnhub_client

        # 初始化所有Agent
        self.agents = [
            FundamentalAgent(deepseek_client),
            TechnicalAgent(deepseek_client),
            SentimentAgent(deepseek_client),
            FlowAgent(deepseek_client),
            RiskAgent(deepseek_client),
        ]
        self.decision_agent = DecisionAgent(deepseek_client)

    async def run_stream(self, symbol: str, market: str = "us") -> AsyncGenerator[str, None]:
        """
        运行所有Agent并流式输出SSE事件
        前5个Agent并行执行，完成后执行决策Agent
        """
        total_agents = len(self.agents) + 1
        start_time = time.time()

        # 1. 数据收集阶段
        yield self._event("status", {"message": "正在收集数据...", "phase": "data_collection"})

        try:
            data = await asyncio.to_thread(collect_stock_data, symbol, self.finnhub_client, market)
        except Exception as e:
            yield self._event("error", {"message": f"数据收集失败: {str(e)}"})
            return

        data_time = time.time() - start_time
        yield self._event("status", {
            "message": f"数据收集完成({data_time:.1f}s)，并行分析中...",
            "phase": "analysis"
        })

        # 2. 并行执行前5个Agent
        # P1-14: 每个 agent 的 chunks_list 是独立的 list 对象
        # CPython GIL 保证 list.append() 是原子操作，多线程写入安全
        # 轮询读取在 async 事件循环中进行，不会与线程池写入并发冲突
        agent_chunks: Dict[str, list] = {a.agent_id: [] for a in self.agents}
        agent_done_events: Dict[str, asyncio.Event] = {a.agent_id: asyncio.Event() for a in self.agents}
        agent_errors: Dict[str, str] = {}

        # 发送所有agent_start事件（同时开始）
        for idx, agent in enumerate(self.agents):
            yield self._event("agent_start", {
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "icon": agent.icon,
                "index": idx + 1,
                "total": total_agents,
                "parallel": True,
            })

        # 启动所有agent的并行任务
        loop = asyncio.get_event_loop()
        futures = []
        for agent in self.agents:
            future = loop.run_in_executor(
                _executor,
                self._run_agent_sync,
                agent,
                data,
                agent_chunks[agent.agent_id],
            )
            futures.append((agent, future))

        # 包装为asyncio tasks以便gather
        async def _wait_agent(agent, future):
            try:
                await future
            except Exception as e:
                agent_errors[agent.agent_id] = str(e)
            finally:
                agent_done_events[agent.agent_id].set()

        tasks = [asyncio.create_task(_wait_agent(a, f)) for a, f in futures]

        # 流式输出：轮询各agent的chunks列表
        read_positions = {a.agent_id: 0 for a in self.agents}
        done_agents = set()

        while len(done_agents) < len(self.agents):
            had_output = False
            for agent in self.agents:
                aid = agent.agent_id
                if aid in done_agents:
                    continue

                chunks = agent_chunks[aid]
                pos = read_positions[aid]

                # 读取新的chunks
                if pos < len(chunks):
                    # 批量发送积累的chunks以减少SSE消息数
                    new_chunks = chunks[pos:]
                    batch_text = "".join(new_chunks)
                    if batch_text:
                        yield self._event("text", {
                            "agent_id": aid,
                            "text": batch_text,
                        })
                    read_positions[aid] = len(chunks)
                    had_output = True

                # 检查是否完成
                if agent_done_events[aid].is_set() and read_positions[aid] >= len(chunks):
                    done_agents.add(aid)
                    # 发送错误或完成事件
                    if aid in agent_errors:
                        yield self._event("text", {
                            "agent_id": aid,
                            "text": f"\n\n⚠️ 分析出错: {agent_errors[aid]}",
                        })
                    output = agent.get_last_output()
                    summary = self._extract_summary(output)
                    yield self._event("agent_done", {
                        "agent_id": aid,
                        "summary": summary,
                    })
                    had_output = True

            if not had_output:
                await asyncio.sleep(0.05)

        # 确保所有任务完成
        await asyncio.gather(*tasks, return_exceptions=True)

        analysis_time = time.time() - start_time - data_time
        yield self._event("status", {
            "message": f"并行分析完成({analysis_time:.1f}s)，生成决策...",
            "phase": "decision"
        })

        # 3. 执行综合决策Agent
        agent_outputs = []
        for agent in self.agents:
            agent_outputs.append({
                "name": agent.name,
                "agent_id": agent.agent_id,
                "output": agent.get_last_output(),
            })

        yield self._event("agent_start", {
            "agent_id": self.decision_agent.agent_id,
            "agent_name": self.decision_agent.name,
            "icon": self.decision_agent.icon,
            "index": total_agents,
            "total": total_agents,
        })

        try:
            async for chunk in self.decision_agent.run_stream(data, agent_outputs):
                yield self._event("text", {
                    "agent_id": self.decision_agent.agent_id,
                    "text": chunk,
                })
        except Exception as e:
            yield self._event("text", {
                "agent_id": self.decision_agent.agent_id,
                "text": f"\n\n⚠️ 决策分析出错: {str(e)}",
            })

        # 解析决策结果
        decision_output = self.decision_agent.get_last_output()
        decision_data = self._parse_decision(decision_output)

        yield self._event("agent_done", {
            "agent_id": self.decision_agent.agent_id,
            "summary": decision_data.get("core_logic", "综合研判完成"),
        })

        # 发送决策结果（含总耗时）
        total_time = time.time() - start_time
        decision_data["total_time"] = f"{total_time:.1f}s"
        yield self._event("decision", decision_data)

    def _run_agent_sync(self, agent, data: Dict[str, Any], chunks_list: list):
        """同步执行agent的LLM调用（在线程池中运行）"""
        system_prompt = agent.get_system_prompt()
        user_prompt = agent.build_user_prompt(data)

        stream = agent.client.chat.completions.create(
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
                chunks_list.append(delta)

        agent._last_output = full_text

    def _event(self, event_type: str, payload: Dict[str, Any]) -> str:
        """生成SSE事件字符串"""
        payload["type"] = event_type
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _extract_summary(self, text: str) -> str:
        """从Agent输出中提取结论摘要"""
        match = re.search(r'【结论】[：:]*\s*(.+?)(?:\n|$)', text)
        if match:
            return match.group(1).strip()
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        return lines[-1][:100] if lines else "分析完成"

    def _parse_decision(self, text: str) -> Dict[str, Any]:
        """解析决策Agent输出中的结构化数据"""
        result = {
            "rating": "持有",
            "confidence": 5,
            "target_price": "",
            "stop_loss": "",
            "time_horizon": "",
            "core_logic": "",
            "operation_plan": {
                "entry_strategy": "",
                "position_sizing": "",
                "take_profit": "",
                "time_stop": "",
            },
        }

        # 查找```decision代码块
        match = re.search(r'```decision\s*\n(.*?)\n```', text, re.DOTALL)
        if match:
            block = match.group(1)
            for line in block.strip().split('\n'):
                line = line.strip()
                val = ""
                if ":" in line:
                    val = line.split(":", 1)[-1].strip()
                elif "：" in line:
                    val = line.split("：", 1)[-1].strip()
                else:
                    continue

                if line.startswith("评级"):
                    if val in ["买入", "增持", "持有", "减持", "卖出"]:
                        result["rating"] = val
                elif line.startswith("信心指数"):
                    try:
                        result["confidence"] = int(re.search(r'\d+', val).group())
                    except:
                        pass
                elif line.startswith("目标价"):
                    result["target_price"] = val
                elif line.startswith("止损价"):
                    result["stop_loss"] = val
                elif line.startswith("时间周期"):
                    result["time_horizon"] = val
                elif line.startswith("核心逻辑"):
                    result["core_logic"] = val
                elif line.startswith("入场策略"):
                    result["operation_plan"]["entry_strategy"] = val
                elif line.startswith("仓位管理"):
                    result["operation_plan"]["position_sizing"] = val
                elif line.startswith("止盈计划"):
                    result["operation_plan"]["take_profit"] = val
                elif line.startswith("时间止损"):
                    result["operation_plan"]["time_stop"] = val

        return result
