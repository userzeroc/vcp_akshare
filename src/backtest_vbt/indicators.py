"""
公共向量化指标计算
==================

所有函数接受 pd.Series，返回 pd.Series（保持原始 index）。
策略信号模块通过本模块统一计算，避免重复实现。
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 均线
# ---------------------------------------------------------------------------

def calc_sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均"""
    return series.rolling(window=period, min_periods=period).mean()


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=period, adjust=False).mean()


def calc_ma_slope(ma_series: pd.Series, lookback: int = 20) -> pd.Series:
    """
    均线斜率：(当前值 - N日前值) / N日前值

    用于判断均线是否向上拐头。
    """
    return (ma_series - ma_series.shift(lookback)) / ma_series.shift(lookback)


# ---------------------------------------------------------------------------
# 波动率 / ATR
# ---------------------------------------------------------------------------

def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """
    Average True Range (ATR)

    TR = max(high-low, |high-prev_close|, |low-prev_close|)
    ATR = SMA(TR, period)
    """
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


# ---------------------------------------------------------------------------
# 成交量
# ---------------------------------------------------------------------------

def calc_vol_ma(vol: pd.Series, period: int) -> pd.Series:
    """成交量移动平均"""
    return vol.rolling(window=period, min_periods=period).mean()


def calc_vol_max(vol: pd.Series, period: int) -> pd.Series:
    """成交量滚动最大值"""
    return vol.rolling(window=period, min_periods=1).max()


# ---------------------------------------------------------------------------
# 价格衍生指标
# ---------------------------------------------------------------------------

def calc_bias(close: pd.Series, ma_series: pd.Series) -> pd.Series:
    """
    乖离率 = (收盘价 - MA) / MA

    正值 = 价格偏离均线上方（追高风险）
    负值 = 价格偏离均线下方（超跌）
    """
    return (close - ma_series) / ma_series


def calc_rolling_range_pct(high: pd.Series, low: pd.Series, period: int = 10) -> pd.Series:
    """
    N日价格波幅百分比 = (N日最高 - N日最低) / N日最低

    用于衡量价格收缩程度（VCP 核心指标之一）。
    """
    rolling_high = high.rolling(period, min_periods=period).max()
    rolling_low  = low.rolling(period, min_periods=period).min()
    return (rolling_high - rolling_low) / rolling_low
