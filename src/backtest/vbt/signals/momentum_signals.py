"""
动量突破策略信号生成 — 向量化实现
====================================

将原 MomentumBreakoutStrategy 的逐行判断逻辑转换为 Pandas 向量化运算。

买入条件（全部满足）:
  A. 股价 > MA60（大级别趋势向上）
  B. 当日涨幅 > min_pct_chg（动量触发）
  C. 成交量 > vol_ma20 × vol_multiplier（倍量确认）
  D. 乖离率 < bias_threshold（防追高）

卖出条件（任一满足）:
  1. 股价 < MA20（短期趋势破位）
  2. 股价 < 信号日低点（由 vbt sl_stop 处理）
  3. ATR 追踪止盈触及（由 vbt 自定义退出逻辑处理）
  4. 硬止损 ≤ -8%（由 vbt sl_stop 处理）

T+1 入场:
  由于 A 股 T+1 制度，买入信号在 T 日收盘产生，T+1 开盘价入场。
  VectorBT 通过 price=open.shift(-1) 或 open 实现，见 engine.py。
"""

import numpy as np
import pandas as pd
from typing import Tuple

from src.backtest.vbt.indicators import (
    calc_sma,
    calc_atr,
    calc_vol_ma,
    calc_bias,
)


def generate_signals(
    df: pd.DataFrame,
    # 均线参数
    ma_long_period: int = 60,
    ma_short_period: int = 20,
    # 动量参数
    min_pct_chg: float = 5.0,       # 最小涨幅 %
    vol_multiplier: float = 2.0,    # 成交量倍数
    vol_ma_period: int = 20,
    # 风控参数
    bias_threshold: float = 0.25,   # 乖离率上限（防追高）
    # 卖出参数
    exit_below_ma: int = 20,        # 跌破此均线触发卖出 (MA20)
    # ATR 追踪止盈
    use_trailing_stop: bool = True,
    atr_period: int = 20,
    atr_multiplier: float = 2.5,
) -> Tuple[pd.Series, pd.Series]:
    """
    计算动量突破策略的买入 / 卖出信号。

    参数:
        df — DataFrame，必须含列:
             trade_date, open, high, low, close, vol, pct_chg

    返回:
        (entries, exits) — 布尔 Series，与 df.index 对齐
    """
    df = df.copy()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').reset_index(drop=True)

    close   = df['close']
    high    = df['high']
    low     = df['low']
    vol     = df['vol']
    pct_chg = df['pct_chg']

    # ------------------------------------------------------------------
    # 指标计算
    # ------------------------------------------------------------------
    ma_long  = calc_sma(close, ma_long_period)
    ma_short = calc_sma(close, ma_short_period)
    vol_ma   = calc_vol_ma(vol, vol_ma_period)
    bias     = calc_bias(close, ma_long)
    atr      = calc_atr(high, low, close, atr_period)

    # ------------------------------------------------------------------
    # 买入信号（T 日收盘条件，T+1 开盘入场）
    # ------------------------------------------------------------------
    cond_a = close.gt(ma_long)                           # A. 大趋势向上
    cond_b = pct_chg.gt(min_pct_chg)                    # B. 涨幅触发
    cond_c = vol.gt(vol_ma * vol_multiplier)             # C. 倍量
    cond_d = bias.lt(bias_threshold)                     # D. 未过度追高

    entries = cond_a & cond_b & cond_c & cond_d

    # ------------------------------------------------------------------
    # 卖出信号（MA 破位）
    # ------------------------------------------------------------------
    exits = close.lt(ma_short)

    # ------------------------------------------------------------------
    # ATR 追踪止盈：动态计算止盈线
    # 若当前价格跌破（最高持仓价 - ATR × 倍数），则卖出
    # 注意：这里只生成"参考止盈线"，在 engine.py 中通过
    #      sl_trail 参数或 delta_format='percent' 转换处理。
    # ------------------------------------------------------------------

    entries = entries.fillna(False)
    exits   = exits.fillna(False)

    return entries, exits


def calc_entry_price(df: pd.DataFrame) -> pd.Series:
    """
    T+1 开盘价入场。

    在 VectorBT 中，买入信号 entries 在 T 日生成，
    实际成交价使用 T+1 的开盘价（open.shift(-1)）。

    返回 shifted open Series，供 engine.py 的 price 参数使用。
    """
    df = df.sort_values('trade_date').reset_index(drop=True)
    return df['open'].shift(-1)
