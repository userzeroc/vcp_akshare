"""
回测报告输出模块

职责：
  格式化打印回测结果报告。
  从 BaseStrategy.print_report() 中提取为独立函数。
"""

from src.strategy.base import BacktestResult


def print_report(result: BacktestResult, stock_info: str = ""):
    """打印标准回测报告"""
    final_value = result.equity_curve[-1][1] if result.equity_curve else 1000000.0

    print("\n" + "=" * 70)
    print(f"  📊 Strategy Backtest Report: {stock_info}")
    print("=" * 70)

    print(f"\n[ Performance Summary ]")
    print(f"  Final Equity:          {final_value:,.2f}")
    print(f"  Total Return:          {result.total_return:.2f}%")
    print(f"  Annualized Return:     {result.annualized_return:.2f}%")
    print(f"  Max Drawdown:          {result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")

    print(f"\n[ Trading Statistics ]")
    print(f"  Total Trades:          {result.total_trades}")
    print(f"  Winning Trades:        {result.winning_trades} ({result.win_rate:.1f}%)")
    print(f"  Profit/Loss Ratio:     {result.profit_loss_ratio:.2f}")
    print(f"  Avg Win/Loss:          {result.avg_win:,.0f} / {result.avg_loss:,.0f}")

    if result.trades:
        print(f"\n[ Trade Details ]")
        print("-" * 70)
        print(f"{'Entry Date':<12} {'Entry':>8} {'Exit Date':<12} {'Exit':>8} {'PnL%':>8} {'Reason'}")
        print("-" * 70)
        for t in result.trades:
            entry_str = str(t.entry_date)
            exit_str = str(t.exit_date)
            pct_str = f"{t.pnl_pct:+.1f}%"
            print(f"{entry_str:<12} {t.entry_price:>8.2f} {exit_str:<12} {t.exit_price:>8.2f} {pct_str:>8} {t.exit_reason[:20]}")
        print("-" * 70)
    print("=" * 70 + "\n")
