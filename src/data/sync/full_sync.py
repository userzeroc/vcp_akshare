"""
全量历史数据同步 — 首次初始化使用

用途:
  第一次建库时，拉取所有历史数据写入 PostgreSQL。
  后续日常更新请使用 daily_sync.py。

注意:
  - 2100分账号对部分接口有频率限制，全量同步约需数小时
  - 支持断点续传：已存在的数据通过 upsert 跳过，不会重复写入
  - daily 行情按"全市场单日"批次拉取（每次 query 一天），避免单次超限

覆盖的表（按依赖顺序）:
  1. trade_cal        — 交易日历（其他模块的前置依赖）
  2. stock_basic      — 股票基本信息
  3. stock_daily      — 日线行情
  4. adj_factor       — 复权因子
  5. index_daily      — 指数日线
  6. daily_basic      — 每日基本面指标
  7. industry_member  — 行业成分股映射
  8. stk_holdernumber — 股东人数

执行方式::

    python -m src.data.sync.full_sync
    python -m src.data.sync.full_sync --start 20220101
    python -m src.data.sync.full_sync --only daily --start 20100101
    python -m src.data.sync.full_sync --only holder --start 20230101
"""

import logging
import datetime
from typing import Optional

import pandas as pd

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
from src.database.models import TradeCal, StockBasic
from src.data.sync import (
    BENCHMARK_INDICES, SW_INDUSTRY_INDICES, ALL_INDICES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 辅助：从本地获取历史交易日列表
# ---------------------------------------------------------------------------

def _get_all_trade_dates(exchange: str = "SSE") -> list[datetime.date]:
    """从本地 trade_cal 表读取所有交易日，按日期升序返回。"""
    with get_session() as session:
        rows = (
            session.query(TradeCal.cal_date)
            .filter(TradeCal.exchange == exchange, TradeCal.is_open == 1)
            .order_by(TradeCal.cal_date)
            .all()
        )
    return [r.cal_date for r in rows]


def _filter_dates(
    trade_dates: list[datetime.date],
    start_date: str,
    end_date: Optional[str] = None,
) -> list[datetime.date]:
    """按起止日期过滤交易日列表。"""
    start = datetime.datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.datetime.strptime(end_date, "%Y%m%d").date() if end_date else datetime.date.today()
    return [d for d in trade_dates if start <= d <= end]


def _get_listed_stock_codes() -> list[str]:
    """获取所有上市股票代码列表。"""
    with get_session() as session:
        rows = (
            session.query(StockBasic.ts_code)
            .filter(StockBasic.list_status == "L")
            .order_by(StockBasic.ts_code)
            .all()
        )
    return [r.ts_code for r in rows]


# ---------------------------------------------------------------------------
# 1. 交易日历
# ---------------------------------------------------------------------------

def sync_trade_cal(
    start_date: str = "19900101",
    end_date: Optional[str] = None,
    exchange: str = "SSE",
) -> None:
    """全量同步交易日历（建议最先执行，其他模块依赖它）。"""
    if end_date is None:
        end_date = datetime.date.today().strftime("%Y%m%d")

    logger.info("同步交易日历: %s ~ %s (%s)", start_date, end_date, exchange)
    df = client.query("trade_cal", exchange=exchange, start_date=start_date, end_date=end_date)
    with get_session() as session:
        n = write_trade_cal(session, df)
    logger.info("trade_cal 完成，共写入 %d 行", n)


# ---------------------------------------------------------------------------
# 2. 股票基本信息
# ---------------------------------------------------------------------------

def sync_stock_basic() -> None:
    """
    全量同步股票基本信息。

    list_status: L=上市 D=退市 P=暂停（分 3 次调用覆盖全部状态）
    """
    for status in ["L", "D", "P"]:
        logger.info("同步 stock_basic [list_status=%s]", status)
        df = client.query("stock_basic", list_status=status,
                          fields="ts_code,symbol,name,area,industry,market,exchange,"
                                 "curr_type,list_status,list_date,delist_date,is_hs")
        with get_session() as session:
            n = write_stock_basic(session, df)
        logger.info("stock_basic [%s] 完成，共写入 %d 行", status, n)


# ---------------------------------------------------------------------------
# 3. 日线行情
# ---------------------------------------------------------------------------

def sync_stock_daily_all(start_date: str = "20100101", end_date: Optional[str] = None) -> None:
    """
    全量同步日线行情（按交易日逐日拉取全市场数据）。

    策略:
      逐日调用 daily 接口获取当日全市场数据，写入后继续下一天。
      这样单次调用数据量小，不易超出 Tushare 单次返回上限（6000行）。
    """
    trade_dates = _filter_dates(_get_all_trade_dates(), start_date, end_date)

    total = len(trade_dates)
    logger.info("开始全量日线同步，共 %d 个交易日 (%s → %s)", total, start_date, end_date or "今日")

    for i, trade_date in enumerate(trade_dates, 1):
        date_str = trade_date.strftime("%Y%m%d")
        try:
            df = client.query("daily", trade_date=date_str)
            with get_session() as session:
                write_stock_daily(session, df)
            if i % 100 == 0:
                logger.info("stock_daily 进度: %d/%d (%s)", i, total, date_str)
        except Exception as exc:
            logger.error("日线同步失败 [%s]: %s", date_str, exc)
            # 不中断，继续下一天（upsert 幂等，下次重跑会补齐）

    logger.info("全量日线同步完成")


# ---------------------------------------------------------------------------
# 4. 复权因子
# ---------------------------------------------------------------------------

def sync_adj_factor_all(start_date: str = "20100101", end_date: Optional[str] = None) -> None:
    """
    全量同步复权因子（按交易日逐日拉取）。
    """
    trade_dates = _filter_dates(_get_all_trade_dates(), start_date, end_date)

    total = len(trade_dates)
    logger.info("开始全量复权因子同步，共 %d 个交易日 (%s → %s)", total, start_date, end_date or "今日")

    for i, trade_date in enumerate(trade_dates, 1):
        date_str = trade_date.strftime("%Y%m%d")
        try:
            df = client.query("adj_factor", trade_date=date_str)
            with get_session() as session:
                write_adj_factor(session, df)
            if i % 100 == 0:
                logger.info("adj_factor 进度: %d/%d (%s)", i, total, date_str)
        except Exception as exc:
            logger.error("复权因子同步失败 [%s]: %s", date_str, exc)

    logger.info("全量复权因子同步完成")


# ---------------------------------------------------------------------------
# 5. 指数日线
# ---------------------------------------------------------------------------

def sync_index_daily_all(
    start_date: str = "20230101",
    end_date: Optional[str] = None,
    indices: list[str] = None,
) -> None:
    """
    全量同步指数日线行情。

    按指数逐个拉取（每个指数一次查询返回全部日期数据，不超限）。
    """
    if indices is None:
        indices = ALL_INDICES
    if end_date is None:
        end_date = datetime.date.today().strftime("%Y%m%d")

    total = len(indices)
    logger.info("同步指数日线: %d 个指数, %s → %s", total, start_date, end_date)

    for i, ts_code in enumerate(indices, 1):
        try:
            df = client.query("index_daily", ts_code=ts_code,
                              start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                with get_session() as session:
                    n = write_index_daily(session, df)
                logger.info("[%d/%d] %s: 写入 %d 行", i, total, ts_code, n)
            else:
                logger.warning("[%d/%d] %s: 无数据", i, total, ts_code)
        except Exception as exc:
            logger.error("[%d/%d] %s 同步失败: %s", i, total, ts_code, exc)

    logger.info("指数日线同步完成")


# ---------------------------------------------------------------------------
# 6. 每日基本面指标
# ---------------------------------------------------------------------------

def sync_daily_basic_all(start_date: str = "20230101", end_date: Optional[str] = None) -> None:
    """
    全量同步每日基本面指标（按交易日逐日拉取全市场数据）。

    数据量约 5000 行/天，与 stock_daily 同步策略一致。
    """
    trade_dates = _filter_dates(_get_all_trade_dates(), start_date, end_date)

    if not trade_dates:
        logger.info("daily_basic: 无需同步的交易日")
        return

    total = len(trade_dates)
    logger.info("同步 daily_basic: %s → %s，共 %d 天",
                trade_dates[0], trade_dates[-1], total)

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
                logger.info("daily_basic 进度: %d/%d (%s)", i, total, date_str)
        except Exception as exc:
            logger.error("daily_basic 同步失败 [%s]: %s", date_str, exc)

    logger.info("daily_basic 同步完成")


# ---------------------------------------------------------------------------
# 7. 行业成分股映射
# ---------------------------------------------------------------------------

def sync_industry_member_all(indices: list[str] = None) -> None:
    """
    全量同步行业成分股映射数据。

    数据量极小（~5000 行），每次全量刷新。
    """
    if indices is None:
        indices = SW_INDUSTRY_INDICES

    logger.info("同步行业成分股映射: %d 个行业指数", len(indices))

    total_rows = 0
    for i, index_code in enumerate(indices, 1):
        try:
            df = client.query("index_member", index_code=index_code)
            if df is not None and not df.empty:
                with get_session() as session:
                    n = write_industry_member(session, df)
                total_rows += n
                logger.info("[%d/%d] %s: 写入 %d 条成分股",
                            i, len(indices), index_code, n)
            else:
                logger.warning("[%d/%d] %s: 无数据", i, len(indices), index_code)
        except Exception as exc:
            logger.error("[%d/%d] %s 同步失败: %s", i, len(indices), index_code, exc)

    logger.info("行业成分股映射同步完成，共 %d 行", total_rows)


# ---------------------------------------------------------------------------
# 8. 股东人数
# ---------------------------------------------------------------------------

def sync_stk_holdernumber_all(
    start_date: str = "20230101",
    end_date: Optional[str] = None,
) -> None:
    """
    全量同步股东人数数据。

    按股票逐只拉取（Tushare stk_holdernumber 接口每次返回单只股票的全部记录）。
    数据为不定期公布（通常随季报/年报），单只股票记录数较少。
    """
    if end_date is None:
        end_date = datetime.date.today().strftime("%Y%m%d")

    stock_codes = _get_listed_stock_codes()
    if not stock_codes:
        logger.warning("stock_basic 为空，请先同步 stock_basic")
        return

    total = len(stock_codes)
    logger.info("同步股东人数: %d 只股票, %s → %s", total, start_date, end_date)

    total_rows = 0
    for i, ts_code in enumerate(stock_codes, 1):
        try:
            df = client.query(
                "stk_holdernumber",
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
            if df is not None and not df.empty:
                with get_session() as session:
                    n = write_stk_holdernumber(session, df)
                total_rows += n
            if i % 100 == 0:
                logger.info("stk_holdernumber 进度: %d/%d, 累计 %d 行", i, total, total_rows)
        except Exception as exc:
            logger.error("stk_holdernumber 同步失败 [%s]: %s", ts_code, exc)

    logger.info("股东人数同步完成，共 %d 行", total_rows)


# ---------------------------------------------------------------------------
# 一键全量初始化入口
# ---------------------------------------------------------------------------

def run_full_sync(start_date: str = "20100101", end_date: Optional[str] = None) -> None:
    """
    按依赖顺序执行全量同步:
      1. trade_cal        — 交易日历（前置依赖）
      2. stock_basic      — 股票基本信息
      3. stock_daily      — 日线行情（逐日拉取）
      4. adj_factor       — 复权因子（逐日拉取）
      5. index_daily      — 指数日线
      6. daily_basic      — 每日基本面指标
      7. industry_member  — 行业成分股映射
      8. stk_holdernumber — 股东人数
    """
    logger.info("===== 全量数据初始化开始 (范围: %s → %s) =====", start_date, end_date or "今日")

    # 第一阶段：基础依赖
    sync_trade_cal(start_date=start_date, end_date=end_date)
    sync_stock_basic()

    # 第二阶段：核心行情数据（从 start_date 开始）
    sync_stock_daily_all(start_date=start_date, end_date=end_date)
    sync_adj_factor_all(start_date=start_date, end_date=end_date)

    # 第三阶段：扩展数据（从 2023 开始，或跟随 start_date 取较晚者）
    ext_start = max(start_date, "20230101")
    sync_index_daily_all(start_date=ext_start, end_date=end_date)
    sync_daily_basic_all(start_date=ext_start, end_date=end_date)
    sync_industry_member_all()
    sync_stk_holdernumber_all(start_date=ext_start, end_date=end_date)

    logger.info("===== 全量数据初始化完成 =====")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

ALL_TABLE_CHOICES = ["cal", "basic", "daily", "adj", "index", "dbasic", "member", "holder"]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="全量历史数据同步（支持全部 8 张数据表）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
表名映射:
  cal    = trade_cal        交易日历
  basic  = stock_basic      股票基本信息
  daily  = stock_daily      日线行情
  adj    = adj_factor       复权因子
  index  = index_daily      指数日线
  dbasic = daily_basic      每日基本面指标
  member = industry_member  行业成分股映射
  holder = stk_holdernumber 股东人数

示例:
  python -m src.data.sync.full_sync                          # 全部表
  python -m src.data.sync.full_sync --only daily             # 仅日线
  python -m src.data.sync.full_sync --only holder            # 仅股东人数
  python -m src.data.sync.full_sync --start 20220101         # 从2022开始
        """,
    )
    parser.add_argument("--start", type=str, default="20100101", help="起始日期 (YYYYMMDD)，默认 20100101")
    parser.add_argument("--end",   type=str, default=None,        help="截止日期 (YYYYMMDD)，默认至今")
    parser.add_argument("--only",  type=str, default=None,
                        choices=ALL_TABLE_CHOICES,
                        help="仅同步指定表（见下方映射）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    dispatch = {
        "cal":    lambda: sync_trade_cal(start_date=args.start, end_date=args.end),
        "basic":  lambda: sync_stock_basic(),
        "daily":  lambda: sync_stock_daily_all(start_date=args.start, end_date=args.end),
        "adj":    lambda: sync_adj_factor_all(start_date=args.start, end_date=args.end),
        "index":  lambda: sync_index_daily_all(start_date=args.start, end_date=args.end),
        "dbasic": lambda: sync_daily_basic_all(start_date=args.start, end_date=args.end),
        "member": lambda: sync_industry_member_all(),
        "holder": lambda: sync_stk_holdernumber_all(start_date=args.start, end_date=args.end),
    }

    if args.only:
        dispatch[args.only]()
    else:
        run_full_sync(start_date=args.start, end_date=args.end)
