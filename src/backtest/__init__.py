"""
backtest 包

提供回测引擎、评估指标和报告输出。

使用方式::

    from src.backtest.engine import BacktestEngine
    from src.backtest.metrics import calculate_metrics
    from src.backtest.reports import print_report

    engine = BacktestEngine(initial_capital=1_000_000)
    result = engine.run(strategy, df)
    print_report(result, "601899.SH (VCP)")
"""

from .engine import BacktestEngine
from .metrics import calculate_metrics
from .reports import print_report

__all__ = ["BacktestEngine", "calculate_metrics", "print_report"]
