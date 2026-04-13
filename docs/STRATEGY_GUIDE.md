# 📈 策略配置与使用说明文档

本文档详细介绍了系统中实现的 **VCP (波动收缩)** 与 **动量突破 (Momentum)** 策略的架构设计、参数配置及定制化方法。

---

## 1. 核心架构设计

系统采用了 **信号与执行分离 (Signal-Engine Decoupling)** 的设计模式，实现了逻辑与执行、逻辑与参数的彻底分离：

- **信号层 (`Strategy`)**: 策略类（如 `VCPStrategy`）仅负责计算技术指标并生成买卖信号（`check_buy` / `check_sell`）。
- **执行层 (`BacktestEngine`)**: 统一处理回测循环、资金管理（仓位计算）、订单执行及权益曲线生成。
- **基类 (`BaseStrategy`)**: 定义了标准信号接口，确保所有策略能无缝对接到回测引擎。
- **配置驱动 (`StrategyFactory`)**: 根据股票代码自动从 `configs/stock_strategies.json` 加载定制参数，并在实例化前进行校验。

---

## 2. VCP (波动收缩) 策略

### 核心逻辑
旨在捕捉股价在高位经过多轮波动由大变小的收缩过程，配合“地量”确认后的突破入场。

### 关键参数说明
| 参数名 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `ma_200` | int | 200 | Stage 2 过滤的长基准线 (年线) |
| `last_t_depth` | float | 0.10 | 最后一次波动收缩的最大幅度 (10%) |
| `vol_exhaust_ratio` | float | 0.50 | “地量”要求：当日成交量/50日均量 < 0.5 |
| `time_stop_days` | int | 3 | **A股特供**：入场后 3 日内若不盈利则强制平仓 |
| `hard_stop_loss` | float | -7.0 | 硬止损位 (-7%) |
| `setup_ready_days` | int | 5 | 形态就绪后等待突破的最长观察天数 |

---

## 3. 能量突破 (Momentum Breakout) 策略

### 核心逻辑
捕捉大级别趋势向好背景下的爆发性机会。

### 关键参数说明
| 参数名 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `ma_long_period` | int | 60 | 宏观趋势过滤线 (MA60) |
| `min_pct_chg` | float | 5.0 | 入场阳线最小涨幅要求 (5%) |
| `vol_multiplier` | float | 2.0 | 成交量爆发倍数要求 (2倍量) |
| `use_trailing_stop` | bool | True | 是否启用 ATR 动态跟踪止盈 |
| `atr_multiplier` | float | 2.5 | 跟踪止盈的 ATR 倍数 (吊灯止盈) |
| `bias_threshold` | float | 0.25 | 60日乖离率上限，防止过度追高 |

---

## 4. 如何定制个股参数？

您无需修改策略代码，只需编辑 `configs/stock_strategies.json` 即可为特定股票定制“股性”参数。

### 校验机制
`StrategyFactory` 具备严苛的**参数校验**功能。如果在配置文件中写错了参数名（Typo），系统会在启动时抛出错误，防止错误的参数被静默忽略。

### 参数优先级
`手动传入参数 (kwargs)` > `JSON 配置文件参数` > `策略类默认参数`

---

## 5. 运行回测与扫描

### 5.1 单股回测
使用 [src/main.py](file:///Users/jiachuxiong/webProject/myProject/pythonProject/vcp_akshare/src/main.py) 定义目标标的并运行。

### 5.2 全市场/多股扫描
使用扫描器检查最新交易日信号：
```bash
python -m src.tools.scanner --codes 600089.SH,601012.SH --strategy vcp
```

### 5.3 结果分析
系统会自动生成包含夏普比率、最大回撤等指标的报表。您可以查看 `backtest/reports/` 模块了解具体的指标定义。
