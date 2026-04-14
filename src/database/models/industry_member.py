"""
行业成分股映射表 ORM 模型

对应 Tushare 接口: index_member（申万行业指数成分股），或 ths_member（同花顺概念）
文档: https://tushare.pro/document/2?doc_id=181

用途:
  - 板块共振查询加速（直接关联行业指数，替代逐票遍历）
  - 行业分类分析

数据量评估:
  ~100 个行业 × ~50 平均成分股 ≈ 5000 行（极小，可全量刷新）

主键策略:
  联合主键 (index_code, ts_code)
"""

import datetime
from typing import Optional

from sqlalchemy import Index, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IndustryMember(Base):
    __tablename__ = "industry_member"

    # ── 联合主键 ────────────────────────────────────────────────────────────
    index_code: Mapped[str] = mapped_column(String(20), primary_key=True, comment="行业指数代码")
    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="成分股TS代码")

    # ── 描述字段 ────────────────────────────────────────────────────────────
    index_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="行业指数名称")
    con_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="成分股名称")

    # ── 时间字段 ────────────────────────────────────────────────────────────
    in_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, comment="纳入日期")
    out_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True, comment="剔除日期")
    is_new: Mapped[str | None] = mapped_column(String(1), nullable=True, comment="是否最新 Y/N")

    # ── 额外索引 ──────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_industry_member_index_code", "index_code"),
        Index("ix_industry_member_ts_code", "ts_code"),
        {"comment": "行业成分股映射表"},
    )

    def __repr__(self) -> str:
        return f"<IndustryMember {self.index_code} → {self.ts_code}>"
