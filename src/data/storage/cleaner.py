"""
数据清洗模块

每个 Tushare 接口返回的 DataFrame 都有其特有的脏数据问题，
此模块为各接口提供专用清洗函数，统一在写库前调用。

清洗规则:
  1. 删除主键列为空的行（空主键无法 upsert）
  2. 日期字段: Tushare 返回 "YYYYMMDD" 字符串 → 转换为 datetime.date
  3. 数值字段: 强制转 float，无法转换的置 None（coerce）
  4. 字符串字段: strip 首尾空白
  5. 删除全行重复（同一次拉取偶有重复行）
"""

import datetime
from typing import Sequence

import pandas as pd


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------

def _to_date(series: pd.Series, fmt: str = "%Y%m%d") -> pd.Series:
    """将 'YYYYMMDD' 字符串列安全转换为 datetime.date（NaT → None）。"""
    return pd.to_datetime(series, format=fmt, errors="coerce").dt.date


def _to_numeric_cols(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _strip_str_cols(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("nan", None)
    return df


# ---------------------------------------------------------------------------
# 各接口专用清洗函数
# ---------------------------------------------------------------------------

def clean_trade_cal(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 Tushare trade_cal 接口数据。

    主键: (exchange, cal_date)
    """
    df = df.dropna(subset=["exchange", "cal_date"])
    df["cal_date"] = _to_date(df["cal_date"])
    if "pretrade_date" in df.columns:
        df["pretrade_date"] = _to_date(df["pretrade_date"])
    df = _to_numeric_cols(df, ["is_open"])
    df["is_open"] = df["is_open"].astype("Int8")  # nullable integer
    df = df.drop_duplicates(subset=["exchange", "cal_date"])
    return df.reset_index(drop=True)


def clean_stock_basic(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 Tushare stock_basic 接口数据。

    主键: ts_code
    """
    df = df.dropna(subset=["ts_code"])
    str_cols = ["ts_code", "symbol", "name", "area", "industry",
                "market", "exchange", "curr_type", "list_status", "is_hs"]
    df = _strip_str_cols(df, str_cols)
    for date_col in ["list_date", "delist_date"]:
        if date_col in df.columns:
            df[date_col] = _to_date(df[date_col])
    df = df.drop_duplicates(subset=["ts_code"])
    return df.reset_index(drop=True)


def clean_stock_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 Tushare daily 接口数据。

    主键: (ts_code, trade_date)
    """
    df = df.dropna(subset=["ts_code", "trade_date"])
    df["trade_date"] = _to_date(df["trade_date"])
    numeric_cols = ["open", "high", "low", "close", "pre_close",
                    "change", "pct_chg", "vol", "amount"]
    df = _to_numeric_cols(df, numeric_cols)
    df = df.drop_duplicates(subset=["ts_code", "trade_date"])
    return df.reset_index(drop=True)


def clean_adj_factor(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 Tushare adj_factor 接口数据。

    主键: (ts_code, trade_date)
    """
    df = df.dropna(subset=["ts_code", "trade_date"])
    df["trade_date"] = _to_date(df["trade_date"])
    df = _to_numeric_cols(df, ["adj_factor"])
    df = df.drop_duplicates(subset=["ts_code", "trade_date"])
    return df.reset_index(drop=True)


def clean_index_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 Tushare index_daily 接口数据。

    主键: (ts_code, trade_date)
    """
    df = df.dropna(subset=["ts_code", "trade_date"])
    df["trade_date"] = _to_date(df["trade_date"])
    numeric_cols = ["open", "high", "low", "close", "pre_close",
                    "change", "pct_chg", "vol", "amount"]
    df = _to_numeric_cols(df, numeric_cols)
    df = df.drop_duplicates(subset=["ts_code", "trade_date"])
    return df.reset_index(drop=True)


def clean_daily_basic(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 Tushare daily_basic 接口数据。

    主键: (ts_code, trade_date)
    """
    df = df.dropna(subset=["ts_code", "trade_date"])
    df["trade_date"] = _to_date(df["trade_date"])
    numeric_cols = [
        "turnover_rate", "turnover_rate_f", "volume_ratio",
        "pe", "pe_ttm", "pb", "ps", "ps_ttm",
        "dv_ratio", "dv_ttm",
        "total_share", "float_share", "free_share",
        "total_mv", "circ_mv",
    ]
    df = _to_numeric_cols(df, numeric_cols)
    df = df.drop_duplicates(subset=["ts_code", "trade_date"])
    return df.reset_index(drop=True)


def clean_industry_member(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗行业成分股映射数据。

    主键: (index_code, ts_code)
    """
    # 统一列名：Tushare 不同接口列名可能不一致
    col_map = {"con_code": "ts_code"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    df = df.dropna(subset=["index_code", "ts_code"])
    str_cols = ["index_code", "ts_code", "index_name", "con_name", "is_new"]
    df = _strip_str_cols(df, str_cols)
    for date_col in ["in_date", "out_date"]:
        if date_col in df.columns:
            df[date_col] = _to_date(df[date_col])
    df = df.drop_duplicates(subset=["index_code", "ts_code"])
    return df.reset_index(drop=True)


def clean_stk_holdernumber(df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗 Tushare stk_holdernumber 接口数据。

    主键: (ts_code, ann_date)
    """
    df = df.dropna(subset=["ts_code", "ann_date"])
    df["ann_date"] = _to_date(df["ann_date"])
    if "end_date" in df.columns:
        df["end_date"] = _to_date(df["end_date"])
    df = _to_numeric_cols(df, ["holder_num"])
    df = _strip_str_cols(df, ["ts_code"])
    df = df.drop_duplicates(subset=["ts_code", "ann_date"])
    return df.reset_index(drop=True)

