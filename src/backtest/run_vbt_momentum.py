"""
动量突破策略 VectorBT 回测入口
================================

执行方式::

    # 单股回测（T+1 开盘入场）
    python -m src.backtest.run_vbt_momentum --stock 600089.SH --start 20220101 --end 20231231

    # 参数网格扫描
    python -m src.backtest.run_vbt_momentum --stock 600089.SH --start 20220101 --end 20231231 --grid
"""

import argparse
import logging
import numpy as np
from datetime import datetime

from src.data.reader import StockReader
from src.backtest.vbt.engine import VbtBacktestEngine
from src.config.settings import settings
from src.backtest.vbt.signals import momentum_signals
from src.backtest.vbt.report import print_report, save_equity_curve, save_trades_csv, save_grid_heatmap

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 单次回测
# ---------------------------------------------------------------------------

def run_single(
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000.0,
    ma_long_period: int = 60,
    ma_short_period: int = 20,
    min_pct_chg: float = 5.0,
    vol_multiplier: float = 2.0,
    bias_threshold: float = 0.25,
    use_trailing_stop: bool = True,
    atr_multiplier: float = 2.5,
    output_dir: str = "backtest_results_vbt",
    save_html: bool = True,
    save_csv: bool = True,
):
    print(f"\n{'='*62}")
    print(f"  📊 动量突破策略回测 (VectorBT) — {stock_code}")
    print(f"{'='*62}")

    # 1. 加载数据（预热 1 年）
    start_dt   = datetime.strptime(start_date, "%Y%m%d")
    load_start = start_dt.replace(year=start_dt.year - 1).strftime("%Y%m%d")

    reader = StockReader()
    df     = reader.get_daily_adj(stock_code, load_start, end_date, mode="qfq")

    if df.empty:
        print(f"  ❌ 未获取到 {stock_code} 数据，请检查代码或日期范围。")
        return None

    print(f"  ✅ 数据加载: {len(df)} 条记录 (含预热期)")
    print(f"  回测区间: {start_date} ~ {end_date}")
    print(f"  参数: MA{ma_long_period}/{ma_short_period}, 涨幅>{min_pct_chg}%, 成交量>{vol_multiplier}x")

    # 2. 生成信号
    entries, exits = momentum_signals.generate_signals(
        df,
        ma_long_period=ma_long_period,
        ma_short_period=ma_short_period,
        min_pct_chg=min_pct_chg,
        vol_multiplier=vol_multiplier,
        bias_threshold=bias_threshold,
        use_trailing_stop=use_trailing_stop,
        atr_multiplier=atr_multiplier,
    )
    # T+1 入场价（下一日开盘价）
    entry_price = momentum_signals.calc_entry_price(df)

    n_entries = entries.sum()
    print(f"  📡 信号生成: {n_entries} 个买入信号 (T+1 开盘入场)")

    if n_entries == 0:
        print("  ⚠️  未产生任何买入信号，请调整参数。")
        return None

    # 3. 裁剪到回测区间
    from datetime import datetime as _dt
    start_dt_obj = _dt.strptime(start_date, "%Y%m%d").date()
    mask         = df['trade_date'].apply(lambda x: x.date() if hasattr(x, 'date') else x) >= start_dt_obj
    df_bt        = df[mask].copy().reset_index(drop=True)
    offset       = (~mask).sum()
    ent_bt       = entries.iloc[offset:].reset_index(drop=True)
    exit_bt      = exits.iloc[offset:].reset_index(drop=True)
    entry_price_bt = entry_price.iloc[offset:].reset_index(drop=True)

    # 4. 运行回测
    engine    = VbtBacktestEngine(initial_capital=initial_capital)
    portfolio = engine.run(df_bt, ent_bt, exit_bt, entry_price=entry_price_bt)

    # 5. 输出报告
    print_report(portfolio, stock_code, "动量突破")

    # 6. 保存文件
    if save_html:
        save_equity_curve(portfolio, stock_code, output_dir)
    if save_csv:
        save_trades_csv(portfolio, stock_code, output_dir)

    return portfolio


# ---------------------------------------------------------------------------
# 参数网格扫描
# ---------------------------------------------------------------------------

