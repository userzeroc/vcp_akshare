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

from src.config.settings import settings
from src.data.reader import StockReader
from src.strategy.factory import StrategyFactory
from src.strategy.base import BacktestResult
from src.backtest.engine import BacktestEngine
from src.backtest.reports import print_report


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
    
    # 通过工厂创建策略实例（自动加载个股配置参数）
    strategy = StrategyFactory.create(
        "Momentum",
        ts_code=stock_code,
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
    engine = BacktestEngine(initial_capital=initial_capital, debug=True)
    result = engine.run(strategy, df, earnings_dates=earnings_dates)
    
    return result


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
    
    parser.add_argument('--output-dir', type=str, default=str(settings.paths.backtest_dir), help='输出目录')
    
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
    print_report(result, args.stock)
    
    # 导出交易明细
    csv_path = os.path.join(args.output_dir, f"trades_detail_{args.stock.replace('.', '_')}.csv")
    export_trades_to_csv(result, csv_path)
    
    print("\n✨ 回测完成!")


if __name__ == "__main__":
    main()
