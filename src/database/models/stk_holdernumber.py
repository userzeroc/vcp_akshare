"""
股东人数表 ORM 模型

对应 Tushare 接口: stk_holdernumber
文档: https://tushare.pro/document/2?doc_id=103

用途:
  - 筹码集中度分析：股东人数持续下降 → 筹码趋于集中，有利于后续拉升
  - VCP/动量策略增强：结合股东人数变化判断主力建仓/出货
  - 基本面过滤：排除筹码极度分散的标的

数据量评估:
  ~5000 只股票 × ~4 次/年（季报） × 多年 ≈ 数十万行（中等偏小）

主键策略:
  联合主键 (ts_code, ann_date) — 同一股票同一公告日唯一
"""

import datetime

from sqlalchemy import Index, Integer, Numeric, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class StkHolderNumber(Base):
    __tablename__ = "stk_holdernumber"

    # ── 联合主键 ────────────────────────────────────────────────────────────
    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="TS代码，如 000001.SZ")
    ann_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True, comment="公告日期")

    # ── 核心字段 ──────────────────────────────────────────────────────────
    end_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, comment="截止日期（报告期）")
    holder_num: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="股东户数")

    # ── 额外索引 ──────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_stk_holdernumber_ts_code", "ts_code"),
        Index("ix_stk_holdernumber_end_date", "end_date"),
        {"comment": "股东人数表（筹码集中度分析）"},
    )

    def __repr__(self) -> str:
        return f"<StkHolderNumber {self.ts_code} {self.ann_date} holder_num={self.holder_num}>"
