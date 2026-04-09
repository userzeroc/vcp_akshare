"""
股票基本信息表 ORM 模型

对应 Tushare 接口: stock_basic
文档: https://tushare.pro/document/2?doc_id=25

字段说明:
  ts_code      - TS代码（主键），格式如 000001.SZ
  symbol       - 股票代码（不含交易所后缀），如 000001
  name         - 股票名称
  area         - 地域（省市）
  industry     - 所属行业（申万一级）
  market       - 市场类型：主板/创业板/科创板/北交所
  exchange     - 交易所：SSE / SZSE / BSE
  curr_type    - 交易货币
  list_status  - 上市状态：L=上市 D=退市 P=暂停
  list_date    - 上市日期
  delist_date  - 退市日期（退市股票才有值）
  is_hs        - 是否沪深港通标的：N=否 H=沪股通 S=深股通
  updated_at   - 本地记录最后更新时间（由程序写入，非 Tushare 字段）
"""

import datetime

from sqlalchemy import String, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="TS代码，如 000001.SZ")
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, comment="股票代码，如 000001")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="股票名称")

    area: Mapped[str | None] = mapped_column(String(30), nullable=True, comment="地域")
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="所属行业")
    market: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="市场类型：主板/创业板/科创板/北交所")
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="交易所：SSE/SZSE/BSE")
    curr_type: Mapped[str | None] = mapped_column(String(5), nullable=True, comment="交易货币")

    list_status: Mapped[str | None] = mapped_column(String(1), nullable=True, comment="上市状态：L=上市 D=退市 P=暂停")
    list_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, comment="上市日期")
    delist_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, comment="退市日期")
    is_hs: Mapped[str | None] = mapped_column(String(1), nullable=True, comment="沪深港通：N=否 H=沪股通 S=深股通")

    # 本地维护字段：记录最后一次 upsert 时间，便于排查数据新鲜度
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="本地最后更新时间",
    )

    def __repr__(self) -> str:
        return f"<StockBasic {self.ts_code} {self.name} [{self.list_status}]>"
