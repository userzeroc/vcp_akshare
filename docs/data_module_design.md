# Data 模块设计文档

> 本文档详细说明 `src/data` 模块的架构设计、各层职责及使用方式。

---

## 1. 模块概览

```
src/data/
├── fetchers/          # 数据获取层：对接 Tushare API
│   └── tushare_client.py
├── storage/           # 数据存储层：清洗 + 幂等写入
│   ├── cleaner.py     # 数据清洗
│   ├── upsert.py      # 幂等写入引擎
│   └── writer.py      # 高级封装入口
└── sync/              # 同步调度层：全量/增量/手动同步
    ├── full_sync.py   # 全量历史初始化
    ├── daily_sync.py  # 每日增量同步
    └── manual_sync.py # 单只股票手动同步
```

**三层职责分工：**
| 层级 | 职责 | 关键词 |
|------|------|--------|
| `fetchers` | 从 Tushare 获取原始数据 | API、限流、重试 |
| `storage` | 清洗数据格式 + 幂等写入数据库 | 清洗、UPSERT、事务 |
| `sync` | 编排同步策略（何时、同步什么） | 增量、全量、手动 |

---

## 2. 数据获取层 (`fetchers/`)

### 2.1 Tushare Client

**文件**: `fetchers/tushare_client.py`

**核心功能：**
- **单例模式**：全局共享一个 `ts.pro_api()` 连接，避免重复初始化
- **限流机制**：每次 API 调用后 sleep 0.4 秒（120分账号建议值）
- **重试机制**：失败后指数退避（2s → 4s → 8s），最多 3 次

**使用方式：**
```python
from src.data.fetchers.tushare_client import client

# 查询日线数据
df = client.query("daily", ts_code="000001.SZ", start_date="20240101")

# 查询股票基本信息
df = client.query("stock_basic", list_status="L")
```

**支持的接口：**
| 接口名 | 说明 |
|--------|------|
| `daily` | 日线行情 |
| `adj_factor` | 复权因子 |
| `stock_basic` | 股票基本信息 |
| `trade_cal` | 交易日历 |

---

## 3. 数据存储层 (`storage/`)

### 3.1 Cleaner — 数据清洗

**文件**: `storage/cleaner.py`

**清洗规则（对所有表通用）：**
1. **删除空主键行** — `dropna(subset=[主键列])`
2. **日期格式转换** — `YYYYMMDD` 字符串 → `datetime.date`
3. **数值类型转换** — `pd.to_numeric(..., errors='coerce')` → float
4. **字符串去空白** — `str.strip()`，并替换 `nan` 为 `None`
5. **去重** — 同一批次内的重复行删除

**各表专用清洗函数：**
| 函数 | 主键 | 特殊处理 |
|------|------|----------|
| `clean_trade_cal` | (exchange, cal_date) | is_open 转 Int8 |
| `clean_stock_basic` | ts_code | 多个字符串字段 strip |
| `clean_stock_daily` | (ts_code, trade_date) | 价格/量字段转 numeric |
| `clean_adj_factor` | (ts_code, trade_date) | adj_factor 转 numeric |

### 3.2 Upsert — 幂等写入引擎

**文件**: `storage/upsert.py`

**核心机制：**
- 使用 PostgreSQL 原生 `INSERT ... ON CONFLICT DO UPDATE`
- 冲突时**只更新非主键列**，主键列保持不变
- 支持**分批写入**：按 `chunk_size=2000` 分批执行，避免单条 SQL 过长
- **幂等性**：重复执行同一数据不会报错，也不会产生重复行

**函数签名：**
```python
def upsert_dataframe(
    session: Session,
    model: Type[Base],
    df: pd.DataFrame,
    conflict_columns: Sequence[str],  # 触发冲突的列（通常是主键）
    chunk_size: int = 2000,
) -> int
```

### 3.3 Writer — 高级封装

**文件**: `storage/writer.py`

**设计理念**：将 `cleaner` + `upsert` 组合成单次调用的入库函数。

| 函数 | 写入表 | 冲突列 |
|------|--------|--------|
| `write_trade_cal` | TradeCal | (exchange, cal_date) |
| `write_stock_basic` | StockBasic | ts_code |
| `write_stock_daily` | StockDaily | (ts_code, trade_date) |
| `write_adj_factor` | AdjFactor | (ts_code, trade_date) |

**使用方式：**
```python
from src.database.session import get_session
from src.data.storage.writer import write_stock_daily

with get_session() as session:
    n = write_stock_daily(session, raw_df)
    print(f"写入 {n} 行")
```

---

## 4. 同步调度层 (`sync/`)

### 4.1 Full Sync — 全量初始化

**文件**: `sync/full_sync.py`