def run_grid(
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000.0,
    output_dir: str = "backtest_results_vbt",
):
    """
    对 min_pct_chg × vol_multiplier 做网格扫描，夏普比率热力图。
    """
    print(f"\n  🔍 参数网格扫描 — 动量突破 | {stock_code}")

    start_dt   = datetime.strptime(start_date, "%Y%m%d")
    load_start = start_dt.replace(year=start_dt.year - 1).strftime("%Y%m%d")

    reader = StockReader()
    df     = reader.get_daily_adj(stock_code, load_start, end_date, mode="qfq")
    if df.empty:
        print(f"  ❌ 数据加载失败: {stock_code}")
        return

    pct_range = np.arange(3.0, 9.0, 1.0)     # 涨幅 3% ~ 8%
    vol_range = np.arange(1.5, 4.0, 0.5)     # 倍量 1.5 ~ 3.5

    import pandas as pd
    entries_list = []
    exits_list   = []
    param_names  = []

    for pct in pct_range:
        for vol in vol_range:
            ent, ext = momentum_signals.generate_signals(
                df,
                min_pct_chg=round(pct, 1),
                vol_multiplier=round(vol, 1),
            )
            label = f"pct{pct:.1f}-vol{vol:.1f}"
            entries_list.append(ent.rename(label))
            exits_list.append(ext.rename(label))
            param_names.append(label)

    entries_grid = pd.concat(entries_list, axis=1)
    exits_grid   = pd.concat(exits_list,   axis=1)

    engine    = VbtBacktestEngine(initial_capital=initial_capital)
    portfolio = engine.run_grid(df, entries_grid, exits_grid, param_names)

    save_grid_heatmap(
        portfolio,
        param_x="vol_multiplier",
        param_y="min_pct_chg",
        metric="Sharpe Ratio",
        output_dir=output_dir,
    )

    stats = portfolio.stats(agg_func=None)
    if "Sharpe Ratio" in stats.columns:
        best_idx = stats["Sharpe Ratio"].idxmax()
        print(f"\n  🏆 最优参数组合: {best_idx}")
        print(f"     Sharpe Ratio : {stats.loc[best_idx, 'Sharpe Ratio']:.3f}")
        print(f"     Total Return : {stats.loc[best_idx, 'Total Return [%]']:.2f}%")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="动量突破策略 VectorBT 回测")
    parser.add_argument("--stock",      type=str,   default="600089.SH", help="股票代码")
    parser.add_argument("--start",      type=str,   default="20220101",  help="开始日期 YYYYMMDD")
    parser.add_argument("--end",        type=str,   default="20251231",  help="结束日期 YYYYMMDD")
    parser.add_argument("--capital",    type=float, default=1_000_000.0, help="初始资金")
    parser.add_argument("--ma60",       type=int,   default=60,          help="长期均线周期")
    parser.add_argument("--ma20",       type=int,   default=20,          help="短期均线周期")
    parser.add_argument("--min-pct",    type=float, default=5.0,         help="最小涨幅 %")
    parser.add_argument("--vol-mult",   type=float, default=2.0,         help="成交量倍数")
    parser.add_argument("--bias",       type=float, default=0.25,        help="乖离率阈值")
    parser.add_argument("--no-trailing",action="store_true",             help="禁用 ATR 追踪止盈")
    parser.add_argument("--atr-multi",  type=float, default=2.5,         help="ATR 追踪倍数")
    parser.add_argument("--output-dir", type=str,   default=str(settings.paths.backtest_dir), help="输出目录")
    parser.add_argument("--grid",       action="store_true",             help="启用参数网格扫描")
    parser.add_argument("--no-html",    action="store_true",             help="不保存 HTML 权益曲线")
    parser.add_argument("--no-csv",     action="store_true",             help="不保存 CSV 交易明细")
    args = parser.parse_args()

    if args.grid:
        run_grid(
            args.stock, args.start, args.end,
            args.capital, args.output_dir,
        )
    else:
        run_single(
            args.stock, args.start, args.end,
            args.capital,
            ma_long_period=args.ma60,
            ma_short_period=args.ma20,
            min_pct_chg=args.min_pct,
            vol_multiplier=args.vol_mult,
            bias_threshold=args.bias,
            use_trailing_stop=not args.no_trailing,
            atr_multiplier=args.atr_multi,
            output_dir=args.output_dir,
            save_html=not args.no_html,
            save_csv=not args.no_csv,
        )
