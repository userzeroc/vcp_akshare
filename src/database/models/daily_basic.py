"""
每日基本面指标表 ORM 模型

对应 Tushare 接口: daily_basic
文档: https://tushare.pro/document/2?doc_id=32

用途:
  - 估值过滤（PE/PB，避免追高垃圾股）
  - 换手率判断（量能真实性）
  - 市值筛选（排除小市值仙股）

数据量评估:
  ~5000 股 × ~5000 交易日 ≈ 2500 万行（与 stock_daily 同量级）

主键策略:
  联合主键 (ts_code, trade_date) — 与 stock_daily 保持一致，便于 JOIN
"""

import datetime

from sqlalchemy import Index, Numeric, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DailyBasic(Base):
    __tablename__ = "daily_basic"

    # ── 联合主键 ────────────────────────────────────────────────────────────
    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="TS代码，如 000001.SZ")
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True, comment="交易日期")

    # ── 换手率 ──────────────────────────────────────────────────────────────
    turnover_rate: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, comment="换手率（%）")
    turnover_rate_f: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, comment="换手率（自由流通股）")
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, comment="量比")

    # ── 估值指标 ────────────────────────────────────────────────────────────
    pe: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="市盈率（总市值/净利润）")
    pe_ttm: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="市盈率（TTM）")
    pb: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="市净率")
    ps: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="市销率")
    ps_ttm: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="市销率（TTM）")

    # ── 股息率 ──────────────────────────────────────────────────────────────
    dv_ratio: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, comment="股息率（%）")
    dv_ttm: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, comment="股息率（TTM）（%）")

    # ── 股本与市值 ──────────────────────────────────────────────────────────
    total_share: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="总股本（万股）")
    float_share: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="流通股本（万股）")
    free_share: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="自由流通股本（万股）")
    total_mv: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="总市值（万元）")
    circ_mv: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="流通市值（万元）")

    # ── 额外索引 ──────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_daily_basic_ts_code", "ts_code"),
        Index("ix_daily_basic_trade_date", "trade_date"),
        {"comment": "每日基本面指标表（估值/换手率/市值）"},
    )

    def __repr__(self) -> str:
        return f"<DailyBasic {self.ts_code} {self.trade_date} pe={self.pe} mv={self.total_mv}>"
