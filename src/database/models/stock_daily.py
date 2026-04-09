"""
日线行情表 ORM 模型

对应 Tushare 接口: daily（未复权日线）
文档: https://tushare.pro/document/2?doc_id=27

数据量评估（120分账号，全市场）:
  ~5000 只股票 × ~5000 个交易日 ≈ 2500 万行
  → 当前阶段无需分区；行数超过 1000 万后可按年做 RANGE 分区。

主键策略:
  联合主键 (ts_code, trade_date) — 天然支持幂等 upsert：
    INSERT ... ON CONFLICT (ts_code, trade_date) DO UPDATE SET ...

索引策略:
  - 主键联合索引已覆盖 "按股票+日期" 的精确查询
  - 额外建 trade_date 单列索引，加速 "某日全市场" 截面查询
  - 额外建 ts_code 单列索引，加速 "单只股票全历史" 时间序列查询
  （两个额外索引在 __table_args__ 中定义，见下方）

字段类型选择:
  价格/金额使用 NUMERIC 而非 FLOAT，避免浮点精度问题。
  vol / amount 用较大精度，因为成交量/成交额数值较大。
"""

import datetime

from sqlalchemy import Index, Numeric, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class StockDaily(Base):
    __tablename__ = "stock_daily"

    # ── 联合主键 ────────────────────────────────────────────────────────────
    ts_code: Mapped[str] = mapped_column(String(12), primary_key=True, comment="TS代码，如 000001.SZ")
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True, comment="交易日期")

    # ── 行情核心字段 ────────────────────────────────────────────────────────
    open: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="开盘价（元）")
    high: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="最高价（元）")
    low: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="最低价（元）")
    close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="收盘价（元）")
    pre_close: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="昨收价（元）")

    change: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True, comment="涨跌额（元）")
    pct_chg: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True, comment="涨跌幅（%），非复权")

    vol: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True, comment="成交量（手）")
    amount: Mapped[float | None] = mapped_column(Numeric(20, 4), nullable=True, comment="成交额（千元）")

    # ── 额外索引（非主键）──────────────────────────────────────────────────
    __table_args__ = (
        # 单只股票 → 全历史时间序列（如回测、策略信号计算）
        Index("ix_stock_daily_ts_code", "ts_code"),
        # 某日 → 全市场截面（如选股、排名）
        Index("ix_stock_daily_trade_date", "trade_date"),
        {"comment": "日线行情表（未复权）"},
    )

    def __repr__(self) -> str:
        return f"<StockDaily {self.ts_code} {self.trade_date} close={self.close}>"
