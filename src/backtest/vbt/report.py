"""
VectorBT 回测结果报告模块
==========================

职责:
  - 格式化输出关键性能指标（对齐现有 print_report 风格）
  - 生成 Plotly 交互式权益曲线（保存为 HTML）
  - 支持参数网格热力图（夏普/收益率）
"""

import os
import logging
from typing import Optional

import pandas as pd
import vectorbt as vbt

from src.config.settings import settings
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 文字报告
# ---------------------------------------------------------------------------

def print_report(
    portfolio: vbt.Portfolio,
    stock_code: str = "",
    strategy_name: str = "",
) -> None:
    """
    打印 VBT 回测报告（中文风格，对齐旧版 print_report）。

    额外输出 VBT 特有指标（夏普、卡玛、索提诺等）。
    """
    stats = portfolio.stats()
    trades = portfolio.trades.records_readable

    tag = f"{strategy_name} | {stock_code}" if stock_code else strategy_name

    print(f"\n{'='*62}")
    print(f"  📈 VBT 回测报告  {tag}")
    print(f"{'='*62}")

    def _get(key, default="N/A"):
        return stats[key] if key in stats.index else default

    # 基本信息
    print(f"  回测区间    : {_get('Start')} ~ {_get('End')}")
    print(f"  回测时长    : {_get('Period')}")
    print()

    # 收益指标
    print(f"  【收益】")
    print(f"  总收益率    : {_get('Total Return [%]'):.2f}%" if isinstance(_get('Total Return [%]'), float) else f"  总收益率    : {_get('Total Return [%]')}")
    print(f"  年化收益率  : {_get('Annualized Return [%]'):.2f}%" if isinstance(_get('Annualized Return [%]'), float) else f"  年化收益率  : {_get('Annualized Return [%]')}")
    print()

    # 风险指标
    print(f"  【风险】")
    _mdd = _get('Max Drawdown [%]')
    print(f"  最大回撤    : {_mdd:.2f}%" if isinstance(_mdd, float) else f"  最大回撤    : {_mdd}")
    print(f"  夏普比率    : {_get('Sharpe Ratio'):.3f}" if isinstance(_get('Sharpe Ratio'), float) else f"  夏普比率    : {_get('Sharpe Ratio')}")
    print(f"  卡玛比率    : {_get('Calmar Ratio'):.3f}" if isinstance(_get('Calmar Ratio'), float) else f"  卡玛比率    : {_get('Calmar Ratio')}")
    print(f"  索提诺比率  : {_get('Sortino Ratio'):.3f}" if isinstance(_get('Sortino Ratio'), float) else f"  索提诺比率  : {_get('Sortino Ratio')}")
    print()

    # 交易统计
    print(f"  【交易】")
    print(f"  总交易次数  : {_get('Total Trades')}")
    _wr = _get('Win Rate [%]')
    print(f"  胜率        : {_wr:.2f}%" if isinstance(_wr, float) else f"  胜率        : {_wr}")
    _pf = _get('Profit Factor')
    print(f"  盈亏比      : {_pf:.3f}" if isinstance(_pf, float) else f"  盈亏比      : {_pf}")
    _aw = _get('Avg Winning Trade [%]')
    print(f"  平均盈利    : {_aw:.2f}%" if isinstance(_aw, float) else f"  平均盈利    : {_aw}")
    _al = _get('Avg Losing Trade [%]')
    print(f"  平均亏损    : {_al:.2f}%" if isinstance(_al, float) else f"  平均亏损    : {_al}")
    _best = _get('Best Trade [%]')
    print(f"  最佳交易    : {_best:.2f}%" if isinstance(_best, float) else f"  最佳交易    : {_best}")
    _worst = _get('Worst Trade [%]')
    print(f"  最差交易    : {_worst:.2f}%" if isinstance(_worst, float) else f"  最差交易    : {_worst}")
    print(f"{'='*62}")

    # 交易明细表
    if not trades.empty:
        print(f"\n  📋 交易明细（最近10笔）：")
        cols = ['Entry Timestamp', 'Exit Timestamp', 'Size', 'Avg Entry Price',
                'Avg Exit Price', 'PnL', 'Return [%]', 'Status']
        display_cols = [c for c in cols if c in trades.columns]
        print(trades[display_cols].tail(10).to_string(index=False))
    print()


# ---------------------------------------------------------------------------
# 权益曲线（Plotly HTML）
# ---------------------------------------------------------------------------

def save_equity_curve(
    portfolio: vbt.Portfolio,
    stock_code: str = "",
    output_dir: str = str(settings.paths.backtest_dir),
    auto_open: bool = False,
) -> str:
    """
    生成并保存 Plotly 交互式权益曲线 HTML。

    返回保存的文件路径。
    """
    os.makedirs(output_dir, exist_ok=True)
    safe_code = stock_code.replace(".", "_")
    filename  = f"equity_{safe_code}.html" if safe_code else "equity_curve.html"
    filepath  = os.path.join(output_dir, filename)

    fig = portfolio.plot()
    fig.write_html(filepath, auto_open=auto_open)

    logger.info("权益曲线已保存: %s", filepath)
    print(f"  📊 权益曲线已保存: {filepath}")
    return filepath


def save_trades_csv(
    portfolio: vbt.Portfolio,
    stock_code: str = "",
    output_dir: str = str(settings.paths.backtest_dir),
) -> str:
    """将交易明细导出为 CSV。"""
    os.makedirs(output_dir, exist_ok=True)
    safe_code = stock_code.replace(".", "_")
    filename  = f"trades_{safe_code}.csv" if safe_code else "trades.csv"
    filepath  = os.path.join(output_dir, filename)

    trades = portfolio.trades.records_readable
    if not trades.empty:
        trades.to_csv(filepath, index=False, encoding="utf-8-sig")
        print(f"  💾 交易明细已保存: {filepath}")
    else:
        print("  ⚠️  无交易记录可导出")
    return filepath


# ---------------------------------------------------------------------------
# 参数网格热力图（供 --grid 模式使用）
# ---------------------------------------------------------------------------

def save_grid_heatmap(
    portfolio: vbt.Portfolio,
    param_x: str,
    param_y: str,
    metric: str = "Sharpe Ratio",
    output_dir: str = str(settings.paths.backtest_dir),
) -> str:
    """
    生成参数网格热力图（Plotly，保存为 HTML）。

    参数:
        portfolio  — 多列 vbt.Portfolio（网格扫描结果）
        param_x    — X 轴参数名
        param_y    — Y 轴参数名
        metric     — 热力图指标（默认 Sharpe Ratio）
        output_dir — 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"grid_{metric.replace(' ', '_')}.html")

    try:
        stats = portfolio.stats(agg_func=None)
        metric_series = stats[metric] if metric in stats.columns else stats.iloc[:, 0]

        import plotly.express as px
        fig = px.imshow(
            metric_series.unstack(),
            title=f"参数扫描热力图 — {metric}",
            labels={"x": param_x, "y": param_y, "color": metric},
            color_continuous_scale="RdYlGn",
        )
        fig.write_html(filepath)
        print(f"  🗺️  参数热力图已保存: {filepath}")
    except Exception as e:
        logger.warning("热力图生成失败: %s", e)

    return filepath
