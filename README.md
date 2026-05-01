# VCP AKShare 量化交易平台

本项目是一个基于 `Tushare` 与 `PostgreSQL` 的本地化量化交易及回测平台。经过重构优化，系统实现了**信号生成与执行逻辑的彻底解耦**，支持高度可配置的 A 股策略研究。

## 一、 系统架构

项目遵循模块化设计，确保各层级职责清晰，易于扩展：

```text
src/
├── config/                 # 配置中心 (含 PathConfig 全局路径管理)
├── data/                   # 数据管理模块
├── database/               # 数据库持久层 (SQLAlchemy)
├── strategy/               # 策略定义 (VCP, Momentum 等)
├── backtest/               # 回测引擎模块
│   ├── engine/             # 事件驱动核心
│   ├── vbt/                # VectorBT 向量化回测引擎
│   ├── metrics/            # 指标计算
│   └── reports/            # 报表输出
├── analysis/               # 股性分析与波段检测
└── tools/                  # 辅助工具 (Scanner)

configs/                    # 外部 JSON 配置文件
experiments/                # 实验性脚本与研究代码 (原 lab/ scratch/)
results/                    # 统一结果输出目录 (回测报告、CSV、HTML)
docs/                       # 系统文档
logs/                       # 运行日志
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

#### Tushare 代理配置 (可选)
如果需要通过代理或 Cloudflare Workers 访问 Tushare，请在 `.env` 中设置 `TUSHARE_HTTP_URL`：
```env
TUSHARE_HTTP_URL=https://your-proxy-url.workers.dev
```
> [!WARNING]
> 使用动态 IP 代理（如某些 Workers）可能会触发 Tushare 的 **IP 数量超限** 限制。如果遇到该错误，建议切换回官方直连模式或增加请求间隔。

### 2. 数据同步
首次运行需初始化基础数据（交易日历、股票列表）：
```bash
python -m src.data.sync.init_foundation
```
或者同步特定个股/指数的历史数据：
```bash
python -m src.data.sync.manual_sync
```
日常增量更新：
```bash
python -m src.data.sync.daily_sync
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
- [📖 系统详细技术文档](docs/detailed_documentation.md)
- [🚀 优化策略与开发计划](docs/optimization_plan.md)
- [策略详细配置与使用指南](docs/STRATEGY_GUIDE.md)
- [Data 模块设计文档](docs/data_module_design.md)
- [动量突破 v2.0 说明](docs/momentum_breakout_v2.md)
- [VCP 分析报告示例](docs/vcp_analysis_report.md)
