"""
交易日历表 ORM 模型

对应 Tushare 接口: trade_cal
文档: https://tushare.pro/document/2?doc_id=26

字段说明:
  exchange     - 交易所（SSE上交所 / SZSE深交所）
  cal_date     - 日历日期
  is_open      - 是否交易日：1=是，0=否
  pretrade_date- 上一个交易日（仅交易日有值）
"""

import datetime

from sqlalchemy import SmallInteger, String, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TradeCal(Base):
    __tablename__ = "trade_cal"

    # 联合主键：交易所 + 日期
    exchange: Mapped[str] = mapped_column(String(10), primary_key=True, comment="交易所代码，如 SSE / SZSE")
    cal_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True, comment="日历日期")

    is_open: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="是否交易日：1=是 0=否")
    pretrade_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, comment="上一个交易日")

    def __repr__(self) -> str:
        return f"<TradeCal {self.exchange} {self.cal_date} open={self.is_open}>"
