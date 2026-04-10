"""
回测评估指标模块

职责：
  将 trades 列表和权益曲线计算为标准化的 BacktestResult 性能指标。
  从 BaseStrategy._calculate_metrics() 中提取，实现 DRY。
"""

import numpy as np
from typing import List, Tuple
from datetime import date

from src.strategy.base import Trade, BacktestResult


def calculate_metrics(
    trades: List[Trade],
    equity_curve: List[Tuple[date, float]],
    initial_capital: float
) -> BacktestResult:
    """
    计算标准化的性能指标。

    参数:
        trades         - 已关闭的交易记录列表
        equity_curve   - (日期, 权益) 元组列表
        initial_capital - 初始资金

    返回:
        BacktestResult，包含所有性能指标
    """
    result = BacktestResult()
    result.trades = trades
    result.equity_curve = equity_curve

    if not trades:
        return result

    result.total_trades = len(trades)
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl <= 0]
    result.winning_trades = len(winning_trades)
    result.losing_trades = len(losing_trades)

    result.win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
    result.avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
    result.avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0

    if result.avg_loss != 0:
        result.profit_loss_ratio = abs(result.avg_win / result.avg_loss)
    else:
        result.profit_loss_ratio = float('inf') if winning_trades else 0

    final_value = equity_curve[-1][1] if equity_curve else initial_capital
    result.total_return = (final_value - initial_capital) / initial_capital * 100

    # 计算年化
    if len(equity_curve) >= 2:
        days = (equity_curve[-1][0] - equity_curve[0][0]).days
        years = days / 365.25
        if years > 0 and final_value > 0 and initial_capital > 0:
            result.annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100

    # 最大回撤
    peak = initial_capital
    max_dd = 0
    max_dd_pct = 0
    for _, value in equity_curve:
        if value > peak:
            peak = value
        dd = peak - value
        dd_pct = dd / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
    result.max_drawdown = max_dd
    result.max_drawdown_pct = max_dd_pct

    return result
