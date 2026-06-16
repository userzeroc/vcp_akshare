"""
幂等 Upsert 引擎

核心: 利用 PostgreSQL 原生 `INSERT ... ON CONFLICT DO UPDATE` 实现幂等写入。
      重复执行同一份数据不会报错，也不会产生重复行。

设计说明:
  - 只依赖 SQLAlchemy Session，不绑定具体 ORM 模型（通用）
  - 每次 upsert 在单个事务内完成（由调用方的 get_session() 控制事务边界）
  - 支持大批量数据：内部按 chunk_size 分批 executemany，避免单条 SQL 过长

参数:
  session          - SQLAlchemy Session 对象（来自 get_session()）
  model            - ORM 模型类（如 StockDaily）
  df               - 已清洗的 DataFrame，列名必须与模型字段一一对应
  conflict_columns - 触发 ON CONFLICT 的列名列表（通常是主键列）
  chunk_size       - 每批写入行数，默认 2000
"""

import math
from typing import Type, Sequence

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database.models.base import Base


def upsert_dataframe(
    session: Session,
    model: Type[Base],
    df: pd.DataFrame,
    conflict_columns: Sequence[str],
    chunk_size: int = 500,
) -> int:
    """
    将 DataFrame 幂等写入到 model 对应的数据库表。

    返回值:
        写入（insert + update）的总行数

    示例::

        from src.database.session import get_session
        from src.database.models import StockDaily
        from src.data.storage.upsert import upsert_dataframe

        with get_session() as session:
            n = upsert_dataframe(session, StockDaily, df, ["ts_code", "trade_date"])
            print(f"upserted {n} rows")
    """
    if df.empty:
        return 0

    # 只保留 ORM 模型上实际存在的列，忽略 DataFrame 中多余的列
    model_cols = {col.key for col in model.__table__.columns}
    df = df[[c for c in df.columns if c in model_cols]].copy()

    # 将 NaN/NaT 彻底转为 None（PostgreSQL 不认识 float NaN 或 Pandas NaT）。
    # 先转 object，避免 float 列在填充 None 时被强制回 NaN。
    df = df.astype(object).where(pd.notna(df), other=None)

    records = df.to_dict(orient="records")
    total = len(records)
    n_chunks = math.ceil(total / chunk_size)

    for i in range(n_chunks):
        chunk = records[i * chunk_size : (i + 1) * chunk_size]

        stmt = pg_insert(model.__table__).values(chunk)

        # 构建 SET clause：除冲突列之外，所有列都做更新
        update_set = {
            col: stmt.excluded[col]
            for col in chunk[0].keys()
            if col not in conflict_columns
        }

        if update_set:
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_=update_set,
            )
        else:
            # 如果除冲突列外没有其他列（理论上不会发生），则跳过冲突行
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)

        session.execute(stmt)

    return total
