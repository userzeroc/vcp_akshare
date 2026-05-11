"""
每日增量同步 — 收盘后定时执行

策略:
  1. 查询本地各表最新日期
  2. 从 Tushare 只拉"最新日期之后"的数据
  3. 幂等写入（已有数据不重复，当日重跑安全）

执行方式::

    python -m src.data.sync.daily_sync

建议配合 cron 或 APScheduler 在每个交易日 17:00 后执行。
"""

import logging
import os
import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import func

from src.data.fetchers.tushare_client import client
from src.data.storage.writer import (
    write_trade_cal,
    write_stock_basic,
    write_stock_daily,
    write_adj_factor,
    write_index_daily,
    write_daily_basic,
    write_industry_member,
    write_stk_holdernumber,
)
from src.database.session import get_session
from src.database.models import TradeCal, StockDaily, AdjFactor, IndexDaily, DailyBasic, StockBasic, StkHolderNumber
from src.data.sync import BENCHMARK_INDICES, SW_INDUSTRY_INDICES, ALL_INDICES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 辅助：查询各表本地最新日期
# ---------------------------------------------------------------------------

def _get_latest_trade_cal_date(exchange: str = "SSE") -> Optional[datetime.date]:
    with get_session() as session:
        return session.query(func.max(TradeCal.cal_date)).filter(
            TradeCal.exchange == exchange
        ).scalar()


def _get_latest_daily_date() -> Optional[datetime.date]:
    """trade_daily 里最新的 trade_date（全市场最大值）。"""
    with get_session() as session:
        return session.query(func.max(StockDaily.trade_date)).scalar()


def _get_latest_adj_date() -> Optional[datetime.date]:
    with get_session() as session:
        return session.query(func.max(AdjFactor.trade_date)).scalar()


def _get_latest_index_date() -> Optional[datetime.date]:
    """index_daily 表最新 trade_date。"""
    with get_session() as session:
        return session.query(func.max(IndexDaily.trade_date)).scalar()


def _get_latest_daily_basic_date() -> Optional[datetime.date]:
    """daily_basic 表最新 trade_date。"""
    with get_session() as session:
        return session.query(func.max(DailyBasic.trade_date)).scalar()


def _get_latest_holdernumber_date() -> Optional[datetime.date]:
    """stk_holdernumber 表最新 ann_date。"""
    with get_session() as session:
        return session.query(func.max(StkHolderNumber.ann_date)).scalar()


def _date_to_str(d: Optional[datetime.date]) -> str:
    """date → 'YYYYMMDD'，若为 None 返回安全默认起始日。"""
    return d.strftime("%Y%m%d") if d else "20100101"


# ---------------------------------------------------------------------------
# 增量同步函数
# ---------------------------------------------------------------------------

def sync_trade_cal_incremental(exchange: str = "SSE") -> None:
    """增量同步交易日历至今日。"""
    latest = _get_latest_trade_cal_date(exchange)
    start = _date_to_str(latest)
    today = datetime.date.today().strftime("%Y%m%d")

    if latest and latest >= datetime.date.today():
        logger.info("trade_cal 已是最新，跳过")
        return

    logger.info("增量同步 trade_cal: %s → %s", start, today)
    df = client.query("trade_cal", exchange=exchange, start_date=start, end_date=today)
    with get_session() as session:
        n = write_trade_cal(session, df)
    logger.info("trade_cal 增量写入 %d 行", n)


def sync_stock_basic_incremental() -> None:
    """
    stock_basic 没有日期过滤参数，每次全量拉取再 upsert 覆盖。
    数据量约 5000 行，速度很快（< 1秒），直接全量刷新即可。
    """
    logger.info("刷新 stock_basic（全量，约 5000行）")
    for status in ["L", "D", "P"]:
        df = client.query("stock_basic", list_status=status,
                          fields="ts_code,symbol,name,area,industry,market,exchange,"
                                 "curr_type,list_status,list_date,delist_date,is_hs")
        with get_session() as session:
            write_stock_basic(session, df)
    logger.info("stock_basic 刷新完成")


