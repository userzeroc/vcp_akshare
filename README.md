# VCP AKShare 量化交易平台

本项目是一个基于 `Tushare` 与 `PostgreSQL` 的本地化量化交易及回测平台。经过重构优化，系统实现了**信号生成与执行逻辑的彻底解耦**，支持高度可配置的 A 股策略研究。

## 一、 系统架构

项目遵循模块化设计，确保各层级职责清晰，易于扩展：

```text
src/
├── config/                 # 配置中心 (Tushare Token, 数据库连接等)
├── data/                   # 数据管理模块 (Data Layer)
│   ├── fetchers/           # Tushare 数据抓取引擎
│   ├── reader/             # 统一数据读取器 (ORM-to-DataFrame)
│   ├── storage/            # 数据清洗与 PostgreSQL 入库 (Upsert 引擎)
│   └── sync/               # 数据同步脚本 (全量/每日增量)
├── database/               # 数据库持久层 (SQLAlchemy ORM)
│   └── models/             # 数据库模型 (每日行情、复权因子、交易日历等)
├── strategy/               # 策略管理模块 (Strategy Layer)
│   ├── base.py             # 策略基类 (定义 Signal 接口)
│   ├── factory.py          # 策略工厂 (含参数校验与配置注入)
│   ├── manager.py          # 配置文件管理器
│   ├── vcp_strategy.py     # VCP 波动收缩策略实现
│   └── momentum_breakout.py# 动量突破策略实现
├── backtest/               # 回测引擎模块 (Backtest Engine)
│   ├── engine/             # 通用事件驱动回测核心逻辑
│   ├── metrics/            # 性能指标计算 (收益率、回撤、胜率等)
│   └── reports/            # 报表输出与可视化
│   ├── run_vcp_backtest.py # VCP 独立运行器
│   └── run_momentum_breakout.py # 动量独立运行器
├── analysis/               # 分析工具 (波动检测器、价格工具等)
└── tools/
    └── scanner.py          # 全市场/多股策略扫描分析工具
```

## 二、 核心特性

- **策略/引擎分离**: 策略子类仅负责 `check_buy` / `check_sell` 信号逻辑，回测引擎 `BacktestEngine` 统管资金、仓位与权益曲线计算。
- **配置驱动 (Config-Driven)**: 允许在 `configs/stock_strategies.json` 中为不同个股定制参数，工厂模式自动注入并进行参数校验。
- **高效数据流**: `StockReader` 提供高性能的本地数据加载，支持前/后复权转换，内部优化了 ORM 到 DataFrame 的转换过程。
- **A 股本地化**: 内置 T+1 交易模拟、时间止损（A 股特供）、财报季规避等符合 A 股实战逻辑的特性。

## 三、 快速上手

### 1. 环境配置
```bash
pip install -r requirements.txt
cp .env.example .env  # 填入 TUSHARE_TOKEN 和 DB 连接信息
```

### 2. 数据同步
同步近三年行情数据：
```bash
python sync_recent_3y.py
```

### 3. 运行回测
修改 `src/main.py` 中的目标股票和策略，直接运行：
```bash
python -m src.main
```
或者运行独立的策略回测器：
```bash
python -m src.backtest.run_vcp_backtest --stock 600089.SH
```

### 4. 实时信号扫描
扫描多只股票是否触发 VCP 买入信号：
```bash
python -m src.tools.scanner --codes 600089.SH,601012.SH --strategy vcp
```

## 四、 核心文档
- [策略详细配置与使用指南](docs/STRATEGY_GUIDE.md)
- [动量突破 v2.0 说明](docs/momentum_breakout_v2.md)
- [VCP 分析报告示例](docs/vcp_analysis_report.md)
