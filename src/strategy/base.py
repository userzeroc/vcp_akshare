
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
    策略基类 — 定义策略与回测引擎之间的标准接口。

    策略子类需要实现以下方法：
      - calculate_indicators(df)   : 计算技术指标
      - get_warmup_period()        : 返回指标计算所需的预热期长度
      - check_buy(row, df, i)      : 检查买入条件
      - check_sell(row, position)  : 检查卖出条件

    可选覆盖：
      - reset_state()  : 重置策略内部状态（如计数器）
      - on_buy()       : 买入后回调
      - on_sell()      : 卖出后回调

    回测执行：
      使用 BacktestEngine.run(strategy, df) 运行回测，
      或调用 strategy.run(df)（向后兼容，内部委托给 BacktestEngine）。
    """
    
    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算策略所需指标，返回已添加指标列的 DataFrame"""
        pass

    @abstractmethod
    def get_warmup_period(self) -> int:
        """返回指标计算所需的预热期长度（交易日数）"""
        pass

    @abstractmethod
    def check_buy(self, row: pd.Series, df: pd.DataFrame, i: int, **kwargs) -> Tuple[bool, Optional[float], str]:
        """
        检查买入条件。

        参数:
            row  - 当日行情数据
            df   - 完整 DataFrame（可用于回溯历史数据）
            i    - 当前行索引

        返回:
            (是否触发买入, 买入价格, 买入原因)
        """
        pass

    @abstractmethod
    def check_sell(self, row: pd.Series, position: Position, **kwargs) -> Tuple[bool, str]:
        """
        检查卖出条件。

        参数:
            row      - 当日行情数据
            position - 当前持仓状态

        返回:
            (是否触发卖出, 卖出原因)
        """
        pass

    def reset_state(self):
        """重置策略内部状态（每次回测开始前调用）"""
        pass

    def on_buy(self, current_date: date):
        """买入后回调，子类可覆盖"""
        pass

    def on_sell(self, current_date: date):
        """卖出后回调，子类可覆盖"""
        pass

    # ------------------------------------------------------------------
    # 向后兼容：strategy.run(df) 委托给 BacktestEngine
    # ------------------------------------------------------------------

    def run(self, df: pd.DataFrame, initial_capital: float = 1000000.0, debug: bool = True, **kwargs) -> BacktestResult:
        """
        运行回测（向后兼容接口）。

        内部委托给 BacktestEngine，无需子类覆盖。
        """
        from src.backtest.engine import BacktestEngine
        engine = BacktestEngine(initial_capital=initial_capital, debug=debug)
        return engine.run(self, df, **kwargs)

    # ------------------------------------------------------------------
    # 向后兼容：strategy.print_report()
    # ------------------------------------------------------------------

    @staticmethod
    def print_report(result: BacktestResult, stock_info: str = ""):
        """打印标准回测报告（委托给 backtest.reports 模块）"""
        from src.backtest.reports import print_report
        print_report(result, stock_info)
