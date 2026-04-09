"""
Alembic 环境配置

关键配置:
  1. target_metadata = Base.metadata
     → 导入所有 ORM 模型后，Alembic autogenerate 可自动检测表结构变更

  2. URL 从 src.config.settings 动态读取
     → 只需维护 .env 文件，alembic.ini 中无需硬编码连接串

  3. compare_type=True
     → autogenerate 时同时检测字段类型变化（如 VARCHAR 长度改变）
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── 接入我们的 ORM Base 与配置中心 ──────────────────────────────────────────
from src.config import settings

# 导入所有模型，使 Base.metadata 能发现全部表
# （models/__init__.py 已统一 re-export，这里一行搞定）
from src.database.models import Base  # noqa: F401

# ── Alembic 标准配置 ─────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 告诉 Alembic 用我们的 metadata 做 autogenerate
target_metadata = Base.metadata

# 动态注入数据库 URL（覆盖 alembic.ini 中的空值）
config.set_main_option("sqlalchemy.url", settings.db.database_url)

# ---------------------------------------------------------------------------
# 仅管理属于我们 ORM 模型的表，忽略同一数据库中的其他外部表
# （如 n8n、airflow 等共存在同一 PostgreSQL 实例中的表）
# ---------------------------------------------------------------------------
_managed_tables = set(Base.metadata.tables.keys())


def include_object(object, name, type_, reflected, compare_to):
    """返回 True 表示 Alembic 需要管理此对象，False 表示忽略。"""
    if type_ == "table":
        return name in _managed_tables
    return True  # index / column / constraint 跟随所属表的决定


# ---------------------------------------------------------------------------
# offline 模式（生成 SQL 脚本，不需要真实数据库连接）
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,              # 检测字段类型变更
        include_object=include_object,  # 过滤外部表
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# online 模式（直连数据库执行迁移，推荐日常使用）
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,        # 迁移时不需要连接池
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,          # 检测字段类型变更
            include_object=include_object,  # 过滤外部表
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
