"""
ORM 声明基类

所有 ORM 模型继承此 Base，Alembic 通过 Base.metadata 自动发现所有表。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
