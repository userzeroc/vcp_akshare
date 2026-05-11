"""
StockReader — 数据库读取核心模块

查询方法汇总:
  get_daily()         - 获取单只/多只股票日线（不复权）
  get_daily_adj()     - 获取前复权或后复权日线
  get_cross_section() - 获取某一交易日全市场截面数据
  get_stock_list()    - 获取股票列表（可过滤上市状态）
  get_trade_cal()     - 获取交易日历
  is_trade_date()     - 判断某天是否为交易日
  get_latest_date()   - 获取本地数据最新日期

复权原理 (Tushare adj_factor):
  后复权价格 = 原始收盘价 × adj_factor
  前复权价格 = 后复权价格 / 当日 adj_factor（即当日 adj_factor 会被标准化为 1.0）
"""

import datetime
from decimal import Decimal
from typing import Optional, Sequence, Union

import pandas as pd
from sqlalchemy import func, and_

from src.database.session import get_session
from src.database.models import (
    StockBasic,
    StockDaily,
    AdjFactor,
    TradeCal,
    IndexDaily,
    DailyBasic,
    StkHolderNumber,
)

# 日期参数类型
_DateLike = Union[str, datetime.date]


def _to_date(d: _DateLike) -> datetime.date:
    """将 'YYYYMMDD' 字符串或 datetime.date 统一转为 datetime.date。"""
    if isinstance(d, str):
        return datetime.datetime.strptime(d, "%Y%m%d").date()
    return d


