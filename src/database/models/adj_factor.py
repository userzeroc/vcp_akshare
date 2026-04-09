"""
复权因子表 ORM 模型

对应 Tushare 接口: adj_factor
文档: https://tushare.pro/document/2?doc_id=28

用途:
  - adj_factor 配合日线行情计算复权价格
  - 前复权: close × (adj_factor / 当日adj_factor)
  - 后复权: close × adj_factor

主键:
  (ts_code, trade_date) — 与 stock_daily 保持一致，便于 JOIN
"""

import datetime

from sqlalchemy import Index, Numeric, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AdjFactor(Base):
    __tablename__ = "adj_factor"

    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="TS代码，如 000001.SZ")
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True, comment="交易日期")

    # 复权因子，精度需足够高，历史累积会产生较大数值
    adj_factor: Mapped[float | None] = mapped_column(
        Numeric(20, 6), nullable=True, comment="复权因子（后复权基准）"
    )

    __table_args__ = (
        Index("ix_adj_factor_ts_code", "ts_code"),
        Index("ix_adj_factor_trade_date", "trade_date"),
        {"comment": "复权因子表"},
    )

    def __repr__(self) -> str:
        return f"<AdjFactor {self.ts_code} {self.trade_date} factor={self.adj_factor}>"
