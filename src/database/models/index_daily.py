"""
指数日线行情表 ORM 模型

对应 Tushare 接口: index_daily
文档: https://tushare.pro/document/2?doc_id=95

用途:
  - 基准对比（策略 vs 沪深300等）
  - 板块共振（行业指数涨跌幅替代全行业股票平均）

数据量评估:
  ~20 个常用指数 × ~8000 交易日 ≈ 16 万行（极小）

主键策略:
  联合主键 (ts_code, trade_date)
"""

import datetime

from sqlalchemy import Index, Numeric, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IndexDaily(Base):
    __tablename__ = "index_daily"

    # ── 联合主键 ────────────────────────────────────────────────────────────
    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="指数代码，如 000300.SH")
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True, comment="交易日期")

    # ── 行情核心字段 ────────────────────────────────────────────────────────
    open: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="开盘点位")
    high: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="最高点位")
    low: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="最低点位")
    close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="收盘点位")
    pre_close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="昨收点位")

    change: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="涨跌额")
    pct_chg: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, comment="涨跌幅（%）")

    vol: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True, comment="成交量（手）")
    amount: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="成交额（千元）")

    # ── 额外索引 ──────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_index_daily_ts_code", "ts_code"),
        Index("ix_index_daily_trade_date", "trade_date"),
        {"comment": "指数日线行情表"},
    )

    def __repr__(self) -> str:
        return f"<IndexDaily {self.ts_code} {self.trade_date} close={self.close}>"
