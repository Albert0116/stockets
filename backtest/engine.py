# -*- coding: utf-8 -*-
"""量化回测引擎

设计原则:
    1. 数据源与策略解耦 —— 接受标准 OHLC 字典列表，不强制使用特定数据源
    2. 结果结构化 —— 返回 BacktestResult，方便前端渲染
    3. 策略可插拔 —— 内置 + 自定义 + AI 生成
    4. 兼容 A股/美股 —— 无需区分市场，只需传入 candles
"""

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Type

import backtrader as bt

from .strategies import STRATEGY_REGISTRY


@dataclass
class TradeRecord:
    """单笔交易记录"""
    date: str
    action: str  # "买入" / "卖出"
    price: float
    size: int
    value: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0


@dataclass
class BacktestResult:
    """回测结果"""
    symbol: str
    strategy_name: str
    strategy_key: str
    params: Dict[str, Any] = field(default_factory=dict)

    # 收益指标
    initial_cash: float = 100000.0
    final_value: float = 100000.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annual_return_pct: float = 0.0

    # 风险指标
    max_drawdown_pct: float = 0.0
    max_drawdown_duration: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate_pct: float = 0.0
    profit_factor: float = 0.0

    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    avg_holding_days: float = 0.0

    # 基准对比
    buy_hold_return_pct: float = 0.0
    alpha_vs_hold: float = 0.0

    # 交易明细
    trades: List[TradeRecord] = field(default_factory=list)

    # 权益曲线
    equity_curve: List[Dict[str, float]] = field(default_factory=list)
    buy_hold_curve: List[Dict[str, float]] = field(default_factory=list)

    # 元信息
    data_start: str = ""
    data_end: str = ""
    data_days: int = 0
    run_time_ms: float = 0.0
    error: str = ""

    @property
    def is_profitable(self) -> bool:
        return self.total_return_pct > 0

    def summary_dict(self) -> Dict[str, Any]:
        """精简摘要，适合前端展示"""
        return {
            "symbol": self.symbol,
            "strategy": self.strategy_name,
            "total_return_pct": round(self.total_return_pct, 2),
            "annual_return_pct": round(self.annual_return_pct, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "win_rate_pct": round(self.win_rate_pct, 1),
            "profit_factor": round(self.profit_factor, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_win_pct": round(self.avg_win_pct, 2),
            "avg_loss_pct": round(self.avg_loss_pct, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
            "buy_hold_return_pct": round(self.buy_hold_return_pct, 2),
            "vs_buy_hold": round(self.alpha_vs_hold, 2),
            "final_value": round(self.final_value, 2),
            "total_return": round(self.total_return, 2),
            "initial_cash": round(self.initial_cash, 2),
            "data_start": self.data_start,
            "data_end": self.data_end,
            "data_days": self.data_days,
            "run_time_ms": round(self.run_time_ms, 0),
            "trades": [
                {
                    "date": t.date,
                    "action": t.action,
                    "price": t.price,
                    "size": t.size,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "holding_days": t.holding_days,
                }
                for t in self.trades
            ],
            "equity_curve": self.equity_curve,
            "buy_hold_curve": self.buy_hold_curve,
            "error": self.error,
        }


class _PandasDataFeed(bt.feeds.PandasData):
    """将标准 candle dict list 转为 backtrader 可用格式"""
    params = (
        ("datetime", None),  # 使用 DataFrame index
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("close", "close"),
        ("volume", "volume"),
        ("openinterest", -1),
    )


class BacktestEngine:
    """回测引擎 —— 封装 backtrader.Cerebro，提供简洁 API"""

    def __init__(self):
        pass

    # ─── 公开 API ─────────────────────────────────────────

    def run(
        self,
        symbol: str,
        candles: List[Dict[str, Any]],
        strategy_key: str = "sma_cross",
        strategy_class: Optional[Type[bt.Strategy]] = None,
        params: Optional[Dict[str, Any]] = None,
        initial_cash: float = 100000.0,
        commission: float = 0.0003,  # 默认万三佣金
    ) -> BacktestResult:
        """运行回测

        Args:
            symbol: 股票代码
            candles: OHLC 数据列表 [{"date","open","high","low","close","volume"},...]
            strategy_key: 内置策略ID (sma_cross / macd / rsi_reversal / bollinger_bounce)
            strategy_class: 自定义策略类 (优先级高于 strategy_key)
            params: 策略参数 (覆盖默认值)
            initial_cash: 初始资金
            commission: 佣金费率

        Returns:
            BacktestResult
        """
        t0 = datetime.now()

        result = BacktestResult(
            symbol=symbol,
            strategy_name="",
            strategy_key=strategy_key,
            initial_cash=initial_cash,
            final_value=initial_cash,
        )

        if not candles or len(candles) < 50:
            result.error = "K线数据不足（至少需要50根K线）"
            return result

        # 确定策略
        if strategy_class is None:
            entry = STRATEGY_REGISTRY.get(strategy_key)
            if entry is None:
                result.error = f"未知策略: {strategy_key}，可用: {list(STRATEGY_REGISTRY.keys())}"
                return result
            strategy_class = entry["class"]
            result.strategy_name = entry["name"]
            merged_params = {**entry["params"], **(params or {})}
        else:
            result.strategy_name = strategy_class.__name__
            merged_params = params or {}

        result.params = merged_params

        # 填充元信息
        result.data_start = str(candles[0].get("date", ""))
        result.data_end = str(candles[-1].get("date", ""))
        result.data_days = len(candles)

        # 计算 Buy & Hold 基准
        first_close = candles[0].get("close", 0)
        last_close = candles[-1].get("close", 0)
        if first_close > 0:
            result.buy_hold_return_pct = round((last_close - first_close) / first_close * 100, 2)

        # 构建 backtrader 数据
        import pandas as pd
        df = pd.DataFrame(candles)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
        df.sort_index(inplace=True)
        data_feed = _PandasDataFeed(dataname=df)

        # 初始化 Cerebro
        cerebro = bt.Cerebro()
        cerebro.adddata(data_feed)
        cerebro.addstrategy(strategy_class, **merged_params)
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=commission)

        # 添加分析器
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe",
                            riskfreerate=0.02, annualize=True)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
        cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")

        # 执行
        try:
            results = cerebro.run()
        except Exception as e:
            result.error = f"回测执行失败: {str(e)}"
            return result

        strat = results[0]

        # ─── 提取结果 ───────────────────────────────────
        result.final_value = round(cerebro.broker.getvalue(), 2)
        net_pnl = result.final_value - initial_cash
        result.total_return = round(net_pnl, 2)
        result.total_return_pct = round(net_pnl / initial_cash * 100, 2)
        result.alpha_vs_hold = round(result.total_return_pct - result.buy_hold_return_pct, 2)

        # 年化收益（使用实际日历天数）
        try:
            d_start = datetime.strptime(result.data_start[:10], "%Y-%m-%d")
            d_end = datetime.strptime(result.data_end[:10], "%Y-%m-%d")
            actual_days = max((d_end - d_start).days, 1)
        except (ValueError, TypeError):
            actual_days = max(result.data_days, 1)
        years = actual_days / 365.25
        if years > 0 and result.final_value > 0:
            result.annual_return_pct = round(
                ((result.final_value / initial_cash) ** (1 / years) - 1) * 100, 2
            )

        # 夏普比率
        sharpe = strat.analyzers.sharpe.get_analysis()
        result.sharpe_ratio = round(sharpe.get("sharperatio", 0.0) or 0.0, 2)

        # 回撤
        dd = strat.analyzers.drawdown.get_analysis()
        result.max_drawdown_pct = round(dd.get("max", {}).get("drawdown", 0.0), 2)
        result.max_drawdown_duration = dd.get("max", {}).get("len", 0)

        # 卡玛比率
        if result.max_drawdown_pct > 0:
            result.calmar_ratio = round(result.annual_return_pct / abs(result.max_drawdown_pct), 2)

        # 交易分析
        ta = strat.analyzers.trades.get_analysis()
        result.total_trades = ta.get("total", {}).get("total", 0) or 0
        result.winning_trades = ta.get("won", {}).get("total", 0) or 0
        result.losing_trades = ta.get("lost", {}).get("total", 0) or 0

        if result.total_trades > 0:
            result.win_rate_pct = round(result.winning_trades / result.total_trades * 100, 1)
            result.avg_win_pct = round(
                (ta.get("won", {}).get("pnl", {}).get("average", 0) or 0) / initial_cash * 100, 2
            )
            result.avg_loss_pct = round(
                abs(ta.get("lost", {}).get("pnl", {}).get("average", 0) or 0) / initial_cash * 100, 2
            )
            gross_profit = ta.get("won", {}).get("pnl", {}).get("total", 0) or 0
            gross_loss = abs(ta.get("lost", {}).get("pnl", {}).get("total", 0) or 0)
            result.profit_factor = round(
                gross_profit / gross_loss, 2
            ) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        # 索提诺比率 (年化下行风险)
        returns_list = []
        for value in strat.analyzers.timereturn.get_analysis().values():
            returns_list.append(value)
        if returns_list and len(returns_list) > 20:
            downside = [r for r in returns_list if r < 0]
            if downside and len(downside) > 1:
                downside_std = statistics.stdev(downside)
                if downside_std > 0:
                    avg_return = sum(returns_list) / len(returns_list)
                    # 年化：假设每日收益，乘以 sqrt(252)
                    result.sortino_ratio = round(
                        (avg_return / downside_std) * math.sqrt(252), 2
                    )

        # 提取权益曲线
        time_returns = strat.analyzers.timereturn.get_analysis()
        if time_returns:
            dates_sorted = sorted(time_returns.keys())
            eq = initial_cash
            bh = initial_cash
            first_close_val = candles[0].get("close", 1)
            eq_points = []
            bh_points = []
            for dt in dates_sorted:
                ret = time_returns[dt]
                eq *= (1 + ret)
                eq_points.append({"date": str(dt)[:10], "value": round(eq, 2)})
            # buy-hold curve based on candle closes
            for c in candles:
                bh = initial_cash * (c.get("close", first_close_val) / first_close_val)
                bh_points.append({"date": str(c.get("date", ""))[:10], "value": round(bh, 2)})
            result.equity_curve = eq_points
            result.buy_hold_curve = bh_points

        # 提取交易明细（从策略实例的 notify_trade 记录）
        result.trades = self._extract_trades(strat, initial_cash)

        # 平均持仓天数
        if result.trades:
            holdings = [t.holding_days for t in result.trades if t.holding_days > 0]
            if holdings:
                result.avg_holding_days = round(sum(holdings) / len(holdings), 1)

        result.run_time_ms = round((datetime.now() - t0).total_seconds() * 1000, 0)
        return result

    # ─── 便捷方法 ─────────────────────────────────────────

    def run_quick(
        self,
        symbol: str,
        candles: List[Dict[str, Any]],
        strategy_key: str = "sma_cross",
        **kwargs,
    ) -> Dict[str, Any]:
        """快速回测 → 只返回摘要 dict"""
        result = self.run(symbol, candles, strategy_key=strategy_key, **kwargs)
        return result.summary_dict()

    def scan_best(
        self,
        symbol: str,
        candles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """扫描所有内置策略，返回按年化收益排序的摘要列表"""
        summaries = []
        for key in STRATEGY_REGISTRY:
            result = self.run(symbol, candles, strategy_key=key)
            summaries.append(result.summary_dict())
        summaries.sort(key=lambda x: x["annual_return_pct"], reverse=True)
        return summaries

    @staticmethod
    def list_strategies() -> List[Dict[str, Any]]:
        """返回所有可用策略的元信息（供前端选择）"""
        return [
            {
                "key": k,
                "name": v["name"],
                "description": v["description"],
                "params": v["params"],
                "param_descriptions": v.get("param_descriptions", {}),
                "recommended_markets": v.get("recommended_markets", ["us", "cn"]),
            }
            for k, v in STRATEGY_REGISTRY.items()
        ]

    # ─── 内部方法 ─────────────────────────────────────────

    @staticmethod
    def _extract_trades(
        strat: bt.Strategy,
        initial_cash: float,
    ) -> List[TradeRecord]:
        """从策略实例收集交易明细"""
        records = getattr(strat, 'trade_records', [])
        trades = []
        for r in records:
            trades.append(TradeRecord(
                date=r.get("exit_date", ""),
                action=r.get("action", "卖出"),
                price=r.get("exit_price", 0),
                size=r.get("size", 0),
                value=r.get("entry_price", 0) * r.get("size", 0),
                pnl=r.get("pnl", 0),
                pnl_pct=r.get("pnl_pct", 0),
                holding_days=r.get("holding_days", 0),
            ))
        return trades


# 单例
_engine_instance: Optional[BacktestEngine] = None


def get_backtest_engine() -> BacktestEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = BacktestEngine()
    return _engine_instance
