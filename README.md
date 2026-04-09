# Quant Trading System Architecture

本项目是一个基于 `Tushare` 与 `PostgreSQL` 的本地化量化交易及数据统一处理平台，注重**高内聚低耦合**，实现了数据层、策略层与执行层（回测与实盘）的分离。

## 一、 系统架构图与模块划分

```text
src/
├── config/                 # 配置中心 (管理 Tushare token、PostgreSql 账号及环境变量等)
├── data/                   # 数据管理模块 (Data Layer)
│   ├── fetchers/           # 对接 Tushare 高频、低频数据的抓取层引擎
│   ├── storage/            # 数据清洗、合并及 PostgreSQL 的入库管理机制
│   └── sync/               # 增量及定时同步数据的脚本、Cron Job
├── database/               # 数据库持久层 (Database Layer)
│   ├── migrations/         # 数据库表结构变更及迁移 (Alembic)
│   └── models/             # SQLAlchemy ORM 数据模型定义
├── strategy/               # 策略管理模块 (Strategy Layer)
│   ├── instances/          # 具体的实战或实验策略 (如截面因子、动量策略、均值回归)
│   └── ...                 # 策略基类和公共指标库计算
├── backtest/               # 回测引擎模块 (Backtest Engine)
│   ├── engine/             # 负责事件驱动或向量化驱动的回测核心机制
│   ├── metrics/            # 回测指标分析 (夏普比率、最大回撤、盈亏比等记录与计算)
│   └── reports/            # 交易明细、资金曲线可视化与结果输出
├── trade/                  # 虚实盘交易模块 (Trading Layer)
│   ├── broker/             # 券商实盘接口适配器或模拟盘网关
│   └── portfolio/          # 聚合账户持仓管理、基础风控校验模块
└── utils/                  # 辅助工具模块
    ├── logger.py           # 统一日志打印配置
    └── helpers.py          # 通用函数 (如节假日与交易日判断，日期格式化)
```

## 二、 核心技术栈 (Technology Stack)

- **环境与配置**: `python-dotenv`, `pydantic`
- **金融数据源**: `Tushare Pro`
- **数据处理引擎**: `Pandas`, `Numpy`
- **关系型数据库**: `PostgreSQL`
- **ORM 框架**: `SQLAlchemy` 2.x
- **数据库迁移**: `Alembic`
- **潜在回测库**: 考虑自研回测引擎或接头 `Backtrader`/`Zipline`

## 三、 数据流转路径 (Data Workflow)

1. **获取**: `src/data/fetchers` 调用 Tushare API 拉取 DataFrame 格式的行情或基本面数据。
2. **清洗入库**: 交由 `src/data/storage` 模块通过 `pandas.to_sql` 或 SQLAlchemy ORM 模型对齐格式后批量灌入 PostgreSQL。
3. **日常更新**: `src/data/sync` 内置相关脚本做每日收盘后的增量拉取任务。
4. **回测/实盘消费**: `strategy` 内通过引入 `database.models` 来构建 query 抓取全量本地数据来生成买卖信号，并通过 `backtest.engine` 执行回测模拟。

## 四、 快速启动指引

1. **安装依赖**
   请在虚拟环境下执行以下命令安装相关的基础库：
   ```bash
   pip install -r requirements.txt
   ```

2. **环境变量配置**
   复制 `.env.example` 为 `.env` 然后填入你的实际参数：
   ```bash
   cp .env.example .env
   ```
   里面包含你个人的 Tushare Token 以及 PostgreSQL 数据库的登录用户与口令。

3. **测试配置文件**
   在脚本中仅需如下导入即可安全获取凭证信息：
   ```python
   from src.config import settings
   
   print("Tushare Token is:", settings.tushare.token)
   print("DB URL is:", settings.db.database_url)
   ```
## 五、 策略说明文档
- [动量突破策略 v2.0 规格说明书](docs/momentum_breakout_v2.md)
