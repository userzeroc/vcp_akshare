"""
VCP 策略 VectorBT 回测入口
============================

执行方式::

    # 单股回测
    python -m src.backtest.run_vbt_vcp --stock 600089.SH --start 20220101 --end 20231231

    # 参数网格扫描（策略定制完成后使用）
    python -m src.backtest.run_vbt_vcp --stock 600089.SH --start 20220101 --end 20231231 --grid
"""

import argparse
import logging
import os
import numpy as np
from datetime import datetime

from src.data.reader import StockReader
from src.backtest_vbt.engine import VbtBacktestEngine
from src.backtest_vbt.signals import vcp_signals
from src.backtest_vbt.report import print_report, save_equity_curve, save_trades_csv, save_grid_heatmap

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 单次回测
# ---------------------------------------------------------------------------

def run_single(
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 1_000_000.0,
    last_t_depth: float = 0.08,
    vol_exhaust_ratio: float = 0.40,
    output_dir: str = "backtest_results_vbt",
    save_html: bool = True,
    save_csv: bool = True,
):
    print(f"\n{'='*62}")
    print(f"  📊 VCP 策略回测 (VectorBT) — {stock_code}")
    print(f"{'='*62}")

    # 1. 加载数据（预热 1 年）
    start_dt   = datetime.strptime(start_date, "%Y%m%d")
    load_start = start_dt.replace(year=start_dt.year - 1).strftime("%Y%m%d")

    reader = StockReader()
    df     = reader.get_daily_adj(stock_code, load_start, end_date, mode="qfq")

    if df.empty:
        print(f"  ❌ 未获取到 {stock_code} 的数据，请检查代码或日期范围。")
        return None

    print(f"  ✅ 数据加载: {len(df)} 条记录 (含预热期)")
    print(f"  回测区间: {start_date} ~ {end_date}")
    print(f"  参数: last_t_depth={last_t_depth}, vol_exhaust_ratio={vol_exhaust_ratio}")

    # 2. 生成信号
    entries, exits = vcp_signals.generate_signals(
        df,
        last_t_depth=last_t_depth,
        vol_exhaust_ratio=vol_exhaust_ratio,
    )
    n_entries = entries.sum()
    print(f"  📡 信号生成: {n_entries} 个买入信号")

    if n_entries == 0:
        print("  ⚠️  未产生任何买入信号，请调整参数。")
        return None

    # 3. 裁剪到回测区间
    from datetime import datetime as _dt
    start_dt_obj = _dt.strptime(start_date, "%Y%m%d").date()
    mask    = df['trade_date'].apply(lambda x: x.date() if hasattr(x, 'date') else x) >= start_dt_obj
    df_bt   = df[mask].copy().reset_index(drop=True)
    offset  = (~mask).sum()
    ent_bt  = entries.iloc[offset:].reset_index(drop=True)
    exit_bt = exits.iloc[offset:].reset_index(drop=True)

    # 4. 运行回测
    engine    = VbtBacktestEngine(initial_capital=initial_capital)
    portfolio = engine.run(df_bt, ent_bt, exit_bt)

    # 5. 输出报告
    print_report(portfolio, stock_code, "VCP")

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
    对 last_t_depth × vol_exhaust_ratio 做网格扫描。
    评估指标：夏普比率热力图。
    """
    print(f"\n  🔍 参数网格扫描 — VCP | {stock_code}")

    start_dt   = datetime.strptime(start_date, "%Y%m%d")
    load_start = start_dt.replace(year=start_dt.year - 1).strftime("%Y%m%d")

    reader = StockReader()
    df     = reader.get_daily_adj(stock_code, load_start, end_date, mode="qfq")
    if df.empty:
        print(f"  ❌ 数据加载失败: {stock_code}")
        return

    depth_range    = np.arange(0.05, 0.13, 0.01)   # 5% ~ 12%
    vol_ratio_range= np.arange(0.25, 0.60, 0.05)   # 0.25 ~ 0.55

    import pandas as pd
    entries_list = []
    exits_list   = []
    param_names  = []

    for depth in depth_range:
        for vol_ratio in vol_ratio_range:
            ent, ext = vcp_signals.generate_signals(
                df,
                last_t_depth=round(depth, 2),
                vol_exhaust_ratio=round(vol_ratio, 2),
            )
            label = f"{depth:.2f}-{vol_ratio:.2f}"
            entries_list.append(ent.rename(label))
            exits_list.append(ext.rename(label))
            param_names.append(label)

    entries_grid = pd.concat(entries_list, axis=1)
    exits_grid   = pd.concat(exits_list,   axis=1)

    engine    = VbtBacktestEngine(initial_capital=initial_capital)
    portfolio = engine.run_grid(df, entries_grid, exits_grid, param_names)

    save_grid_heatmap(
        portfolio,
        param_x="vol_exhaust_ratio",
        param_y="last_t_depth",
        metric="Sharpe Ratio",
        output_dir=output_dir,
    )

    # 输出最优参数组合
    stats = portfolio.stats(agg_func=None)
    if "Sharpe Ratio" in stats.columns:
        best_idx = stats["Sharpe Ratio"].idxmax()
        print(f"\n  🏆 最优参数组合 (Sharpe最高): {best_idx}")
        print(f"     Sharpe Ratio: {stats.loc[best_idx, 'Sharpe Ratio']:.3f}")
        print(f"     Total Return: {stats.loc[best_idx, 'Total Return [%]']:.2f}%")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="VCP 策略 VectorBT 回测")
    parser.add_argument("--stock",    type=str,   default="600089.SH", help="股票代码")
    parser.add_argument("--start",    type=str,   default="20220101",  help="开始日期 YYYYMMDD")
    parser.add_argument("--end",      type=str,   default="20231231",  help="结束日期 YYYYMMDD")
    parser.add_argument("--capital",  type=float, default=1_000_000.0, help="初始资金")
    parser.add_argument("--depth",    type=float, default=0.08,        help="波幅收缩阈值")
    parser.add_argument("--vol-ratio",type=float, default=0.40,        help="地量倍数")
    parser.add_argument("--output-dir",type=str,  default="backtest_results_vbt", help="输出目录")
    parser.add_argument("--grid",     action="store_true",             help="启用参数网格扫描")
    parser.add_argument("--no-html",  action="store_true",             help="不保存 HTML 权益曲线")
    parser.add_argument("--no-csv",   action="store_true",             help="不保存 CSV 交易明细")
    args = parser.parse_args()

    if args.grid:
        run_grid(
            args.stock, args.start, args.end,
            args.capital, args.output_dir,
        )
    else:
        run_single(
            args.stock, args.start, args.end,
            args.capital, args.depth, args.vol_ratio,
            args.output_dir,
            save_html=not args.no_html,
            save_csv=not args.no_csv,
        )
