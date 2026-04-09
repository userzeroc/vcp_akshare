
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Any
from datetime import date
from abc import ABC, abstractmethod

@dataclass
class Signal:
    """交易信号"""
    date: date
    signal_type: str  # 'buy', 'sell'
    price: float
    reason: str

@dataclass
class Trade:
    """单笔交易记录"""
    entry_date: date
    entry_price: float
    quantity: int
    stop_loss_price: Optional[float] = None
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    
    def close(self, exit_date: date, exit_price: float, reason: str):
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.pnl = (exit_price - self.entry_price) * self.quantity
        self.pnl_pct = (exit_price - self.entry_price) / self.entry_price * 100
        self.exit_reason = reason

@dataclass
class Position:
    """持仓状态"""
    is_long: bool = False
    entry_date: Optional[date] = None
    entry_price: Optional[float] = None
    quantity: int = 0
    signal_low: Optional[float] = None  # 信号日最低价
    highest_price: Optional[float] = None  # 持仓期间最高价

@dataclass
class BacktestResult:
    """回测结果统计"""
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[date, float]] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    
    # 性能指标
    total_return: float = 0.0
    annualized_return: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_loss_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

class BaseStrategy(ABC):
    """
    策略基类，标准化所有策略的接口与评估逻辑
    """
    
    @abstractmethod
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算策略所需指标"""
        pass

    @abstractmethod
    def run(self, df: pd.DataFrame, initial_capital: float = 1000000.0, debug: bool = True) -> BacktestResult:
        """运行回测的主循环"""
        pass

    def _calculate_metrics(
        self,
        trades: List[Trade],
        equity_curve: List[Tuple[date, float]],
        initial_capital: float
    ) -> BacktestResult:
        """计算标准化的性能指标 (DRY原则)"""
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

    def print_report(self, result: BacktestResult, stock_info: str = ""):
        """打印标准回测报告"""
        final_value = result.equity_curve[-1][1] if result.equity_curve else 1000000.0
        
        print("\n" + "=" * 70)
        print(f"  📊 Strategy Backtest Report: {stock_info}")
        print("=" * 70)
        
        print(f"\n[ Performance Summary ]")
        print(f"  Final Equity:          {final_value:,.2f}")
        print(f"  Total Return:          {result.total_return:.2f}%")
        print(f"  Annualized Return:     {result.annualized_return:.2f}%")
        print(f"  Max Drawdown:          {result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")
        
        print(f"\n[ Trading Statistics ]")
        print(f"  Total Trades:          {result.total_trades}")
        print(f"  Winning Trades:        {result.winning_trades} ({result.win_rate:.1f}%)")
        print(f"  Profit/Loss Ratio:     {result.profit_loss_ratio:.2f}")
        print(f"  Avg Win/Loss:          {result.avg_win:,.0f} / {result.avg_loss:,.0f}")
        
        if result.trades:
            print(f"\n[ Trade Details ]")
            print("-" * 70)
            print(f"{'Entry Date':<12} {'Entry':>8} {'Exit Date':<12} {'Exit':>8} {'PnL%':>8} {'Reason'}")
            print("-" * 70)
            for t in result.trades:
                entry_str = str(t.entry_date)
                exit_str = str(t.exit_date)
                pct_str = f"{t.pnl_pct:+.1f}%"
                print(f"{entry_str:<12} {t.entry_price:>8.2f} {exit_str:<12} {t.exit_price:>8.2f} {pct_str:>8} {t.exit_reason[:20]}")
            print("-" * 70)
        print("=" * 70 + "\n")
