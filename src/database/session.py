"""
数据库连接与 Session 工厂模块

职责:
- 创建全局 SQLAlchemy Engine（带连接池）
- 提供 get_session() 上下文管理器，自动处理 commit / rollback / close
- 提供 get_engine() 供 Alembic、to_sql 等场景直接使用 Engine
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from src.config import settings

# ---------------------------------------------------------------------------
# Engine（全局单例）
# ---------------------------------------------------------------------------
# pool_size=5        : 常驻连接数，适合单进程量化脚本
# max_overflow=10    : 超出 pool_size 时最多额外建立的临时连接数
# pool_pre_ping=True : 每次从连接池取连接前发送 SELECT 1，自动踢掉断连
# echo=False         : 生产环境关闭 SQL 日志；调试时可改为 True
# ---------------------------------------------------------------------------
_engine: Engine = create_engine(
    settings.db.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

# Session 工厂（不要在模块级直接 new Session，应通过 get_session() 获取）
_SessionLocal = sessionmaker(
    bind=_engine,
    autoflush=False,   # 手动控制 flush，避免意外提前写库
    autocommit=False,
    expire_on_commit=False,  # commit 后对象属性不失效，避免再次访问触发 lazy load
)


def get_engine() -> Engine:
    """
    返回全局 Engine 实例。
    用途：
      - pandas.DataFrame.to_sql(con=get_engine(), ...)
      - Alembic env.py 中 context.configure(connection=get_engine().connect())
    """
    return _engine


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    提供事务性 Session 上下文管理器。

    用法::

        from src.database.session import get_session

        with get_session() as session:
            session.add(obj)
            # 正常退出时自动 commit
            # 异常时自动 rollback

    注意:
        不要跨 with 块共享同一个 session 对象。
        长事务（如批量 upsert 几万行）请在同一个 with 块内完成。
    """
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
