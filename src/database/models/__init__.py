"""
models 包统一导出

Alembic 的 env.py 只需 `from src.database.models import Base`
即可自动发现所有在此导入的模型，无需手动逐一注册。
"""

from .base import Base
from .trade_cal import TradeCal
from .stock_basic import StockBasic
from .stock_daily import StockDaily
from .adj_factor import AdjFactor
from .index_daily import IndexDaily
from .daily_basic import DailyBasic
from .industry_member import IndustryMember
from .stk_holdernumber import StkHolderNumber

__all__ = [
    "Base",
    "TradeCal",
    "StockBasic",
    "StockDaily",
    "AdjFactor",
    "IndexDaily",
    "DailyBasic",
    "IndustryMember",
    "StkHolderNumber",
]
