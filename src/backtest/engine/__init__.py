"""
通用回测引擎 (Backtest Engine)
==============================

职责：
  - 驱动标准化的 "日线遍历" 回测循环
  - 管理资金、仓位、权益曲线
  - 调用策略的 check_buy / check_sell 接口实现信号与执行分离

设计原则：
  策略层只负责 "该不该买" / "该不该卖" 的判断，
  回测引擎负责 "怎么买" / "怎么卖" 的执行。
  两层解耦后，策略可以单独测试信号质量，回测引擎可以复用于任意策略。
"""

import logging
from typing import List, Tuple, Optional

import pandas as pd
from datetime import date

from src.strategy.base import BaseStrategy, Signal, Trade, Position, BacktestResult
from src.backtest.metrics import calculate_metrics

logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    通用事件驱动回测引擎。

    Usage::

        from src.backtest.engine import BacktestEngine
        from src.strategy.vcp_strategy import VCPStrategy

        engine = BacktestEngine(initial_capital=1_000_000)
        result = engine.run(VCPStrategy(), df)
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        debug: bool = True,
    ):
        self.initial_capital = initial_capital
        self.debug = debug

    def run(self, strategy: BaseStrategy, df: pd.DataFrame, **strategy_run_kwargs) -> BacktestResult:
        """
        运行回测主循环。

        参数:
            strategy           - 实现了 BaseStrategy 接口的策略实例
            df                 - 包含 trade_date, open, high, low, close, vol, pct_chg 的 DataFrame
            **strategy_run_kwargs - 额外传递给策略的参数（如 earnings_dates）

        返回:
            BacktestResult，包含所有交易记录和性能指标
        """
        # 1. 让策略计算技术指标
        df = strategy.calculate_indicators(df)

        cash = self.initial_capital
        position = Position()
        trades: List[Trade] = []
        equity_curve: List[Tuple[date, float]] = []
        signals: List[Signal] = []

        # 策略级状态由策略自行管理
        strategy.reset_state()

        warmup = strategy.get_warmup_period()

        for i in range(warmup, len(df)):
            row = df.iloc[i]
            current_date = row['trade_date'].date() if hasattr(row['trade_date'], 'date') else row['trade_date']
            close_price = row['close']

            # ============ 持仓中 ============
            if position.is_long:
                if close_price > (position.highest_price or 0):
                    position.highest_price = close_price

                sell_triggered, sell_reason = strategy.check_sell(row, position, **strategy_run_kwargs)

                if sell_triggered:
                    trade = Trade(
                        entry_date=position.entry_date,
                        entry_price=position.entry_price,
                        quantity=position.quantity,
                        stop_loss_price=position.signal_low
                    )
                    trade.close(current_date, close_price, sell_reason)
                    trades.append(trade)
                    cash += (position.quantity * close_price)
                    equity_curve.append((current_date, cash))
                    if self.debug:
                        logger.info("[SELL] %s @ %.2f | PnL: %+.1f%% | Reason: %s",
                                    current_date, close_price, trade.pnl_pct, sell_reason)
                    position = Position()
                    signals.append(Signal(current_date, 'sell', close_price, sell_reason))
                    strategy.on_sell(current_date)
                else:
                    equity_curve.append((current_date, cash + position.quantity * close_price))

            # ============ 空仓中 ============
            else:
                equity_curve.append((current_date, cash))

                buy_triggered, buy_price, buy_reason = strategy.check_buy(
                    row, df, i, **strategy_run_kwargs
                )

                if buy_triggered and buy_price is not None:
                    quantity = int(cash / buy_price / 100) * 100
                    if quantity > 0:
                        buy_date = current_date
                        # 如果策略返回的是 T+1 开盘价入场
                        if hasattr(strategy, 'get_buy_date') and i + 1 < len(df):
                            next_row = df.iloc[i + 1]
                            buy_date = next_row['trade_date'].date() if hasattr(next_row['trade_date'], 'date') else next_row['trade_date']

                        cash -= quantity * buy_price
                        position = Position(
                            is_long=True,
                            entry_date=buy_date,
                            entry_price=buy_price,
                            quantity=quantity,
                            signal_low=row['low'],
                            highest_price=buy_price
                        )
                        # 修正买入当日的权益曲线
                        equity_curve[-1] = (current_date, cash + quantity * buy_price)
                        if self.debug:
                            logger.info("[BUY] %s @ %.2f | Reason: %s",
                                        buy_date, buy_price, buy_reason)
                        signals.append(Signal(buy_date, 'buy', buy_price, buy_reason))
                        strategy.on_buy(current_date)

            # 最后一天平仓
            if i == len(df) - 1 and position.is_long:
                trade = Trade(position.entry_date, position.entry_price, position.quantity, position.signal_low)
                trade.close(current_date, close_price, "回测结束强制平仓")
                trades.append(trade)
                cash += (position.quantity * close_price)
                equity_curve[-1] = (current_date, cash)

        result = calculate_metrics(trades, equity_curve, self.initial_capital)
        result.signals = signals
        return result