def sync_stock_daily_incremental() -> None:
    """
    增量同步日线行情：从本地最新交易日的下一天拉到今天。
    按交易日逐日拉取（全市场单日数据约 5000 行，不超限）。
    """
    latest = _get_latest_daily_date()
    start_date = latest + datetime.timedelta(days=1) if latest else datetime.date(2010, 1, 1)
    today = datetime.date.today()

    if start_date > today:
        logger.info("stock_daily 已是最新，跳过")
        return

    # 从 trade_cal 获取需要补齐的交易日列表
    with get_session() as session:
        rows = (
            session.query(TradeCal.cal_date)
            .filter(
                TradeCal.exchange == "SSE",
                TradeCal.is_open == 1,
                TradeCal.cal_date >= start_date,
                TradeCal.cal_date <= today,
            )
            .order_by(TradeCal.cal_date)
            .all()
        )
    trade_dates = [r.cal_date for r in rows]

    if not trade_dates:
        logger.info("无需补齐的交易日")
        return

    logger.info("增量补齐日线: %s → %s，共 %d 天",
                trade_dates[0], trade_dates[-1], len(trade_dates))

    for trade_date in trade_dates:
        date_str = trade_date.strftime("%Y%m%d")
        try:
            df = client.query("daily", trade_date=date_str)
            with get_session() as session:
                write_stock_daily(session, df)
        except Exception as exc:
            logger.error("日线增量同步失败 [%s]: %s", date_str, exc)

    logger.info("stock_daily 增量同步完成")


def sync_adj_factor_incremental() -> None:
    """增量同步复权因子。"""
    latest = _get_latest_adj_date()
    start_date = latest + datetime.timedelta(days=1) if latest else datetime.date(2010, 1, 1)
    today = datetime.date.today()

    if start_date > today:
        logger.info("adj_factor 已是最新，跳过")
        return

    with get_session() as session:
        rows = (
            session.query(TradeCal.cal_date)
            .filter(
                TradeCal.exchange == "SSE",
                TradeCal.is_open == 1,
                TradeCal.cal_date >= start_date,
                TradeCal.cal_date <= today,
            )
            .order_by(TradeCal.cal_date)
            .all()
        )
    trade_dates = [r.cal_date for r in rows]

    logger.info("增量补齐复权因子: %d 天", len(trade_dates))
    for trade_date in trade_dates:
        date_str = trade_date.strftime("%Y%m%d")
        try:
            df = client.query("adj_factor", trade_date=date_str)
            with get_session() as session:
                write_adj_factor(session, df)
        except Exception as exc:
            logger.error("复权因子增量同步失败 [%s]: %s", date_str, exc)

    logger.info("adj_factor 增量同步完成")


def sync_index_daily_incremental() -> None:
    """增量同步指数日线行情。"""
    latest = _get_latest_index_date()
    start_date = latest + datetime.timedelta(days=1) if latest else datetime.date(2023, 1, 1)
    today = datetime.date.today()

    if start_date > today:
        logger.info("index_daily 已是最新，跳过")
        return

    end_str = today.strftime("%Y%m%d")
    start_str = start_date.strftime("%Y%m%d")

    logger.info("增量同步指数日线: %s → %s", start_str, end_str)

    for ts_code in ALL_INDICES:
        try:
            df = client.query("index_daily", ts_code=ts_code,
                              start_date=start_str, end_date=end_str)
            if df is not None and not df.empty:
                with get_session() as session:
                    write_index_daily(session, df)
        except Exception as exc:
            logger.error("指数日线增量同步失败 [%s]: %s", ts_code, exc)

    logger.info("index_daily 增量同步完成")


