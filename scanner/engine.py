# -*- coding: utf-8 -*-
"""扫描引擎 - 两阶段选股：数据过滤(0 tokens) -> AI评估(仅top候选)"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

import akshare as ak
from openai import OpenAI

from .strategies import BUILTIN_STRATEGIES
from db import scan_save, scan_get_latest

logger = logging.getLogger(__name__)


class ScannerEngine:
    """自动选股扫描引擎"""

    def __init__(self, deepseek_client: Optional[OpenAI] = None):
        self.deepseek_client = deepseek_client

    async def scan(self, strategy_name: str, use_ai: bool = False, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        执行扫描
        Args:
            strategy_name: 策略名称
            use_ai: 是否用AI对top候选做二次评估
            top_n: 最终返回的股票数
        Returns:
            候选股票列表 [{"symbol", "name", "market", "score", "reason"}]
        """
        if strategy_name not in BUILTIN_STRATEGIES:
            raise ValueError(f"未知策略: {strategy_name}，可用: {list(BUILTIN_STRATEGIES.keys())}")

        strategy = BUILTIN_STRATEGIES[strategy_name]
        filter_fn = strategy["filter_fn"]
        market = strategy.get("market", "cn")

        # Phase 1: 数据层筛选（0 tokens消耗）
        logger.info(f"扫描策略 [{strategy['name']}] 开始数据筛选...")
        start = time.time()

        try:
            if market == "cn":
                df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
            else:
                raise NotImplementedError("暂只支持A股扫描")
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return []

        candidates_df = await asyncio.to_thread(filter_fn, df)
        filter_time = time.time() - start
        logger.info(f"数据筛选完成: {len(candidates_df)} 只候选, 耗时 {filter_time:.1f}s")

        if candidates_df.empty:
            return []

        # 构造结果
        results = []
        for _, row in candidates_df.iterrows():
            results.append({
                "symbol": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "market": market,
                "price": float(row.get("最新价", 0)),
                "change_pct": float(row.get("涨跌幅", 0)),
                "volume_ratio": float(row.get("量比", 0)),
                "turnover": float(row.get("换手率", 0)),
                "score": 0,
                "reason": "",
            })

        # Phase 2: AI评估（可选，仅对top候选）
        if use_ai and self.deepseek_client and results:
            ai_top = results[:min(5, len(results))]  # 最多5只用AI评估
            logger.info(f"AI评估 {len(ai_top)} 只候选...")
            ai_results = await self._ai_evaluate(ai_top, strategy)
            # 合并AI评分
            ai_map = {r["symbol"]: r for r in ai_results}
            for item in results:
                if item["symbol"] in ai_map:
                    item["score"] = ai_map[item["symbol"]].get("score", 0)
                    item["reason"] = ai_map[item["symbol"]].get("reason", "")

            results.sort(key=lambda x: x["score"], reverse=True)

        results = results[:top_n]

        # 保存到数据库
        await scan_save(strategy_name, results)

        return results

    async def _ai_evaluate(self, candidates: List[Dict[str, Any]], strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """用AI对候选做简要评估"""
        if not self.deepseek_client:
            return candidates

        stocks_info = "\n".join([
            f"- {c['symbol']} {c['name']}: 价格{c['price']}, 涨幅{c['change_pct']:.1f}%, 量比{c['volume_ratio']:.1f}, 换手{c['turnover']:.1f}%"
            for c in candidates
        ])

        prompt = f"""你是一位量化分析师。以下是通过「{strategy['name']}」策略（{strategy['description']}）筛选出的候选股票：

{stocks_info}

请对每只股票打分(1-10)并给出一句话理由。注意排除ST、次新股等风险标的。
输出格式(每行一只):
代码|分数|理由

例如:
600519|8|白酒龙头放量突破前高，资金关注度高"""

        try:
            resp = await asyncio.to_thread(
                self.deepseek_client.chat.completions.create,
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )
            text = resp.choices[0].message.content
            results = []
            for line in text.strip().split("\n"):
                parts = line.strip().split("|")
                if len(parts) >= 3:
                    results.append({
                        "symbol": parts[0].strip(),
                        "score": int(parts[1].strip()) if parts[1].strip().isdigit() else 5,
                        "reason": parts[2].strip(),
                    })
            return results
        except Exception as e:
            logger.error(f"AI评估失败: {e}")
            return candidates

    async def batch_scan(self, strategy_names: List[str], top_n: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        批量执行多个策略扫描（共享一次数据拉取）
        Returns:
            {"strategy_name": [results], ...}
        """
        valid_names = [n for n in strategy_names if n in BUILTIN_STRATEGIES]
        if not valid_names:
            return {}

        # 一次拉取市场数据
        logger.info(f"批量扫描 {len(valid_names)} 个策略，拉取全市场数据...")
        try:
            df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return {}

        results = {}
        for name in valid_names:
            strategy = BUILTIN_STRATEGIES[name]
            filter_fn = strategy["filter_fn"]
            candidates_df = await asyncio.to_thread(filter_fn, df)
            strategy_results = []
            for _, row in candidates_df.head(top_n).iterrows():
                strategy_results.append({
                    "symbol": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "market": strategy.get("market", "cn"),
                    "price": float(row.get("最新价", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "volume_ratio": float(row.get("量比", 0)),
                    "turnover": float(row.get("换手率", 0)),
                    "score": 0,
                    "reason": "",
                })
            results[name] = strategy_results
            await scan_save(name, strategy_results)
            logger.info(f"  策略 [{strategy['name']}]: {len(strategy_results)} 只候选")

        return results

    async def get_strategies(self) -> List[Dict[str, str]]:
        """获取所有可用策略"""
        return [
            {"id": k, "name": v["name"], "description": v["description"], "market": v.get("market", "cn")}
            for k, v in BUILTIN_STRATEGIES.items()
        ]
