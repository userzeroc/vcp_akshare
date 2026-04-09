
import os
import sys
import pandas as pd
from datetime import date

# Ensure src module is findable
sys.path.append(os.getcwd())

from src.data.reader.stock_reader import StockReader
from src.strategy.momentum_breakout import MomentumBreakoutStrategy, print_backtest_report

def run_all_momentum_backtests():
    reader = StockReader()
    stocks = [
        ("601899.SH", "紫金矿业"),
        ("002475.SZ", "立讯精密"),
        ("603993.SH", "洛阳钼业")
    ]
    start_date = "20200101"
    
    print("=" * 70)
    print("  ⭐ 能量突破策略 (Momentum Breakout) 多股联动回测 ⭐")
    print("=" * 70)
    
    for ts_code, name in stocks:
        print(f"\n>>> 正在回测: {name} ({ts_code}) ...")
        
        # 获取前复权数据
        df = reader.get_daily_adj(ts_code, start_date=start_date, mode="qfq")
        
        if df.empty:
            print(f"    [!] 错误: 未找到数据，请确认是否已同步。")
            continue
            
        # 初始化策略
        # 使用默认参数: MA60趋势, 涨幅>5%, 成交量>2xMA20
        strategy = MomentumBreakoutStrategy()
        
        # 运行回测
        result = strategy.run(df, initial_capital=1000000.0, debug=False)
        
        # 打印报告
        print_backtest_report(result, stock_code=f"{name} ({ts_code})")

if __name__ == "__main__":
    run_all_momentum_backtests()
