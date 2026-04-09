
import os
import sys
from sqlalchemy import func, distinct

# 确保能找到 src 模块
sys.path.append(os.getcwd())

from src.database.session import get_session
from src.database.models import StockBasic, StockDaily, TradeCal, AdjFactor

def get_stats():
    stats = []
    
    with get_session() as session:
        # StockBasic stats
        total_stocks = session.query(func.count(StockBasic.ts_code)).scalar()
        listed_stocks = session.query(func.count(StockBasic.ts_code)).filter(StockBasic.list_status == 'L').scalar()
        stats.append({
            "table": "stock_basic",
            "description": "股票基本信息",
            "total_count": total_stocks,
            "details": f"上市(L): {listed_stocks}"
        })
        
        # StockDaily stats
        total_daily = session.query(func.count(StockDaily.ts_code)).scalar()
        if total_daily > 0:
            min_date = session.query(func.min(StockDaily.trade_date)).scalar()
            max_date = session.query(func.max(StockDaily.trade_date)).scalar()
            unique_codes = session.query(func.count(distinct(StockDaily.ts_code))).scalar()
            details = f"日期范围: {min_date} ~ {max_date}, 覆盖代码数: {unique_codes}"
        else:
            details = "无数据"
        stats.append({
            "table": "stock_daily",
            "description": "日线行情数据",
            "total_count": total_daily,
            "details": details
        })
        
        # TradeCal stats
        total_cal = session.query(func.count(TradeCal.cal_date)).scalar()
        if total_cal > 0:
            min_cal = session.query(func.min(TradeCal.cal_date)).scalar()
            max_cal = session.query(func.max(TradeCal.cal_date)).scalar()
            open_days = session.query(func.count(TradeCal.cal_date)).filter(TradeCal.is_open == 1).scalar()
            details = f"范围: {min_cal} ~ {max_cal}, 交易日: {open_days}"
        else:
            details = "无数据"
        stats.append({
            "table": "trade_cal",
            "description": "交易日历",
            "total_count": total_cal,
            "details": details
        })
        
        # AdjFactor stats
        total_adj = session.query(func.count(AdjFactor.ts_code)).scalar()
        if total_adj > 0:
            min_adj = session.query(func.min(AdjFactor.trade_date)).scalar()
            max_adj = session.query(func.max(AdjFactor.trade_date)).scalar()
            unique_adj_codes = session.query(func.count(distinct(AdjFactor.ts_code))).scalar()
            details = f"范围: {min_adj} ~ {max_adj}, 覆盖代码数: {unique_adj_codes}"
        else:
            details = "无数据"
        stats.append({
            "table": "adj_factor",
            "description": "复权因子",
            "total_count": total_adj,
            "details": details
        })
        
    return stats

if __name__ == "__main__":
    results = get_stats()
    print("| 数据表 (Table) | 描述 (Description) | 数据量 (Rows) | 统计详情 (Statistics Details) |")
    print("| :--- | :--- | :--- | :--- |")
    for r in results:
        print(f"| {r['table']} | {r['description']} | {r['total_count']:,} | {r['details']} |")
