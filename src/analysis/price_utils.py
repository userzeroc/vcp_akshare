"""
price_utils.py
==============
价格数据预处理工具。

职责：
- 将 Tushare / StockReader 返回的原始 DataFrame 整理为分析层可直接使用的格式。
- 不依赖任何业务逻辑，只做纯数据清洗与特征计算。
"""

import pandas as pd


def prepare_price_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    对原始日线数据做标准化预处理：
      1. 将 trade_date 列转为 DatetimeIndex（若尚未设置）
      2. 按日期正序排列
      3. 新增 avg_price 列（开盘价与收盘价的均值）

    Parameters
    ----------
    df : pd.DataFrame
        来自 StockReader 的原始日线 DataFrame，
        须包含 'open'、'close' 列；
        trade_date 可以是普通列，也可以已是 Index。

    Returns
    -------
    pd.DataFrame
        处理后的 DataFrame，DatetimeIndex 为 trade_date，
        新增 avg_price 列。
    """
    df = df.copy()

    # 若 trade_date 是普通列，将其设为索引
    if 'trade_date' in df.columns:
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)

    # 保证时间正序
    df.sort_index(inplace=True)

    # 计算每日均价
    df['avg_price'] = (df['open'] + df['close']) / 2

    return df
