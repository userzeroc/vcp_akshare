"""
VCP 策略回测运行器 (VCP Strategy Backtest Runner)
==============================================

运行 A 股本地化 VCP 策略并生成报告。
"""

import os
import argparse
import pandas as pd
from typing import Optional
from datetime import datetime
from src.data.reader import StockReader
from src.strategy.factory import StrategyFactory
from src.backtest.engine import BacktestEngine
from src.backtest.reports import print_report

def run_backtest(
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 1000000.0,
    last_t_depth: Optional[float] = None,
    vol_exhaust_ratio: Optional[float] = None,
):
    print(f"\n============================================================")
    print(f"📊 A股本地化 VCP 策略回测 - {stock_code}")
    print(f"============================================================")
    
    # 1. 加载数据 (提前1年加载以确保均线数据充足)
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    load_start = (start_dt.replace(year=start_dt.year - 1)).strftime('%Y%m%d')
    
    reader = StockReader()
    df = reader.get_daily_adj(stock_code, load_start, end_date, mode='qfq')
    
    if df.empty:
        print(f"❌ 未获取到 {stock_code} 的数据，请检查代码或日期范围。")
        return
    
    print(f"✅ 数据加载完成: {len(df)} 条记录 (含预热期)")
    print(f"   回测区间: {start_date} ~ {end_date}")
    
    # 2. 通过工厂初始化策略（自动加载个股配置参数）
    # 2. 通过工厂初始化策略（自动加载个股配置参数）
    # 仅在非默认情况下覆盖配置
    strat_kwargs = {"time_stop_days": 3}
    if last_t_depth is not None: strat_kwargs["last_t_depth"] = last_t_depth
    if vol_exhaust_ratio is not None: strat_kwargs["vol_exhaust_ratio"] = vol_exhaust_ratio
    
    strategy = StrategyFactory.create(
        "VCP",
        ts_code=stock_code,
        **strat_kwargs
    )

    # 注入数据交互依赖 (Factor 3: Sector Resonance)
    strategy._reader = reader
    strategy._ts_code = stock_code
    strategy._industry = reader.get_industry_info(stock_code)
    
    print("\n📈 VCP 策略参数 (已针对A股校准):")
    print(f"   Stage 2 均线: MA50, MA120, MA150, MA200")
    print(f"   最后收缩阈值: {strategy.last_t_depth*100:.1f}%")
    print(f"   地量倍数: {strategy.vol_exhaust_ratio}")
    print(f"   时间止损: {strategy.time_stop_days}日")
    
    print("\n⏳ 回测运行中...")
    engine = BacktestEngine(initial_capital=initial_capital, debug=True)
    result = engine.run(strategy, df)
    
    # 3. 打印分析报告
    print_report(result, stock_code)
    
    return result, df

def save_vcp_results(result, df, stock_code, output_dir='backtest_results_vcp'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # 保存交易明细
    trades_data = []
    for t in result.trades:
        trades_data.append({
            'entry_date': t.entry_date,
            'entry_price': t.entry_price,
            'exit_date': t.exit_date,
            'exit_price': t.exit_price,
            'pnl': t.pnl,
            'pnl_pct': t.pnl_pct,
            'reason': t.exit_reason
        })
    
    trades_df = pd.DataFrame(trades_data)
    trades_path = os.path.join(output_dir, f"trades_vcp_{stock_code}.csv")
    trades_df.to_csv(trades_path, index=False)
    print(f"✅ 交易明细已导出至: {trades_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A股 VCP 策略回测')
    parser.add_argument('--stock', type=str, default='600089.SH', help='股票代码')
    parser.add_argument('--start', type=str, default='20200101', help='开始日期')
    parser.add_argument('--end', type=str, default='20250401', help='结束日期')
    parser.add_argument('--capital', type=float, default=1000000.0, help='初始资金')
    parser.add_argument('--depth', type=float, default=None, help='波幅收缩阈值')
    parser.add_argument('--vol-ratio', type=float, default=None, help='地量倍数')
    parser.add_argument('--output-dir', type=str, default='backtest_results_vcp', help='输出目录')
    
    args = parser.parse_args()
    
    result, df = run_backtest(
        args.stock,
        args.start,
        args.end,
        args.capital,
        args.depth,
        args.vol_ratio
    )
    
    if result:
        save_vcp_results(result, df, args.stock, args.output_dir)
        print("\n✨ VCP 回测完成!")
