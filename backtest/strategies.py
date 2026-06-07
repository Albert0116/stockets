# -*- coding: utf-8 -*-
"""内置回测策略集合

所有策略遵循 backtrader.Strategy 接口，可直接被 BacktestEngine 调用。
同时也暴露了参数和文档，方便 AI (DeepSeek) 理解和生成变体。
"""

import backtrader as bt


class _BaseStrategy(bt.Strategy):
    """策略基类 —— 提供仓位管理和交易记录收集"""

    def __init__(self):
        self.trade_records = []  # 收集交易明细
        self._entry_date = None
        self._entry_price = 0.0
        self._entry_size = 0

    def _calc_size(self):
        """动态仓位：用 95% 可用资金买入"""
        available = self.broker.getcash() * 0.95
        price = self.data.close[0]
        if price <= 0:
            return 0
        return int(available / price)

    def buy(self, **kwargs):
        """重写买入：自动计算仓位 + 记录入场信息"""
        if 'size' not in kwargs:
            size = self._calc_size()
            if size <= 0:
                return
            kwargs['size'] = size
        self._entry_date = self.data.datetime.date(0)
        self._entry_price = self.data.close[0]
        self._entry_size = kwargs.get('size', 0)
        return super().buy(**kwargs)

    def notify_trade(self, trade):
        """每笔交易关闭时记录明细"""
        if trade.isclosed:
            entry_date = str(self._entry_date) if self._entry_date else ""
            exit_date = str(self.data.datetime.date(0))
            holding = 0
            if self._entry_date:
                holding = (self.data.datetime.date(0) - self._entry_date).days
            cost = self._entry_price * self._entry_size if self._entry_price * self._entry_size > 0 else 1
            self.trade_records.append({
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_price": round(self._entry_price, 2),
                "exit_price": round(trade.price, 2),
                "size": self._entry_size,
                "pnl": round(trade.pnl, 2),
                "pnl_pct": round(trade.pnl / cost * 100, 2),
                "holding_days": holding,
                "action": "卖出",
            })


class SmaCrossStrategy(_BaseStrategy):
    """均线金叉死叉策略

    参数:
        fast (int): 快线周期，默认 10
        slow (int): 慢线周期，默认 30

    逻辑:
        - 快线上穿慢线 → 买入
        - 快线下穿慢线 → 卖出
        适合趋势明显的市场，在震荡市中容易频繁止损。
    """
    params = (
        ("fast", 10),
        ("slow", 30),
    )

    def __init__(self):
        super().__init__()
        sma_fast = bt.ind.SMA(period=self.params.fast)
        sma_slow = bt.ind.SMA(period=self.params.slow)
        self.crossover = bt.ind.CrossOver(sma_fast, sma_slow)

    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.buy()
        elif self.crossover < 0:
            self.close()


class MacdStrategy(_BaseStrategy):
    """MACD 金叉死叉策略

    参数:
        fast (int): 快线周期，默认 12
        slow (int): 慢线周期，默认 26
        signal (int): 信号线周期，默认 9

    逻辑:
        - MACD 线上穿信号线 → 买入
        - MACD 线下穿信号线 → 卖出
    """
    params = (
        ("fast", 12),
        ("slow", 26),
        ("signal", 9),
    )

    def __init__(self):
        super().__init__()
        self.macd = bt.ind.MACD(
            period_me1=self.params.fast,
            period_me2=self.params.slow,
            period_signal=self.params.signal,
        )
        self.crossover = bt.ind.CrossOver(self.macd.macd, self.macd.signal)

    def next(self):
        if not self.position:
            if self.crossover > 0:
                self.buy()
        elif self.crossover < 0:
            self.close()