def sync_daily_basic_incremental() -> None:
    """增量同步每日基本面指标。"""
    latest = _get_latest_daily_basic_date()
    start_date = latest + datetime.timedelta(days=1) if latest else datetime.date(2023, 1, 1)
    today = datetime.date.today()

    if start_date > today:
        logger.info("daily_basic 已是最新，跳过")
        return

    with get_session() as session:
        rows = (
            session.query(TradeCal.cal_date)
            .filter(
                TradeCal.exchange == "SSE",
                TradeCal.is_open == 1,
                TradeCal.cal_date >= start_date,
                TradeCal.cal_date <= today,
            )
            .order_by(TradeCal.cal_date)
            .all()
        )
    trade_dates = [r.cal_date for r in rows]

    if not trade_dates:
        logger.info("daily_basic: 无需补齐的交易日")
        return

    logger.info("增量补齐 daily_basic: %s → %s，共 %d 天",
                trade_dates[0], trade_dates[-1], len(trade_dates))

    for i, trade_date in enumerate(trade_dates, 1):
        date_str = trade_date.strftime("%Y%m%d")
        try:
            df = client.query("daily_basic", trade_date=date_str,
                              fields="ts_code,trade_date,turnover_rate,turnover_rate_f,"
                                     "volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,"
                                     "dv_ratio,dv_ttm,"
                                     "total_share,float_share,free_share,"
                                     "total_mv,circ_mv")
            if df is not None and not df.empty:
                with get_session() as session:
                    write_daily_basic(session, df)
            if i % 50 == 0:
                logger.info("daily_basic 进度: %d/%d (%s)", i, len(trade_dates), date_str)
        except Exception as exc:
            logger.error("daily_basic 增量同步失败 [%s]: %s", date_str, exc)

    logger.info("daily_basic 增量同步完成")


def sync_stk_holdernumber_incremental() -> None:
    """
    增量同步股东人数。

    股东人数为不定期公布数据，增量策略：
    获取本地最新 ann_date，从该日期起重新拉取所有上市股票的数据。
    """
    latest = _get_latest_holdernumber_date()
    start_date = latest.strftime("%Y%m%d") if latest else "20230101"
    today = datetime.date.today().strftime("%Y%m%d")

    # 获取所有上市股票
    with get_session() as session:
        rows = (
            session.query(StockBasic.ts_code)
            .filter(StockBasic.list_status == "L")
            .order_by(StockBasic.ts_code)
            .all()
        )
    stock_codes = [r.ts_code for r in rows]

    if not stock_codes:
        logger.info("stk_holdernumber: stock_basic 为空，跳过")
        return

    logger.info("增量同步股东人数: %s → %s，%d 只股票", start_date, today, len(stock_codes))

    total_rows = 0
    for i, ts_code in enumerate(stock_codes, 1):
        try:
            df = client.query(
                "stk_holdernumber",
                ts_code=ts_code,
                start_date=start_date,
                end_date=today,
            )
            if df is not None and not df.empty:
                with get_session() as session:
                    n = write_stk_holdernumber(session, df)
                total_rows += n
            if i % 200 == 0:
                logger.info("stk_holdernumber 进度: %d/%d, 累计 %d 行",
                            i, len(stock_codes), total_rows)
        except Exception as exc:
            logger.error("stk_holdernumber 增量同步失败 [%s]: %s", ts_code, exc)

    logger.info("stk_holdernumber 增量同步完成，共 %d 行", total_rows)


def sync_industry_member_incremental() -> None:
    """
    增量同步行业成分股映射。

    行业成分股数据量极小（~5000 行），每次全量刷新即可。
    """
    logger.info("刷新行业成分股映射（全量）")

    total_rows = 0
    for i, index_code in enumerate(SW_INDUSTRY_INDICES, 1):
        try:
            df = client.query("index_member", index_code=index_code)
            if df is not None and not df.empty:
                with get_session() as session:
                    n = write_industry_member(session, df)
                total_rows += n
        except Exception as exc:
            logger.error("industry_member 同步失败 [%s]: %s", index_code, exc)

    logger.info("industry_member 刷新完成，共 %d 行", total_rows)


# ---------------------------------------------------------------------------
# 每日定时执行入口
# ---------------------------------------------------------------------------

def run_daily_sync() -> None:
    """每日收盘后（建议 17:00+）调用此函数完成增量同步。"""
    # 核心日志配置
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "daily_sync.log")
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除旧的 Handlers (防止 basicConfig 干扰)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # 1. 终端 Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)
    
    # 2. 文件 Handler (追加模式)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    logger.info("===== 每日增量同步开始 =====")
    sync_trade_cal_incremental()
    sync_stock_basic_incremental()
    sync_stock_daily_incremental()
    sync_adj_factor_incremental()
    sync_index_daily_incremental()
    sync_daily_basic_incremental()
    sync_industry_member_incremental()
    sync_stk_holdernumber_incremental()
    logger.info("===== 每日增量同步完成 =====")


if __name__ == "__main__":
    run_daily_sync()