**用途**：首次建库时，拉取所有历史数据。

**执行顺序（依赖关系）：**
1. `sync_trade_cal` — 必须最先，其他模块依赖交易日列表
2. `sync_stock_basic` — 股票基本信息（全量）
3. `sync_stock_daily_all` — **按交易日逐日拉取**（避免单次超限）
4. `sync_adj_factor_all` — **按交易日逐日拉取**

**执行方式：**
```bash
python -m src.data.sync.full_sync
```

**注意事项：**
- 120分账号全量同步约需数小时
- 支持断点续传（upsert 幂等，重跑会补齐）

### 4.2 Daily Sync — 每日增量

**文件**: `sync/daily_sync.py`

**策略**：
1. 查询本地各表最新日期
2. 从 Tushare 拉取"最新日期之后"的数据
3. 幂等写入（已有数据跳过）

**同步任务：**
| 函数 | 策略 |
|------|------|
| `sync_trade_cal_incremental` | 从最新日期拉到今日 |
| `sync_stock_basic_incremental` | 全量刷新（约 5000 行，速度快） |
| `sync_stock_daily_incremental` | 逐日拉取交易日列表中的日期 |
| `sync_adj_factor_incremental` | 逐日拉取复权因子 |

**执行方式：**
```bash
python -m src.data.sync.daily_sync
```

**建议**：配合 cron 或 APScheduler 在每个交易日 17:00 后执行。

### 4.3 Manual Sync — 单只股票手动同步

**文件**: `sync/manual_sync.py`

**用途**：单独同步或修复某一只（或几只）股票的历史数据，不必执行全市场更新。

**使用方式：**
```python
from src.data.sync.manual_sync import sync_single_stock

# 代码调用
sync_single_stock("000001.SZ", "20200101", "20240101")

# 或命令行
python -m src.data.sync.manual_sync
```

---

## 5. 完整数据流图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户调用层                                │
│   run_full_sync()  /  run_daily_sync()  /  sync_single_stock()  │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Sync 调度层 (sync/)                         │
│   full_sync.py / daily_sync.py / manual_sync.py                │
│   职责: 决定何时同步、同步什么、是否分批                          │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Fetchers 获取层 (fetchers/)                    │
│                      tushare_client.py                           │
│   职责: 单例 API、限流 0.4s、重试机制                              │
│   输出: pd.DataFrame（原始数据）                                  │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Storage 存储层 (storage/)                       │
│                                                               │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │  cleaner    │───▶│   writer    │───▶│  upsert     │        │
│   │  数据清洗   │    │  高级封装   │    │  幂等写入   │        │
│   └─────────────┘    └─────────────┘    └──────┬──────┘        │
│                                                 │               │
└─────────────────────────────────────────────────┼───────────────┘
                                                  ▼
                                    ┌─────────────────────────┐
                                    │    PostgreSQL 数据库    │
                                    │   (upsert 幂等写入)      │
                                    └─────────────────────────┘
```

---

## 6. 数据库会话管理

**文件**: `src/database/session.py`

**Session 工厂：**
```python
from src.database.session import get_session

with get_session() as session:
    # 自动 commit / rollback / close
    session.add(obj)
```

**事务特性：**
- `autoflush=False` — 手动控制 flush
- `autocommit=False` — 显式 commit
- `expire_on_commit=False` — commit 后对象属性不失效

---

## 7. 使用示例

### 7.1 首次初始化（全量同步）
```python
from src.data.sync.full_sync import run_full_sync

run_full_sync(start_date="20100101")
```

### 7.2 每日定时任务
```python
from src.data.sync.daily_sync import run_daily_sync

run_daily_sync()
```

### 7.3 手动同步单只股票
```python
from src.data.sync.manual_sync import sync_single_stock

sync_single_stock("000001.SZ", "20200101", "20240101")
```

### 7.4 自定义数据获取
```python
from src.data.fetchers.tushare_client import client
from src.data.storage.writer import write_stock_daily
from src.database.session import get_session

# 获取数据
df = client.query("daily", ts_code="000001.SZ", start_date="20240101")

# 写入数据库
with get_session() as session:
    n = write_stock_daily(session, df)
    print(f"写入 {n} 行")
```

---

## 8. 关键设计原则

1. **幂等性**：所有写入操作使用 `INSERT ON CONFLICT DO UPDATE`，重复执行安全
2. **分层解耦**：获取层、存储层、调度层各司其职，便于单独测试和维护
3. **限流保护**：Tushare API 调用有内置限流，避免被封禁
4. **断点续传**：依赖 upsert 幂等特性，失败后可重跑补齐
5. **事务安全**：使用 context manager 自动管理 commit/rollback