class StockReader:
    """
    数据库数据读取器。

    策略模块推荐通过此类读取所有行情数据，不要直接写 SQLAlchemy 查询。
    """

    # ------------------------------------------------------------------
    # 通用辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _orm_to_dataframe(rows, columns: Sequence[str]) -> pd.DataFrame:
        """
        将 ORM 查询结果列表统一转为 DataFrame。

        自动处理:
          - Decimal → float（Numeric 字段）
          - None 保持 None
        """
        if not rows:
            return pd.DataFrame()

        def _convert(val):
            if isinstance(val, Decimal):
                return float(val)
            return val

        return pd.DataFrame([
            {col: _convert(getattr(r, col, None)) for col in columns}
            for r in rows
        ])

    # ------------------------------------------------------------------
    # 1. 日线行情（不复权）
    # ------------------------------------------------------------------

    def get_daily(
        self,
        ts_code: Union[str, list[str]],
        start_date: Optional[_DateLike] = None,
        end_date: Optional[_DateLike] = None,
    ) -> pd.DataFrame:
        """
        获取单只或多只股票的原始日线数据（不复权）。

        参数:
            ts_code    - 股票代码，如 '000001.SZ' 或列表 ['000001.SZ', '600519.SH']
            start_date - 起始日期，如 '20230101' 或 datetime.date
            end_date   - 截止日期，不传则取所有最新数据

        返回:
            DataFrame，列: [ts_code, trade_date, open, high, low, close,
                             pre_close, change, pct_chg, vol, amount]
        """
        codes = [ts_code] if isinstance(ts_code, str) else ts_code

        with get_session() as session:
            q = session.query(StockDaily).filter(StockDaily.ts_code.in_(codes))

            if start_date:
                q = q.filter(StockDaily.trade_date >= _to_date(start_date))
            if end_date:
                q = q.filter(StockDaily.trade_date <= _to_date(end_date))

            q = q.order_by(StockDaily.ts_code, StockDaily.trade_date)
            rows = q.all()

        _DAILY_COLS = ["ts_code", "trade_date", "open", "high", "low",
                       "close", "pre_close", "change", "pct_chg", "vol", "amount"]
        return self._orm_to_dataframe(rows, _DAILY_COLS)

    # ------------------------------------------------------------------
    # 2. 复权日线
    # ------------------------------------------------------------------

    def get_daily_adj(
        self,
        ts_code: str,
        start_date: Optional[_DateLike] = None,
        end_date: Optional[_DateLike] = None,
        mode: str = "qfq",  # "qfq"=前复权  "hfq"=后复权  "none"=不复权
    ) -> pd.DataFrame:
        """
        获取单只股票的复权日线数据。

        参数:
            ts_code    - 股票代码
            start_date - 起始日期
            end_date   - 截止日期
            mode       - 复权方式: 'qfq'(前复权) / 'hfq'(后复权) / 'none'(不复权)

        返回:
            DataFrame，在原始列基础上增加:
              adj_factor  - 当日复权因子
              close_adj   - 复权后收盘价（其他价格列同样已复权）

        复权价格计算原理:
            后复权 (hfq): price_hfq = price × adj_factor
            前复权 (qfq): price_qfq = price × adj_factor / latest_adj_factor
                          效果是让最新价格等于原始价，往前的历史价格按比例缩放
        """
        df = self.get_daily(ts_code, start_date, end_date)
        if df.empty or mode == "none":
            return df

        # 拉取对应时间段的复权因子
        codes = [ts_code]
        with get_session() as session:
            q = session.query(AdjFactor).filter(AdjFactor.ts_code == ts_code)
            if start_date:
                q = q.filter(AdjFactor.trade_date >= _to_date(start_date))
            if end_date:
                q = q.filter(AdjFactor.trade_date <= _to_date(end_date))
            adj_rows = q.order_by(AdjFactor.trade_date).all()

        if not adj_rows:
            # 没有复权因子，原样返回（加警告列）
            df["adj_factor"] = None
            return df

        adj_df = pd.DataFrame(
            [{"trade_date": r.trade_date, "adj_factor": float(r.adj_factor)}
             for r in adj_rows]
        )

        df = df.merge(adj_df, on="trade_date", how="left")
        df["adj_factor"] = df["adj_factor"].ffill().fillna(1.0)

        price_cols = ["open", "high", "low", "close", "pre_close"]

        if mode == "hfq":
            for col in price_cols:
                df[col] = df[col] * df["adj_factor"]

        elif mode == "qfq":
            # 用最新一个 adj_factor 标准化，让最近价格保持不变
            latest_factor = df["adj_factor"].iloc[-1]
            for col in price_cols:
                df[col] = df[col] * df["adj_factor"] / latest_factor

        return df

    # ------------------------------------------------------------------
    # 3. 全市场截面（某交易日所有股票）
    # ------------------------------------------------------------------

    def get_cross_section(
        self,
        trade_date: _DateLike,
        fields: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        获取某一交易日的全市场截面数据（所有股票当天的行情）。

        应用场景: 选股排名、涨跌幅榜、截面因子计算。

        参数:
            trade_date - 交易日期，如 '20240104'
            fields     - 需要返回的列名，None 表示全部列

        返回:
            DataFrame（约 5000 行 × N列）
        """
        date = _to_date(trade_date)
        with get_session() as session:
            rows = (
                session.query(StockDaily)
                .filter(StockDaily.trade_date == date)
                .order_by(StockDaily.ts_code)
                .all()
            )

        _CROSS_COLS = ["ts_code", "trade_date", "open", "high", "low",
                       "close", "pct_chg", "vol", "amount"]
        df = self._orm_to_dataframe(rows, _CROSS_COLS)

        if fields and not df.empty:
            df = df[[c for c in fields if c in df.columns]]

        return df

    # ------------------------------------------------------------------
    # 4. 股票列表
    # ------------------------------------------------------------------

    def get_stock_list(
        self,
        list_status: Optional[str] = "L",
        exchange: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取股票基本信息表。

        参数:
            list_status - 'L'=上市(默认) / 'D'=退市 / 'P'=暂停 / None=全部
            exchange    - 'SSE'=上交所 / 'SZSE'=深交所 / None=全部

        返回:
            DataFrame，列: [ts_code, name, industry, market, list_date, ...]
        """
        with get_session() as session:
            q = session.query(StockBasic)
            if list_status:
                q = q.filter(StockBasic.list_status == list_status)
            if exchange:
                q = q.filter(StockBasic.exchange == exchange)
            rows = q.order_by(StockBasic.ts_code).all()

        _BASIC_COLS = ["ts_code", "symbol", "name", "area", "industry",
                       "market", "exchange", "list_status", "list_date",
                       "delist_date", "is_hs"]
        return self._orm_to_dataframe(rows, _BASIC_COLS)

    def get_industry_info(self, ts_code: str) -> Optional[str]:
        """获取指定股票所属的行业名称。"""
        with get_session() as session:
            row = session.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()
            return row.industry if row else None

    def get_industry_performance(
        self, industry: str, trade_date: _DateLike, window: int = 5
    ) -> float:
        """
        计算某一行业在指定日期的平均收益率（简单共振指标）。
        
        参数:
            industry   - 行业名称
            trade_date - 目标日期
            window     - 回溯天数 (计算区间收益)
        """
        date_obj = _to_date(trade_date)
        
        # 1. 获取该行业所有股票
        with get_session() as session:
            peer_codes = [
                r.ts_code for r in session.query(StockBasic.ts_code).filter(StockBasic.industry == industry).all()
            ]
        
        if not peer_codes:
            return 0.0
            
        # 2. 获取这些股票在当天的涨跌幅
        with get_session() as session:
            rows = session.query(StockDaily.pct_chg).filter(
                StockDaily.ts_code.in_(peer_codes),
                StockDaily.trade_date == date_obj
            ).all()
            
        if not rows:
            return 0.0
            
        pct_chgs = [float(r.pct_chg) for r in rows if r.pct_chg is not None]
        return sum(pct_chgs) / len(pct_chgs) if pct_chgs else 0.0

    # ------------------------------------------------------------------
    # 5. 交易日历
    # ------------------------------------------------------------------

    def get_trade_cal(
        self,
        start_date: Optional[_DateLike] = None,
        end_date: Optional[_DateLike] = None,
        exchange: str = "SSE",
        is_open: Optional[int] = 1,  # 1=只返回交易日 None=返回全部
    ) -> pd.DataFrame:
        """
        获取交易日历。

        参数:
            start_date - 起始日期
            end_date   - 截止日期
            exchange   - 交易所，默认上交所 'SSE'
            is_open    - 1=只返回交易日（默认），None=返回全部日历日

        返回:
            DataFrame，列: [exchange, cal_date, is_open, pretrade_date]
        """
        with get_session() as session:
            q = session.query(TradeCal).filter(TradeCal.exchange == exchange)
            if start_date:
                q = q.filter(TradeCal.cal_date >= _to_date(start_date))
            if end_date:
                q = q.filter(TradeCal.cal_date <= _to_date(end_date))
            if is_open is not None:
                q = q.filter(TradeCal.is_open == is_open)
            rows = q.order_by(TradeCal.cal_date).all()

        _CAL_COLS = ["exchange", "cal_date", "is_open", "pretrade_date"]
        return self._orm_to_dataframe(rows, _CAL_COLS)

    # ------------------------------------------------------------------
    # 6. 实用工具方法
    # ------------------------------------------------------------------

    def is_trade_date(self, date: _DateLike, exchange: str = "SSE") -> bool:
        """判断某天是否为交易日。"""
        d = _to_date(date)
        with get_session() as session:
            row = session.query(TradeCal).filter(
                TradeCal.exchange == exchange,
                TradeCal.cal_date == d,
                TradeCal.is_open == 1,
            ).first()
        return row is not None

    def get_latest_date(self, ts_code: Optional[str] = None) -> Optional[datetime.date]:
        """
        获取本地 stock_daily 表的最新交易日期。

        参数:
            ts_code - 指定股票代码（不传则返回全市场最新日期）
        """
        with get_session() as session:
            q = session.query(func.max(StockDaily.trade_date))
            if ts_code:
                q = q.filter(StockDaily.ts_code == ts_code)
            return q.scalar()

    def get_prev_trade_date(
        self, date: _DateLike, n: int = 1, exchange: str = "SSE"
    ) -> Optional[datetime.date]:
        """
        获取给定日期往前第 n 个交易日。

        参数:
            date     - 基准日期
            n        - 往前数几个交易日，默认 1（即上一交易日）
            exchange - 交易所，默认 'SSE'

        返回:
            datetime.date 或 None（如果历史数据不足）
        """
        d = _to_date(date)
        with get_session() as session:
            rows = (
                session.query(TradeCal.cal_date)
                .filter(
                    TradeCal.exchange == exchange,
                    TradeCal.is_open == 1,
                    TradeCal.cal_date < d,
                )
                .order_by(TradeCal.cal_date.desc())
                .limit(n)
                .all()
            )
        if len(rows) < n:
            return None
        return rows[-1].cal_date

    # ------------------------------------------------------------------
    # 7. 指数日线行情
    # ------------------------------------------------------------------

    def get_index_daily(
        self,
        ts_code: Union[str, list[str]],
        start_date: Optional[_DateLike] = None,
        end_date: Optional[_DateLike] = None,
    ) -> pd.DataFrame:
        """
        获取指数日线行情（如沪深300、行业指数等）。

        参数:
            ts_code    - 指数代码，如 '000300.SH' 或列表
            start_date - 起始日期
            end_date   - 截止日期

        返回:
            DataFrame，列: [ts_code, trade_date, open, high, low, close,
                             pre_close, change, pct_chg, vol, amount]
        """
        codes = [ts_code] if isinstance(ts_code, str) else ts_code

        with get_session() as session:
            q = session.query(IndexDaily).filter(IndexDaily.ts_code.in_(codes))
            if start_date:
                q = q.filter(IndexDaily.trade_date >= _to_date(start_date))
            if end_date:
                q = q.filter(IndexDaily.trade_date <= _to_date(end_date))
            q = q.order_by(IndexDaily.ts_code, IndexDaily.trade_date)
            rows = q.all()

        _IDX_COLS = ["ts_code", "trade_date", "open", "high", "low",
                     "close", "pre_close", "change", "pct_chg", "vol", "amount"]
        return self._orm_to_dataframe(rows, _IDX_COLS)

    # ------------------------------------------------------------------
    # 8. 每日基本面指标
    # ------------------------------------------------------------------

    def get_daily_basic(
        self,
        ts_code: Union[str, list[str]],
        start_date: Optional[_DateLike] = None,
        end_date: Optional[_DateLike] = None,
        fields: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        获取每日基本面指标（换手率、PE/PB、市值等）。

        参数:
            ts_code    - 股票代码或列表
            start_date - 起始日期
            end_date   - 截止日期
            fields     - 需要返回的列名子集，None 表示全部

        返回:
            DataFrame，列: [ts_code, trade_date, turnover_rate, pe, pb, total_mv, ...]
        """
        codes = [ts_code] if isinstance(ts_code, str) else ts_code

        with get_session() as session:
            q = session.query(DailyBasic).filter(DailyBasic.ts_code.in_(codes))
            if start_date:
                q = q.filter(DailyBasic.trade_date >= _to_date(start_date))
            if end_date:
                q = q.filter(DailyBasic.trade_date <= _to_date(end_date))
            q = q.order_by(DailyBasic.ts_code, DailyBasic.trade_date)
            rows = q.all()

        _BASIC_COLS = [
            "ts_code", "trade_date",
            "turnover_rate", "turnover_rate_f", "volume_ratio",
            "pe", "pe_ttm", "pb", "ps", "ps_ttm",
            "dv_ratio", "dv_ttm",
            "total_share", "float_share", "free_share",
            "total_mv", "circ_mv",
        ]
        df = self._orm_to_dataframe(rows, _BASIC_COLS)

        if fields and not df.empty:
            df = df[[c for c in fields if c in df.columns]]

        return df

    def get_daily_basic_cross_section(
        self,
        trade_date: _DateLike,
        fields: Optional[list[str]] = None,
    ) -> pd.DataFrame:
        """
        获取某一交易日全市场基本面截面数据。

        应用场景: 全市场估值排名、市值筛选。
        """
        date = _to_date(trade_date)
        with get_session() as session:
            rows = (
                session.query(DailyBasic)
                .filter(DailyBasic.trade_date == date)
                .order_by(DailyBasic.ts_code)
                .all()
            )

        _ALL_COLS = [
            "ts_code", "trade_date",
            "turnover_rate", "turnover_rate_f", "volume_ratio",
            "pe", "pe_ttm", "pb", "ps", "ps_ttm",
            "dv_ratio", "dv_ttm",
            "total_share", "float_share", "free_share",
            "total_mv", "circ_mv",
        ]
        df = self._orm_to_dataframe(rows, _ALL_COLS)

        if fields and not df.empty:
            df = df[[c for c in fields if c in df.columns]]

        return df

    # ------------------------------------------------------------------
    # 10. 股东人数
    # ------------------------------------------------------------------

    def get_holder_number(
        self,
        ts_code: Union[str, list[str]],
        start_date: Optional[_DateLike] = None,
        end_date: Optional[_DateLike] = None,
    ) -> pd.DataFrame:
        """
        获取股东人数数据。

        参数:
            ts_code    - 股票代码或列表
            start_date - 起始日期（按公告日期 ann_date 过滤）
            end_date   - 截止日期

        返回:
            DataFrame，列: [ts_code, ann_date, end_date, holder_num]
        """
        codes = [ts_code] if isinstance(ts_code, str) else ts_code

        with get_session() as session:
            q = session.query(StkHolderNumber).filter(
                StkHolderNumber.ts_code.in_(codes)
            )
            if start_date:
                q = q.filter(StkHolderNumber.ann_date >= _to_date(start_date))
            if end_date:
                q = q.filter(StkHolderNumber.ann_date <= _to_date(end_date))
            q = q.order_by(StkHolderNumber.ts_code, StkHolderNumber.ann_date)
            rows = q.all()

        _HOLDER_COLS = ["ts_code", "ann_date", "end_date", "holder_num"]
        return self._orm_to_dataframe(rows, _HOLDER_COLS)
