"""
VCP 策略信号生成 — 向量化实现
==============================

将原 VCPStrategy 的逐行状态机逻辑完全转换为 Pandas 滚动窗口运算。

设计原则:
  - 所有条件均在时间轴上一次性计算为布尔 Series
  - 无 Python for-loop，充分利用 NumPy 向量化
  - 与原策略逻辑严格对齐，便于结果交叉验证

信号说明:
  entries — 买入信号（True 表示当日收盘买入）
  exits   — 卖出信号（True 表示当日收盘卖出）
  其余止损（硬止损 sl_stop / ATR 追踪止盈）由 VbtBacktestEngine 通过
  vbt.Portfolio.from_signals 的参数统一处理。
"""

import numpy as np
import pandas as pd
from typing import Tuple

from src.backtest.vbt.indicators import (
    calc_sma,
    calc_ma_slope,
    calc_vol_ma,
    calc_vol_max,
    calc_rolling_range_pct,
)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def generate_signals(
    df: pd.DataFrame,
    # Stage 2 均线周期
    ma_50: int = 50,
    ma_120: int = 120,
    ma_150: int = 150,
    ma_200: int = 200,
    ma_slope_lookback: int = 20,
    # VCP 形态参数
    contraction_window: int = 120,   # 120日高点（base_high 窗口）
    range_period: int = 10,          # price_range 收缩窗口
    last_t_depth: float = 0.08,      # 最大允许波幅（默认 8%）
    vol_exhaust_ratio: float = 0.40, # 地量：当前量 < 近20日高量 × 此比例
    # 突破确认
    vol_surge_ratio: float = 1.2,    # 放量倍数（相对 vol_ma20）
    setup_ready_days: int = 5,       # 形态就绪后等待突破的最长窗口
    # 卖出参数
    exit_below_ma: int = 50,         # 跌破此均线触发卖出（MA50）
) -> Tuple[pd.Series, pd.Series]:
    """
    计算 VCP 策略的买入 / 卖出信号。

    参数:
        df — DataFrame，必须含列:
             trade_date, open, high, low, close, vol, pct_chg

    返回:
        (entries, exits) — 两个与 df.index 对齐的布尔 Series
          entries: True 表示当日收盘触发买入
          exits:   True 表示当日收盘触发卖出（MA50 破位）
    """
    df = df.copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').reset_index(drop=True)

    close = df['close']
    high  = df['high']
    low   = df['low']
    vol   = df['vol']

    # ------------------------------------------------------------------
    # 1. 均线系统与 Stage 2 多头排列
    # ------------------------------------------------------------------
    ma50  = calc_sma(close, ma_50)
    ma120 = calc_sma(close, ma_120)
    ma150 = calc_sma(close, ma_150)
    ma200 = calc_sma(close, ma_200)
    ma200_slope = calc_ma_slope(ma200, ma_slope_lookback)

    stage2 = (
        close.gt(ma200) &
        close.gt(ma150) &
        ma150.gt(ma200) &
        ma50.gt(ma120)  &
        ma120.gt(ma150) &
        ma200_slope.gt(0)
    )

    # ------------------------------------------------------------------
    # 2. VCP 形态检测（全向量化）
    # ------------------------------------------------------------------
    # 2a. 距离近期高点不超过 25%
    base_high  = high.rolling(contraction_window, min_periods=contraction_window).max()
    dist_ok    = ((base_high - close) / base_high).lt(0.25)

    # 2b. 近 N 日价格波幅已收缩到 last_t_depth 以内
    rolling_range = calc_rolling_range_pct(high, low, range_period)
    range_ok  = rolling_range.lt(last_t_depth)

    # 2c. 地量：当前量 < 近20日最高量 × vol_exhaust_ratio
    vol_max20 = calc_vol_max(vol, 20)
    vol_ma20  = calc_vol_ma(vol, 20)
    vol_low   = vol.lt(vol_max20 * vol_exhaust_ratio)

    # VCP 形态就绪
    vcp_shape = dist_ok & range_ok & vol_low & stage2

    # 2d. 形态就绪后 setup_ready_days 内有效（滚动前向窗口）
    #     等价于：过去 setup_ready_days 日内曾出现过 vcp_shape=True
    vcp_window = vcp_shape.rolling(setup_ready_days, min_periods=1).max().astype(bool)

    # ------------------------------------------------------------------
    # 3. 突破条件（枢轴突破 + 放量）
    # ------------------------------------------------------------------
    # 枢轴 = 近 20 日（不含当日）的最高价
    pivot = high.shift(1).rolling(20, min_periods=5).max()

    price_breakout = close.gt(pivot)
    vol_surge      = vol.gt(vol_ma20 * vol_surge_ratio)

    # ------------------------------------------------------------------
    # 4. 最终买入信号
    # ------------------------------------------------------------------
    entries = vcp_window & price_breakout & vol_surge

    # ------------------------------------------------------------------
    # 5. 卖出信号（MA 破位）
    #    硬止损（-8%）和时间止损（3日）由 VbtBacktestEngine 通过
    #    sl_stop / 自定义 exit 信号处理，这里只处理趋势破位。
    # ------------------------------------------------------------------
    ma_exit = calc_sma(close, exit_below_ma)
    exits   = close.lt(ma_exit)

    # 对齐索引
    entries = entries.fillna(False)
    exits   = exits.fillna(False)

    return entries, exits


# ---------------------------------------------------------------------------
# 含时间止损的辅助信号（3日涨幅不足则退出）
# ---------------------------------------------------------------------------

def generate_time_stop_exits(
    close: pd.Series,
    entries: pd.Series,
    time_stop_days: int = 3,
    min_profit_pct: float = 0.01,   # 1%
) -> pd.Series:
    """
    时间止损：持仓 time_stop_days 日后，若收益 < min_profit_pct 则卖出。

    实现思路：对每个 entry 日，向前推 time_stop_days 天，如果价格涨幅
    不足 min_profit_pct，则在该日标记 exit=True。

    注意：此函数生成的 exit 需与主 exits OR 合并后传入引擎。
    """
    time_stop = pd.Series(False, index=close.index)
    entry_indices = entries[entries].index.tolist()

    for idx in entry_indices:
        pos = close.index.get_loc(idx)
        check_pos = pos + time_stop_days
        if check_pos < len(close):
            entry_price = close.iloc[pos]
            check_price = close.iloc[check_pos]
            ret = (check_price - entry_price) / entry_price
            if ret < min_profit_pct:
                time_stop.iloc[check_pos] = True

    return time_stop
