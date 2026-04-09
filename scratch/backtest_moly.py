
import os
import sys
import pandas as pd
from datetime import date

# Ensure src module is findable
sys.path.append(os.getcwd())

from src.data.reader.stock_reader import StockReader
from src.strategy.vcp_strategy import VCPStrategy

def run_moly_backtest():
    reader = StockReader()
    ts_code = "603993.SH"
    start_date = "20200101"
    
    print(f"正在读取 {ts_code} (洛阳钼业) 的复权数据...")
    # 获取前复权数据
    df = reader.get_daily_adj(ts_code, start_date=start_date, mode="qfq")
    
    if df.empty:
        print(f"错误: 未找到 {ts_code} 的数据，请先同步。")
        return

    print(f"数据读取成功，共 {len(df)} 行记录。")
    
    # 初始化 VCP 策略 (目前已还原为严谨版)
    strategy = VCPStrategy()
    
    print("开始运行 VCP 策略回测...")
    result = strategy.run(df, initial_capital=1000000.0, debug=True)
    
    # 打印简要报告
    print("\n" + "=" * 70)
    print(f"  VCP Strategy Backtest Report: 洛阳钼业 ({ts_code})")
    print("=" * 70)
    
    print(f"\n[ 性能统计 ]")
    print(f"  总收益率:          {result.total_return:.2f}%")
    print(f"  年化收益率:        {result.annualized_return:.2f}%")
    print(f"  最大回撤:          {result.max_drawdown_pct:.2f}%")
    
    print(f"\n[ 交易统计 ]")
    print(f"  成交笔数:          {result.total_trades}")
    print(f"  胜率:              {result.win_rate:.1f}%")
    print(f"  盈亏比:            {result.profit_loss_ratio:.2f}")
    print(f"  平均盈利:          {result.avg_win:,.2f}")
    print(f"  平均亏损:          {result.avg_loss:,.2f}")
    
    if result.trades:
        print(f"\n[ 交易明细 ]")
        print("-" * 70)
        print(f"{'买入日期':<12} {'买入价':>8} {'卖出日期':<12} {'卖出价':>8} {'盈亏%':>8} {'退出原因'}")
        print("-" * 70)
        for t in result.trades:
            entry_str = t.entry_date.strftime('%Y-%m-%d') if hasattr(t.entry_date, 'strftime') else str(t.entry_date)
            exit_str = t.exit_date.strftime('%Y-%m-%d') if t.exit_date and hasattr(t.exit_date, 'strftime') else str(t.exit_date)
            pct_str = f"{t.pnl_pct:+.1f}%"
            reason = t.exit_reason[:20] if t.exit_reason else ""
            print(f"{entry_str:<12} {t.entry_price:>8.2f} {exit_str:<12} {t.exit_price:>8.2f} {pct_str:>8} {reason}")
        print("-" * 70)
    else:
        print("\n[!] 无成交记录。可能是形态未触发或趋势过滤未通过。")
    
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_moly_backtest()
