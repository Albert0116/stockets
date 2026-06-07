# -*- coding: utf-8 -*-
"""监控引擎 - 定时轮询行情并检查预警条件"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .conditions import check_alert_conditions
from .notifiers import notify

logger = logging.getLogger(__name__)


class MonitorEngine:
    """智能盯盘引擎 - 定时检查自选股行情并触发预警"""

    def __init__(self, finnhub_client, get_quote_fn=None):
        """
        Args:
            finnhub_client: finnhub SDK 客户端
            get_quote_fn: 获取行情的函数(symbol, market) -> dict
        """
        self.finnhub_client = finnhub_client
        self._get_quote_fn = get_quote_fn
        self.scheduler = AsyncIOScheduler()
        self._running = False
        # 防重复通知：{rule_id: last_trigger_time}
        self._cooldowns: Dict[int, float] = {}
        self._cooldown_seconds = 300  # 同一规则5分钟内不重复通知

    def start(self, interval_minutes: int = 5):
        """启动监控定时任务"""
        if self._running:
            return
        self.scheduler.add_job(
            self._check_all,
            IntervalTrigger(minutes=interval_minutes),
            id="monitor_check",
            replace_existing=True,
        )
        self.scheduler.start()
        self._running = True
        logger.info(f"监控引擎已启动，检查间隔: {interval_minutes}分钟")

    def stop(self):
        """停止监控"""
        if self._running:
            self.scheduler.shutdown(wait=False)
            self._running = False
            logger.info("监控引擎已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _check_all(self):
        """检查所有启用的预警规则"""
        # 延迟导入避免循环依赖
        from db import alert_list, alert_record_trigger, watchlist_list

        try:
            rules = await alert_list(enabled_only=True)
            if not rules:
                return

            # 按symbol分组避免重复获取行情
            symbol_rules: Dict[str, list] = {}
            for rule in rules:
                key = f"{rule['symbol']}:{rule['market']}"
                symbol_rules.setdefault(key, []).append(rule)

            for key, group_rules in symbol_rules.items():
                symbol, market = key.split(":", 1)
                quote = await self._fetch_quote(symbol, market)
                if not quote or quote.get("price", 0) <= 0:
                    continue

                for rule in group_rules:
                    # 检查冷却期
                    rule_id = rule["id"]
                    if self._in_cooldown(rule_id):
                        continue

                    message = check_alert_conditions(rule, quote)
                    if message:
                        logger.info(f"预警触发: {message}")
                        self._cooldowns[rule_id] = time.time()

                        # 记录到数据库
                        await alert_record_trigger(
                            rule_id=rule_id,
                            symbol=symbol,
                            message=message,
                            price=quote.get("price", 0)
                        )

                        # 发送通知
                        await notify(message, title=f"预警: {symbol}")

        except Exception as e:
            logger.error(f"监控检查异常: {e}", exc_info=True)

    async def _fetch_quote(self, symbol: str, market: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        try:
            if self._get_quote_fn:
                return await asyncio.to_thread(self._get_quote_fn, symbol, market)

            # 默认实现
            if market == "cn":
                return await self._fetch_cn_quote(symbol)
            else:
                return await self._fetch_us_quote(symbol)
        except Exception as e:
            logger.error(f"获取行情失败 {symbol}: {e}")
            return None

    async def _fetch_us_quote(self, symbol: str) -> Dict[str, Any]:
        """获取美股行情"""
        quote = await asyncio.to_thread(self.finnhub_client.quote, symbol)
        return {
            "price": quote.get("c", 0),
            "change_pct": quote.get("dp", 0),
            "volume": quote.get("v", 0) if "v" in quote else 0,
            "avg_volume": 0,
        }

    async def _fetch_cn_quote(self, symbol: str) -> Dict[str, Any]:
        """获取A股行情 - 新浪实时接口，单只获取"""
        import requests
        # 新浪格式: sh600519 / sz000001
        if symbol.startswith("6") or symbol.startswith("5") or symbol.startswith("9"):
            sina_sym = f"sh{symbol}"
        else:
            sina_sym = f"sz{symbol}"

        def _fetch():
            url = f"https://hq.sinajs.cn/list={sina_sym}"
            resp = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"},
                                timeout=5, proxies={"http": None, "https": None})
            resp.encoding = "gbk"
            text = resp.text
            if '=""' in text or not text.strip():
                return {}
            # 解析: var hq_str_sh600519="贵州茅台,开盘价,...";
            data_str = text.split('"')[1] if '"' in text else ""
            if not data_str:
                return {}
            parts = data_str.split(",")
            if len(parts) < 32:
                return {}
            return {
                "price": float(parts[3]) if parts[3] else 0,     # 当前价
                "change_pct": float(parts[32]) if len(parts) > 32 and parts[32] else
                    (round((float(parts[3]) - float(parts[2])) / float(parts[2]) * 100, 2)
                     if parts[3] and parts[2] and float(parts[2]) > 0 else 0),
                "volume": float(parts[8]) if len(parts) > 8 and parts[8] else 0,
                "avg_volume": 0,
            }

        return await asyncio.to_thread(_fetch)

    def _in_cooldown(self, rule_id: int) -> bool:
        """检查是否在冷却期内"""
        last = self._cooldowns.get(rule_id, 0)
        return (time.time() - last) < self._cooldown_seconds

    async def trigger_check_now(self):
        """手动立即触发一次检查"""
        await self._check_all()
