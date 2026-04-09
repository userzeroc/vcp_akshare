# 📈 策略配属与使用说明文档

本文档详细介绍了当前系统中实现的 **VCP (波动收缩)** 与 **能量突破 (Momentum)** 策略的参数配置、逻辑细节及定制化方法。

---

## 1. 核心架构设计

系统采用了 **配置驱动 (Config-Driven)** 的工厂模式，实现了逻辑与参数的彻底分离：
- **基类 (`BaseStrategy`)**: 统一了所有策略的回测循环、资金管理及性能评估算法。
- **配置管理器 (`StrategyManager`)**: 自动加载 `configs/stock_strategies.json` 中的定制参数。
- **策略工厂 (`StrategyFactory`)**: 根据股票代码自动注入参数并实例化策略。

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

您无需修改任何 Python 代码，只需编辑 [configs/stock_strategies.json](file:///Users/jiachuxiong/webProject/myProject/pythonProject/vcp_akshare/configs/stock_strategies.json) 即可为特定股票定制“股性”参数。

### 优先级顺序
`手动传入参数 (kwargs)` > `JSON 配置文件参数` > `策略类默认参数`

### JSON 配置示例
```json
{
  "601899.SH": {
    "VCPStrategy": {
      "vol_exhaust_ratio": 0.7  // 针对紫金矿业调宽地量门槛
    }
  }
}
```

---

## 5. 快速运行

使用根目录下的 [src/main.py](file:///Users/jiachuxiong/webProject/myProject/pythonProject/vcp_akshare/src/main.py) 进行回测。

*提示：您可以根据需要修改 `main.py` 中的 `target_stock` 和 `target_strategy`。*
