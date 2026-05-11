"""
手动同步特定股票数据脚本

用途:
  如果你只想单独同步或修复某一只（或几只）股票的历史数据，
  而不必执行全市场所有的历史更新，可以使用此脚本。

执行方式::

    # 在代码中调用
    from src.data.sync.manual_sync import sync_single_stock
    sync_single_stock("000001.SZ", "20200101", "20240101")
    
    # 也可在命令行直接执行 (会使用代码内写的默认值)
    python -m src.data.sync.manual_sync
"""

import logging
from typing import Optional

from src.data.fetchers.tushare_client import client
from src.data.storage.writer import (
    write_stock_daily,
    write_adj_factor,
)
from src.database.session import get_session

logger = logging.getLogger(__name__)

def sync_single_stock(ts_code: str, start_date: str = "20100101", end_date: Optional[str] = None) -> None:
    """
    全量/补齐单只股票的日线行情和复权因子。
    """
    logger.info(f"开始同步单只股票: {ts_code} (从 {start_date} 到 {end_date or '今日'})")

    # 1. 同步日线行情 (StockDaily)
    try:
        kwargs = {"ts_code": ts_code, "start_date": start_date}
        if end_date:
            kwargs["end_date"] = end_date
            
        df_daily = client.query("daily", **kwargs)
        with get_session() as session:
            n_daily = write_stock_daily(session, df_daily)
        logger.info(f"[{ts_code}] 日线同步完成，写入 {n_daily} 行。")
    except Exception as e:
        logger.error(f"[{ts_code}] 日线同步失败: {e}")

    # 2. 同步复权因子 (AdjFactor)
    try:
        df_adj = client.query("adj_factor", **kwargs)
        with get_session() as session:
            n_adj = write_adj_factor(session, df_adj)
        logger.info(f"[{ts_code}] 复权因子同步完成，写入 {n_adj} 行。")
    except Exception as e:
        logger.error(f"[{ts_code}] 复权因子同步失败: {e}")

    logger.info(f"[{ts_code}] 数据同步结束。")


def sync_index_data(ts_code: str, start_date: str = "20100101", end_date: Optional[str] = None) -> None:
    """
    同步指数日线行情。
    Tushare 接口: index_daily
    """
    logger.info(f"开始同步指数: {ts_code} (从 {start_date} 到 {end_date or '今日'})")

    try:
        kwargs = {"ts_code": ts_code, "start_date": start_date}
        if end_date:
            kwargs["end_date"] = end_date
            
        # 使用 index_daily 接口
        df_daily = client.query("index_daily", **kwargs)
        with get_session() as session:
            n_daily = write_stock_daily(session, df_daily)
        logger.info(f"[{ts_code}] 指数日线同步完成，写入 {n_daily} 行。")
    except Exception as e:
        logger.error(f"[{ts_code}] 指数同步失败: {e}")

    logger.info(f"[{ts_code}] 数据同步结束。")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    # 演示：同步大盘指数
    indices = ["000001.SH", "399001.SZ"]
    for code in indices:
        sync_index_data(code, start_date="20200101")
