"""
动量突破策略回测运行器
======================

针对特变电工(600089.SH)的带大级别过滤的动量突破策略回测

运行方式:
    python -m src.backtest.run_momentum_breakout
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.data.reader import StockReader
from src.strategy.momentum_breakout import (
    MomentumBreakoutStrategy,
    print_backtest_report,
    BacktestResult,
)


def load_stock_data(
    stock_code: str,
    start_date: str = "20200101",
    end_date: str = "20260101",
) -> pd.DataFrame:
    """加载股票数据"""
    reader = StockReader()
    df = reader.get_daily_adj(stock_code, start_date, end_date, mode="qfq")
    
    if df.empty:
        raise ValueError(f"无法加载 {stock_code} 的数据")
    
    # 确保必要的列存在
    required_cols = ['trade_date', 'open', 'high', 'low', 'close', 'vol', 'pct_chg']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"缺少必要列: {col}")
    
    # 转换日期格式
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').reset_index(drop=True)
    
    print(f"✅ 数据加载完成: {len(df)} 条记录")
    print(f"   时间范围: {df['trade_date'].min().strftime('%Y-%m-%d')} ~ {df['trade_date'].max().strftime('%Y-%m-%d')}")
    
    return df


def run_backtest(
    df: pd.DataFrame,
    stock_code: str,
    # 策略参数
    ma_long_period: int = 60,
    ma_short_period: int = 20,
    min_pct_chg: float = 5.0,
    vol_multiplier: float = 2.0,
    vol_ma_period: int = 20,
    hard_stop_loss: float = -8.0,
    position_size: float = 1.0,
    # 进阶参数
    use_atr_filter: bool = False,
    atr_period: int = 20,
    atr_threshold_ratio: float = 0.5,
    # 财报规避
    avoid_earnings: bool = False,
    earnings_dates: list = None,
    # 优化参数 (v2.0)
    bias_threshold: float = 0.25,
    use_trailing_stop: bool = True,
    atr_multiplier: float = 2.5,
    # 回测参数
    initial_capital: float = 1000000.0,
) -> BacktestResult:
    """运行回测"""
    
    # 创建策略实例
    strategy = MomentumBreakoutStrategy(
        ma_long_period=ma_long_period,
        ma_short_period=ma_short_period,
        min_pct_chg=min_pct_chg,
        vol_multiplier=vol_multiplier,
        vol_ma_period=vol_ma_period,
        hard_stop_loss=hard_stop_loss,
        position_size=position_size,
        use_atr_filter=use_atr_filter,
        atr_period=atr_period,
        atr_threshold_ratio=atr_threshold_ratio,
        avoid_earnings=avoid_earnings,
        earnings_lead_days=3,
        bias_threshold=bias_threshold,
        use_trailing_stop=use_trailing_stop,
        atr_multiplier=atr_multiplier
    )
    
    print("\n📈 策略参数:")
    print(f"   长期均线周期: {ma_long_period}")
    print(f"   短期均线周期: {ma_short_period}")
    print(f"   最小涨幅要求: {min_pct_chg}%")
    print(f"   成交量倍数: {vol_multiplier}x")
    print(f"   成交量均线周期: {vol_ma_period}")
    print(f"   硬止损幅度: {hard_stop_loss}%")
    print(f"   仓位比例: {position_size*100:.0f}%")
    if use_atr_filter:
        print(f"   ATR横盘过滤: 启用 (周期={atr_period}, 阈值={atr_threshold_ratio})")
    if avoid_earnings:
        print(f"   财报规避: 启用")
    
    # v2.0 参数打印
    print(f"   [v2.0] 乖离率阈值: {bias_threshold}")
    print(f"   [v2.0] ATR追踪止盈: {'启用' if use_trailing_stop else '禁用'} (倍数={atr_multiplier})")
    
    print("\n⏳ 回测运行中...")
    result = strategy.run(df, initial_capital, earnings_dates)
    
    return result


def plot_equity_curve(result: BacktestResult, stock_code: str, save_path: str = None):
    """绘制权益曲线"""
    if not result.equity_curve:
        print("⚠️ 没有权益曲线数据可绘制")
        return
    
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # 提取数据
    dates = [d for d, _ in result.equity_curve]
    values = [v for _, v in result.equity_curve]
    
    # 图1: 权益曲线
    ax1 = axes[0]
    ax1.plot(dates, values, 'b-', linewidth=1.5, label='权益曲线')
    ax1.axhline(y=values[0], color='gray', linestyle='--', alpha=0.7, label='初始资金')
    ax1.fill_between(dates, values[0], values, alpha=0.3, color='blue')
    
    # 标记买卖点
    for trade in result.trades:
        if trade.exit_date:
            exit_idx = dates.index(trade.exit_date) if trade.exit_date in dates else -1
            if exit_idx >= 0:
                color = 'green' if trade.pnl > 0 else 'red'
                ax1.axvline(x=trade.exit_date, color=color, alpha=0.3, linewidth=0.5)
    
    ax1.set_ylabel('账户权益 (¥)', fontsize=12)
    ax1.set_title(f'动量突破策略 - {stock_code} 权益曲线', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 添加收益信息
    textstr = f'总收益: {result.total_return:.2f}%\n年化: {result.annualized_return:.2f}%\n最大回撤: {result.max_drawdown_pct:.2f}%\n胜率: {result.win_rate:.1f}%\n盈亏比: {result.profit_loss_ratio:.2f}'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=10,
             verticalalignment='top', bbox=props)
    
    # 图2: 回撤曲线
    ax2 = axes[1]
    peak = values[0]
    drawdowns = []
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100
        drawdowns.append(dd)
    
    ax2.fill_between(dates, 0, drawdowns, alpha=0.5, color='red')
    ax2.plot(dates, drawdowns, 'r-', linewidth=1)
    ax2.set_ylabel('回撤 (%)', fontsize=12)
    ax2.set_xlabel('日期', fontsize=12)
    ax2.set_title('回撤曲线', fontsize=12)
    ax2.grid(True, alpha=0.3)
    
    # 设置日期格式
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✅ 图表已保存至: {save_path}")
    
    plt.close()


def plot_trades_on_price(df: pd.DataFrame, result: BacktestResult, stock_code: str, save_path: str = None):
    """绘制价格图表并标记交易"""
    if not result.equity_curve:
        return
    
    # 计算均线指标用于绘图
    df = df.copy()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # 绘制价格
    ax.plot(df['trade_date'], df['close'], 'b-', linewidth=1, alpha=0.7, label='Close')
    
    # 绘制均线
    ax.plot(df['trade_date'], df['ma60'], 'orange', linewidth=1, alpha=0.8, label='MA60')
    ax.plot(df['trade_date'], df['ma20'], 'purple', linewidth=1, alpha=0.8, label='MA20')
    
    # 标记买入点
    buy_signals = [s for s in result.signals if s.signal_type == 'buy']
    for sig in buy_signals:
        ax.scatter(sig.date, sig.price, marker='^', color='green', s=150, zorder=5, label='买入' if sig == buy_signals[0] else '')
    
    # 标记卖出点
    sell_signals = [s for s in result.signals if s.signal_type == 'sell']
    for sig in sell_signals:
        ax.scatter(sig.date, sig.price, marker='v', color='red', s=150, zorder=5, label='卖出' if sig == sell_signals[0] else '')
    
    ax.set_xlabel('日期', fontsize=12)
    ax.set_ylabel('价格 (¥)', fontsize=12)
    ax.set_title(f'动量突破策略 - {stock_code} 交易标记', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # 设置日期格式
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✅ 交易图表已保存至: {save_path}")
    
    plt.close()


def export_trades_to_csv(result: BacktestResult, output_path: str):
    """导出交易明细到CSV"""
    if not result.trades:
        print("⚠️ 没有交易记录可导出")
        return
    
    data = []
    for i, trade in enumerate(result.trades, 1):
        holding_days = (trade.exit_date - trade.entry_date).days if trade.exit_date and trade.exit_date else 0
        data.append({
            '序号': i,
            '买入日期': trade.entry_date.strftime('%Y-%m-%d') if hasattr(trade.entry_date, 'strftime') else str(trade.entry_date),
            '买入价': trade.entry_price,
            '卖出日期': trade.exit_date.strftime('%Y-%m-%d') if trade.exit_date and hasattr(trade.exit_date, 'strftime') else '',
            '卖出价': trade.exit_price if trade.exit_price else '',
            '持仓天数': holding_days,
            '盈亏金额': trade.pnl,
            '盈亏比例(%)': trade.pnl_pct,
            '出场原因': trade.exit_reason,
        })
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"✅ 交易明细已导出至: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='动量突破策略回测')
    parser.add_argument('--stock', type=str, default='600089.SH', help='股票代码')
    parser.add_argument('--start', type=str, default='20200101', help='开始日期')
    parser.add_argument('--end', type=str, default='20260101', help='结束日期')
    parser.add_argument('--capital', type=float, default=1000000.0, help='初始资金')
    parser.add_argument('--ma60', type=int, default=60, help='长期均线周期')
    parser.add_argument('--ma20', type=int, default=20, help='短期均线周期')
    parser.add_argument('--min-pct', type=float, default=5.0, help='最小涨幅要求(%)')
    parser.add_argument('--vol-mult', type=float, default=2.0, help='成交量倍数')
    parser.add_argument('--stop-loss', type=float, default=8.0, help='止损幅度(%)')
    parser.add_argument('--position', type=float, default=0.5, help='仓位比例 (0.0-1.0)')
    parser.add_argument('--atr', action='store_true', help='启用ATR横盘过滤')
    parser.add_argument('--no-earnings', action='store_true', help='禁用财报规避')
    
    # v2.0 参数
    parser.add_argument('--bias', type=float, default=0.25, help='乖离率阈值')
    parser.add_argument('--no-trailing', action='store_true', help='禁用ATR追踪止盈')
    parser.add_argument('--atr-multi', type=float, default=2.5, help='ATR追踪止盈倍数')
    
    parser.add_argument('--output-dir', type=str, default='backtest_results', help='输出目录')
    
    args = parser.parse_args()
    
    # 创建输出目录
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 加载数据
    print("=" * 60)
    print(f"📊 动量突破策略回测 - {args.stock}")
    print("=" * 60)
    
    df = load_stock_data(args.stock, args.start, args.end)
    
    # 运行回测
    result = run_backtest(
        df,
        stock_code=args.stock,
        ma_long_period=args.ma60,
        ma_short_period=args.ma20,
        min_pct_chg=args.min_pct,
        vol_multiplier=args.vol_mult,
        hard_stop_loss=-args.stop_loss,
        position_size=args.position,
        use_atr_filter=args.atr,
        avoid_earnings=not args.no_earnings,
        bias_threshold=args.bias,
        use_trailing_stop=not args.no_trailing,
        atr_multiplier=args.atr_multi,
        initial_capital=args.capital,
    )
    
    # 打印报告
    print_backtest_report(result, args.stock)
    
    # 生成图表
    print("\n📈 生成可视化图表...")
    equity_path = os.path.join(args.output_dir, f"equity_curve_{args.stock.replace('.', '_')}.png")
    trades_path = os.path.join(args.output_dir, f"trades_{args.stock.replace('.', '_')}.png")
    
    plot_equity_curve(result, args.stock, equity_path)
    plot_trades_on_price(df, result, args.stock, trades_path)
    
    # 导出交易明细
    csv_path = os.path.join(args.output_dir, f"trades_detail_{args.stock.replace('.', '_')}.csv")
    export_trades_to_csv(result, csv_path)
    
    print("\n✨ 回测完成!")


if __name__ == "__main__":
    main()
