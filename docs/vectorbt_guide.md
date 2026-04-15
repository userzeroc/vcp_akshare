# VectorBT 回测引擎 — 使用与配置说明

> 适用版本：`vectorbt 0.28.5`（免费开源版）  
> 虚拟环境：`.venv/`  
> 最后更新：2026-04-15

---

## 目录

1. [快速开始](#1-快速开始)
2. [命令行参数说明](#2-命令行参数说明)
3. [策略参数配置](#3-策略参数配置)
4. [参数网格扫描](#4-参数网格扫描)
5. [输出文件说明](#5-输出文件说明)
6. [模块结构与扩展开发](#6-模块结构与扩展开发)
7. [与旧引擎对比](#7-与旧引擎对比)
8. [常见问题](#8-常见问题)

---

## 1. 快速开始

> 所有命令均需在项目根目录 `vcp_akshare/` 下执行，使用虚拟环境的 Python。

### 运行 VCP 策略回测

```bash
.venv/bin/python -m src.backtest.run_vbt_vcp \
    --stock 600089.SH \
    --start 20220101 \
    --end 20231231
```

### 运行动量突破策略回测

```bash
.venv/bin/python -m src.backtest.run_vbt_momentum \
    --stock 000001.SZ \
    --start 20220101 \
    --end 20231231
```

运行后将在终端输出完整回测报告，并在 `backtest_results_vbt/` 目录下生成交易明细 CSV 和权益曲线 HTML。

---

## 2. 命令行参数说明

### VCP 策略 (`run_vbt_vcp.py`)

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--stock` | str | `600089.SH` | 股票代码（Tushare 格式） |
| `--start` | str | `20220101` | 回测开始日期（YYYYMMDD） |
| `--end` | str | `20231231` | 回测结束日期（YYYYMMDD） |
| `--capital` | float | `1000000.0` | 初始资金（元） |
| `--depth` | float | `0.08` | VCP 波幅收缩阈值（如 0.08 = 8%） |
| `--vol-ratio` | float | `0.40` | 地量判定倍数（当前量 < 近20日高量 × 此值） |
| `--output-dir` | str | `backtest_results_vbt` | 输出目录 |
| `--grid` | flag | 关闭 | 启用参数网格扫描模式 |
| `--no-html` | flag | 关闭 | 不保存 HTML 权益曲线（减少依赖） |
| `--no-csv` | flag | 关闭 | 不保存 CSV 交易明细 |

### 动量突破策略 (`run_vbt_momentum.py`)

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `--stock` | str | `600089.SH` | 股票代码 |
| `--start` | str | `20220101` | 回测开始日期 |
| `--end` | str | `20231231` | 回测结束日期 |
| `--capital` | float | `1000000.0` | 初始资金 |
| `--ma60` | int | `60` | 长期均线周期（趋势过滤） |
| `--ma20` | int | `20` | 短期均线周期（卖出信号） |
| `--min-pct` | float | `5.0` | 买入日最小涨幅 % |
| `--vol-mult` | float | `2.0` | 成交量倍数（相对20日均量） |
| `--bias` | float | `0.25` | 乖离率上限（防止追高，25% = 涨幅已超均线25%则不买） |
| `--no-trailing` | flag | 关闭 | 禁用 ATR 追踪止盈 |
| `--atr-multi` | float | `2.5` | ATR 追踪止盈倍数 |
| `--output-dir` | str | `backtest_results_vbt` | 输出目录 |
| `--grid` | flag | 关闭 | 启用参数网格扫描 |
| `--no-html` | flag | 关闭 | 不保存 HTML |
| `--no-csv` | flag | 关闭 | 不保存 CSV |

---

## 3. 策略参数配置

### 3.1 VCP 策略参数详解

VCP（Volatility Contraction Pattern，波动收缩形态）策略核心参数：

#### Stage 2 多头排列过滤（固定，不建议修改）

```
收盘价 > MA200 > MA150 > MA120，且 MA50 > MA120
MA200 斜率向上（20日斜率 > 0）
```

只在股价处于明确上升趋势时才考虑入场。

#### `--depth`（波幅收缩阈值）

近10日的高低价波幅 = (10日最高 - 10日最低) / 10日最低

- 数值越小 → 要求波幅收缩越充分，信号越稀少但质量更高
- 建议范围：`0.05`（5%）~ `0.12`（12%）
- **推荐起点**：`0.08`

```bash
# 严格模式（信号少，质量高）
--depth 0.05

# 宽松模式（信号多，适合验证）
--depth 0.12
```

#### `--vol-ratio`（地量判定倍数）

当前成交量 < 近20日最高量 × vol_ratio 才判定为地量

- 数值越小 → 要求量能萎缩越明显
- 建议范围：`0.25` ~ `0.55`
- **推荐起点**：`0.40`

```bash
# 严格地量（信号少）
--vol-ratio 0.25

# 宽松地量
--vol-ratio 0.55
```

#### 其余固定参数（via 代码修改）

在 `src/backtest_vbt/signals/vcp_signals.py` 的 `generate_signals()` 中可调：

| 参数 | 默认 | 说明 |
|---|---|---|
| `contraction_window` | 120 | 寻找近120日高点（base_high） |
| `range_period` | 10 | 价格波幅计算窗口 |
| `vol_surge_ratio` | 1.2 | 突破时放量倍数（相对20日均量） |
| `setup_ready_days` | 5 | 形态就绪后5日内均视为有效 |
| `exit_below_ma` | 50 | 跌破MA50触发卖出 |

---

### 3.2 动量突破策略参数详解

#### `--min-pct`（最小涨幅）

信号日涨幅必须超过此值才触发买入。

- 越高 → 信号越强但越稀少
- 建议范围：`3.0` ~ `8.0`
- **推荐**：`5.0`（对应涨停约5~10%）

#### `--vol-mult`（成交量倍数）

信号日成交量 > 20日均量 × vol_mult

- 越高 → 要求爆量越明显
- 建议范围：`1.5` ~ `3.5`
- **推荐**：`2.0`

#### `--bias`（乖离率上限）

(收盘价 - MA60) / MA60 < bias_threshold

- 防止在价格已经大幅偏离均线时追高
- 建议范围：`0.15` ~ `0.35`
- **推荐**：`0.25`

#### `--ma60` / `--ma20`（均线周期）

- `--ma60`：趋势过滤。MA60 被视为"中长期趋势"，仅当股价在其上方才考虑买入
- `--ma20`：退出信号。股价跌破 MA20 时卖出

---

### 3.3 全局风控配置（代码层修改）

在 `src/backtest_vbt/engine.py` 的 `VbtBacktestEngine.__init__()` 中修改：

```python
class VbtBacktestEngine:
    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        fees: float = 0.001,      # 单边手续费 0.1%（双边合计 0.2%）
        slippage: float = 0.001,  # 滑点 0.1%
        sl_stop: float = 0.08,    # 硬止损 8%（相对买入价）
        freq: str = "D",          # 数据频率：日线
    ):
```

---

## 4. 参数网格扫描

> 建议在针对个股完成基础参数定制后再使用网格扫描进行精细优化。

### VCP 网格扫描

扫描维度：`last_t_depth` × `vol_exhaust_ratio`

```bash
.venv/bin/python -m src.backtest.run_vbt_vcp \
    --stock 600089.SH \
    --start 20220101 \
    --end 20231231 \
    --grid
```

扫描范围（可在代码中修改）：
- `last_t_depth`：5% ~ 12%，步长 1%
- `vol_exhaust_ratio`：0.25 ~ 0.55，步长 0.05

### 动量突破网格扫描

扫描维度：`min_pct_chg` × `vol_multiplier`

```bash
.venv/bin/python -m src.backtest.run_vbt_momentum \
    --stock 600089.SH \
    --start 20220101 \
    --end 20231231 \
    --grid
```

扫描范围：
- `min_pct_chg`：3% ~ 8%，步长 1%
- `vol_multiplier`：1.5 ~ 3.5，步长 0.5

### 扫描输出

```
backtest_results_vbt/
└── grid_Sharpe_Ratio.html     ← Plotly 热力图（横轴/纵轴为扫描参数）
```

控制台同时输出 Sharpe 最高的参数组合。

---

## 5. 输出文件说明

所有输出默认保存到 `backtest_results_vbt/` 目录（可通过 `--output-dir` 修改）。

| 文件名 | 触发条件 | 内容 |
|---|---|---|
| `equity_<code>.html` | 默认生成（`--no-html` 跳过） | Plotly 交互式权益曲线，含持仓区间标注 |
| `trades_<code>.csv` | 默认生成（`--no-csv` 跳过） | 完整交易明细（入/出场时间、价格、PnL、状态） |
| `grid_Sharpe_Ratio.html` | 仅 `--grid` 模式 | 参数热力图 |

**CSV 字段说明：**

| 字段 | 说明 |
|---|---|
| `Entry Timestamp` | 入场日期 |
| `Exit Timestamp` | 出场日期 |
| `Size` | 持仓数量（股数） |
| `Avg Entry Price` | 平均入场价（已复权） |
| `Avg Exit Price` | 平均出场价（已复权） |
| `PnL` | 盈亏金额（元） |
| `Return [%]` | 该笔交易收益率 % |
| `Status` | `Closed` = 已平仓 / `Open` = 持仓中 |

---

## 6. 模块结构与扩展开发

### 新增自定义策略

**Step 1**：在 `src/backtest_vbt/signals/` 下新建 `xxx_signals.py`:

```python
def generate_signals(df, param_a=..., param_b=...) -> Tuple[pd.Series, pd.Series]:
    """
    返回 (entries, exits)，均为与 df.index 对齐的布尔 Series。
    """
    # 计算指标
    ma = calc_sma(df['close'], 20)
    # 买入条件
    entries = df['close'] > ma
    # 卖出条件
    exits = df['close'] < ma * 0.95
    return entries.fillna(False), exits.fillna(False)
```

**Step 2**：新增回测入口 `src/backtest/run_vbt_xxx.py`，参考 `run_vbt_vcp.py` 结构。

**Step 3**：调用引擎：

```python
from src.backtest_vbt.engine import VbtBacktestEngine
from src.backtest_vbt.report import print_report, save_equity_curve

engine    = VbtBacktestEngine(initial_capital=1_000_000)
portfolio = engine.run(df, entries, exits)
print_report(portfolio, stock_code="000001.SZ", strategy_name="我的策略")
save_equity_curve(portfolio, "000001.SZ")
```

### 可用指标函数（`src/backtest_vbt/indicators.py`）

```python
from src.backtest_vbt.indicators import (
    calc_sma,              # 简单移动平均
    calc_ema,              # 指数移动平均
    calc_ma_slope,         # 均线斜率（N日变化率）
    calc_atr,              # ATR（平均真实波幅）
    calc_vol_ma,           # 成交量均线
    calc_vol_max,          # 成交量滚动最大值
    calc_bias,             # 乖离率
    calc_rolling_range_pct,# 滚动价格波幅百分比
)
```

---

## 7. 与旧引擎对比

| 维度 | 旧引擎（自研）| VBT 引擎 |
|---|---|---|
| 执行方式 | Python for-loop 逐日 | NumPy/Pandas 全向量 |
| 单股速度 | ~1–2 秒 | < 0.1 秒 |
| 全市场速度 | 数分钟 | 秒级 |
| 夏普/卡玛/索提诺 | ❌ | ✅ 内置 |
| ATR 追踪止盈 | 手动实现 | 参数化配置 |
| 参数网格扫描 | ❌ | ✅ `--grid` |
| Plotly 权益曲线 | ❌ | ✅ HTML |
| 旧代码兼容 | — | ✅ 旧入口保留不变 |

### 旧引擎入口（继续可用）

```bash
# 旧引擎 VCP
.venv/bin/python -m src.backtest.run_vcp_backtest \
    --stock 600089.SH --start 20220101 --end 20231231

# 旧引擎 动量突破
.venv/bin/python -m src.backtest.run_momentum_breakout \
    --stock 600089.SH --start 20200101 --end 20260101
```

---

## 8. 常见问题

### Q1：VCP 策略无买入信号

**原因**：默认参数（`depth=0.08, vol_ratio=0.40`）在熊市或震荡市中信号极少，这是策略设计本意（高质量入场）。

**解决**：
1. 逐步放宽参数：`--depth 0.12 --vol-ratio 0.55`
2. 延长回测区间，使用牛市数据验证（如 2020–2021）
3. 运行 `--grid` 扫描找到该股最优参数

### Q2：年化收益率显示 `N/A`

**原因**：VBT 在某些版本中对较短区间的年化计算返回 `N/A`，属正常现象，总收益率计算不受影响。

### Q3：手续费如何修改

在 `src/backtest_vbt/engine.py` 中修改 `fees` 和 `slippage`，单位为小数：

```python
# 当前配置：单边 0.1%（双边合计约 0.2%）
VbtBacktestEngine(fees=0.001, slippage=0.001)

# 如需更低成本（如机构席位）
VbtBacktestEngine(fees=0.0003, slippage=0.0005)
```

### Q4：如何加载并比较多只股票

目前为单股模式。如需多股对比，可在脚本中循环调用：

```python
from src.backtest.run_vbt_momentum import run_single

stocks = ["600519.SH", "000858.SZ", "600036.SH"]
for code in stocks:
    run_single(code, "20220101", "20231231", output_dir="results_multi")
```

### Q5：データ数据缺失导致报错

确保在运行回测前已完成数据同步：

```bash
# 同步基础行情（stock_daily / adj_factor）
.venv/bin/python -m src.data.sync.full_sync --start 20210101 --end 20231231

# 同步新增表（index_daily / daily_basic）
.venv/bin/python -m src.data.sync.sync_new_tables --start 20210101 --end 20231231
```
