"""
data reader 包

使用时只需::

    from src.data.reader import StockReader

    reader = StockReader()
    df = reader.get_daily("000001.SZ", "20230101", "20240101")
"""

from .stock_reader import StockReader

__all__ = ["StockReader"]
