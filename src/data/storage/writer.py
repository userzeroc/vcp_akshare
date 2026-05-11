"""
Writer 模块 — 清洗 + Upsert 的高级组合入口

职责:
  将 cleaner.py 和 upsert.py 组合为单次调用的便捷函数。
  调用方只需传入原始 DataFrame 和 Session，无需关心清洗和分批细节。

使用方式::

    from src.database.session import get_session
    from src.data.storage.writer import write_trade_cal, write_stock_basic
    from src.data.storage.writer import write_stock_daily, write_adj_factor

    with get_session() as session:
        write_stock_daily(session, raw_df)
"""

import logging

import pandas as pd
from sqlalchemy.orm import Session

from src.database.models import (
    TradeCal, StockBasic, StockDaily, AdjFactor,
    IndexDaily, DailyBasic, IndustryMember, StkHolderNumber,
)
from src.data.storage.cleaner import (
    clean_trade_cal,
    clean_stock_basic,
    clean_stock_daily,
    clean_adj_factor,
    clean_index_daily,
    clean_daily_basic,
    clean_industry_member,
    clean_stk_holdernumber,
)
from src.data.storage.upsert import upsert_dataframe

logger = logging.getLogger(__name__)


def write_trade_cal(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入交易日历数据。"""
    df = clean_trade_cal(df)
    n = upsert_dataframe(session, TradeCal, df, conflict_columns=["exchange", "cal_date"])
    logger.info("trade_cal: upserted %d rows", n)
    return n


def write_stock_basic(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入股票基本信息数据。"""
    df = clean_stock_basic(df)
    n = upsert_dataframe(session, StockBasic, df, conflict_columns=["ts_code"])
    logger.info("stock_basic: upserted %d rows", n)
    return n


def write_stock_daily(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入日线行情数据。"""
    df = clean_stock_daily(df)
    n = upsert_dataframe(session, StockDaily, df, conflict_columns=["ts_code", "trade_date"])
    logger.info("stock_daily: upserted %d rows", n)
    return n


def write_adj_factor(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入复权因子数据。"""
    df = clean_adj_factor(df)
    n = upsert_dataframe(session, AdjFactor, df, conflict_columns=["ts_code", "trade_date"])
    logger.info("adj_factor: upserted %d rows", n)
    return n


def write_index_daily(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入指数日线行情数据。"""
    df = clean_index_daily(df)
    n = upsert_dataframe(session, IndexDaily, df, conflict_columns=["ts_code", "trade_date"])
    logger.info("index_daily: upserted %d rows", n)
    return n


def write_daily_basic(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入每日基本面指标数据。"""
    df = clean_daily_basic(df)
    n = upsert_dataframe(session, DailyBasic, df, conflict_columns=["ts_code", "trade_date"])
    logger.info("daily_basic: upserted %d rows", n)
    return n


def write_industry_member(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入行业成分股映射数据。"""
    df = clean_industry_member(df)
    n = upsert_dataframe(session, IndustryMember, df, conflict_columns=["index_code", "ts_code"])
    logger.info("industry_member: upserted %d rows", n)
    return n


def write_stk_holdernumber(session: Session, df: pd.DataFrame) -> int:
    """清洗并写入股东人数数据。"""
    df = clean_stk_holdernumber(df)
    n = upsert_dataframe(session, StkHolderNumber, df, conflict_columns=["ts_code", "ann_date"])
    logger.info("stk_holdernumber: upserted %d rows", n)
    return n
