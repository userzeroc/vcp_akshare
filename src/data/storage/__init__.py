"""
data storage 包

职责:
  cleaner.py  — 数据清洗：类型转换、去空、字段重命名
  upsert.py   — 幂等写入：ON CONFLICT DO UPDATE
  writer.py   — 高级封装：将 cleaner + upsert 组合成单次调用的入库函数
"""