class RsiReversalStrategy(_BaseStrategy):
    """RSI 超买超卖反转策略

    参数:
        period (int): RSI 周期，默认 14
        oversold (int): 超卖阈值，默认 30
        overbought (int): 超买阈值，默认 70

    逻辑:
        - RSI 从超卖区回升 → 买入
        - RSI 从超买区回落 → 卖出
    """
    params = (
        ("period", 14),
        ("oversold", 30),
        ("overbought", 70),
    )

    def __init__(self):
        super().__init__()
        self.rsi = bt.ind.RSI(period=self.params.period)
        self.entered_oversold = False
        self.entered_overbought = False

    def next(self):
        if not self.position:
            if self.rsi[0] < self.params.oversold:
                self.entered_oversold = True
            if self.entered_oversold and self.rsi[0] > self.params.oversold:
                self.buy()
                self.entered_oversold = False
        else:
            if self.rsi[0] > self.params.overbought:
                self.entered_overbought = True
            if self.entered_overbought and self.rsi[0] < self.params.overbought:
                self.close()
                self.entered_overbought = False


class BollingerBounceStrategy(_BaseStrategy):
    """布林带反弹策略

    参数:
        period (int): 布林带周期，默认 20
        devfactor (float): 标准差倍数，默认 2.0

    逻辑:
        - 价格触及下轨后反弹回轨内 → 买入
        - 价格触及上轨或跌破中轨 → 卖出
    """
    params = (
        ("period", 20),
        ("devfactor", 2.0),
    )

    def __init__(self):
        super().__init__()
        self.bb = bt.ind.BollingerBands(
            period=self.params.period,
            devfactor=self.params.devfactor,
        )
        self.sma = bt.ind.SMA(period=self.params.period)

    def next(self):
        if not self.position:
            # 价格触及下轨后回到下轨上方
            if self.data.close[-1] <= self.bb.lines.bot[-1] and self.data.close[0] > self.bb.lines.bot[0]:
                self.buy()
        else:
            # 触及上轨卖出
            if self.data.close[0] >= self.bb.lines.top[0]:
                self.close()
            # 跌破中轨且趋势向下才卖出（避免假突破）
            elif (self.data.close[0] < self.sma[0] and
                  self.data.close[-1] < self.data.close[-2] and
                  self.data.close[0] < self.data.close[-1]):
                self.close()


# 策略注册表 — 供 AI 或前端动态调用
STRATEGY_REGISTRY = {
    "sma_cross": {
        "class": SmaCrossStrategy,
        "name": "均线交叉",
        "description": "快慢均线金叉买入，死叉卖出。适合趋势市。",
        "params": {"fast": 10, "slow": 30},
        "param_descriptions": {
            "fast": "快线周期 (默认10)",
            "slow": "慢线周期 (默认30)",
        },
        "recommended_markets": ["us", "cn"],
    },
    "macd": {
        "class": MacdStrategy,
        "name": "MACD",
        "description": "MACD金叉买入，死叉卖出。经典动量策略。",
        "params": {"fast": 12, "slow": 26, "signal": 9},
        "param_descriptions": {
            "fast": "快线周期 (默认12)",
            "slow": "慢线周期 (默认26)",
            "signal": "信号线周期 (默认9)",
        },
        "recommended_markets": ["us", "cn"],
    },
    "rsi_reversal": {
        "class": RsiReversalStrategy,
        "name": "RSI反转",
        "description": "RSI超卖反弹买入，超买回落卖出。适合震荡市。",
        "params": {"period": 14, "oversold": 30, "overbought": 70},
        "param_descriptions": {
            "period": "RSI周期 (默认14)",
            "oversold": "超卖阈值 (默认30)",
            "overbought": "超买阈值 (默认70)",
        },
        "recommended_markets": ["us", "cn"],
    },
    "bollinger_bounce": {
        "class": BollingerBounceStrategy,
        "name": "布林带反弹",
        "description": "价格触及下轨反弹买入，触及上轨或跌破中轨卖出。",
        "params": {"period": 20, "devfactor": 2.0},
        "param_descriptions": {
            "period": "布林带周期 (默认20)",
            "devfactor": "标准差倍数 (默认2.0)",
        },
        "recommended_markets": ["us", "cn"],
    },
}
