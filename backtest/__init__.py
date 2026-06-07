# -*- coding: utf-8 -*-
"""量化回测模块 - 基于 backtrader，集成系统现有数据源"""

from .engine import BacktestEngine, BacktestResult
from .strategies import (
    SmaCrossStrategy,
    MacdStrategy,
    RsiReversalStrategy,
    BollingerBounceStrategy,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "SmaCrossStrategy",
    "MacdStrategy",
    "RsiReversalStrategy",
    "BollingerBounceStrategy",
]
