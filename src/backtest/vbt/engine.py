"""
VbtBacktestEngine — 封装 vbt.Portfolio.from_signals
=====================================================

职责:
  - 接收向量化买入/卖出信号（布尔 Series）
  - 配置手续费（双边 0.1%）、止损、滑点
  - 返回 vbt.Portfolio 对象（含所有内置性能指标）
  - 支持参数网格扫描（param_grid 模式）

Usage::

    from src.backtest.vbt.engine import VbtBacktestEngine
    from src.backtest.vbt.signals import vcp_signals

    entries, exits = vcp_signals.generate_signals(df)
    engine = VbtBacktestEngine()
    portfolio = engine.run(df, entries, exits)
    engine.print_stats(portfolio)
"""

import logging
from typing import Optional, Union

import numpy as np
import pandas as pd
import vectorbt as vbt

logger = logging.getLogger(__name__)


class VbtBacktestEngine:
    """
    基于 VectorBT 的向量化回测引擎。

    参数:
        initial_capital  — 初始资金（默认 100 万元）
        fees             — 单边手续费率（默认 0.001 = 0.1%）
        slippage         — 滑点（默认 0.001 = 0.1%）
        sl_stop          — 硬止损比例（默认 0.08 = 8%，相对买入价）
        freq             — 数据频率（默认 'D' = 日线）
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        fees: float = 0.001,          # 单边 0.1%，双边共 0.2%
        slippage: float = 0.001,      # 0.1% 滑点
        sl_stop: float = 0.08,        # 8% 硬止损
        freq: str = "D",
    ):
        self.initial_capital = initial_capital
        self.fees            = fees
        self.slippage        = slippage
        self.sl_stop         = sl_stop
        self.freq            = freq

    # ------------------------------------------------------------------
    # 单次回测
    # ------------------------------------------------------------------

    def run(
        self,
        df: pd.DataFrame,
        entries: pd.Series,
        exits: pd.Series,
        entry_price: Optional[pd.Series] = None,
        use_sl_stop: bool = True,
        accumulate: bool = False,
    ) -> vbt.Portfolio:
        """
        运行单次回测。

        参数:
            df           — 含 trade_date / close / open 的 DataFrame
            entries      — 买入信号（布尔 Series）
            exits        — 卖出信号（布尔 Series）
            entry_price  — 实际入场价格（None 则用收盘价；T+1 入场传 open.shift(-1)）
            use_sl_stop  — 是否启用硬止损
            accumulate   — 是否允许加仓（默认 False，持仓期间跳过新信号）

        返回:
            vbt.Portfolio 对象
        """
        df = df.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)

        close_series = pd.Series(
            df['close'].values,
            index=df['trade_date'],
        )
        entries_s = pd.Series(entries.values, index=df['trade_date'])
        exits_s   = pd.Series(exits.values,   index=df['trade_date'])

        # 入场价格（默认收盘价）
        if entry_price is not None:
            price_s = pd.Series(entry_price.values, index=df['trade_date'])
        else:
            price_s = close_series

        kwargs = dict(
            close        = close_series,
            entries      = entries_s,
            exits        = exits_s,
            open         = price_s,       # 入场价
            init_cash    = self.initial_capital,
            fees         = self.fees,
            slippage     = self.slippage,
            freq         = self.freq,
            accumulate   = accumulate,
        )

        if use_sl_stop:
            kwargs['sl_stop'] = self.sl_stop

        portfolio = vbt.Portfolio.from_signals(**kwargs)

        logger.info(
            "VBT 回测完成 | 总收益: %.2f%% | 夏普: %.2f | 最大回撤: %.2f%%",
            portfolio.total_return() * 100,
            portfolio.sharpe_ratio(),
            portfolio.max_drawdown() * 100,
        )
        return portfolio

    # ------------------------------------------------------------------
    # 参数网格扫描
    # ------------------------------------------------------------------

    def run_grid(
        self,
        df: pd.DataFrame,
        entries_grid: pd.DataFrame,
        exits_grid: pd.DataFrame,
        param_names: list[str],
    ) -> vbt.Portfolio:
        """
        参数网格扫描（多列 entries / exits DataFrame）。

        entries_grid / exits_grid 的每一列对应一组参数组合，
        列名应为参数组合标识（如 '0.06-0.3'）。

        参数:
            df             — 基础行情 DataFrame
            entries_grid   — 多列布尔 DataFrame（行=时间，列=参数组合）
            exits_grid     — 多列布尔 DataFrame（同上）
            param_names    — 参数组合列表（用于报告标签）

        返回:
            vbt.Portfolio （多列），通过 .stats() 可批量获取指标
        """
        df = df.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)

        close_series = pd.Series(df['close'].values, index=df['trade_date'])

        entries_grid.index = df['trade_date']
        exits_grid.index   = df['trade_date']

        portfolio = vbt.Portfolio.from_signals(
            close       = close_series,
            entries     = entries_grid,
            exits       = exits_grid,
            init_cash   = self.initial_capital,
            fees        = self.fees,
            slippage    = self.slippage,
            sl_stop     = self.sl_stop,
            freq        = self.freq,
        )

        logger.info("参数网格扫描完成，共 %d 组参数", len(param_names))
        return portfolio

    # ------------------------------------------------------------------
    # 统计报告（控制台输出）
    # ------------------------------------------------------------------

    @staticmethod
    def print_stats(portfolio: vbt.Portfolio, label: str = "") -> None:
        """打印 VectorBT 内置统计指标（精选关键指标）。"""
        stats = portfolio.stats()

        tag = f"[{label}] " if label else ""
        print(f"\n{'='*60}")
        print(f"  📊 {tag}VectorBT 回测统计")
        print(f"{'='*60}")

        keys = [
            ("Start",               "回测开始"),
            ("End",                 "回测结束"),
            ("Period",              "回测时长"),
            ("Total Return [%]",    "总收益率"),
            ("Annualized Return [%]","年化收益率"),
            ("Sharpe Ratio",        "夏普比率"),
            ("Calmar Ratio",        "卡玛比率"),
            ("Max Drawdown [%]",    "最大回撤"),
            ("Win Rate [%]",        "胜率"),
            ("Total Trades",        "总交易次数"),
            ("Profit Factor",       "盈亏比"),
            ("Avg Winning Trade [%]","平均盈利"),
            ("Avg Losing Trade [%]", "平均亏损"),
            ("Best Trade [%]",      "最佳交易"),
            ("Worst Trade [%]",     "最差交易"),
        ]

        for vbt_key, zh_label in keys:
            if vbt_key in stats.index:
                val = stats[vbt_key]
                print(f"  {zh_label:<12}: {val}")

        print(f"{'='*60}\n")
