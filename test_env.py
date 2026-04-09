import datetime

import pandas as pd
import tushare as ts
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from src.config import settings

def test_tushare():
    token = settings.tushare.token
    if not token or token == "your_tushare_token_here":
        print("❌ Tushare 测试失败: 请先在 .env 文件中配置有效的 TUSHARE_TOKEN")
        return False
        
    try:
        # 初始化 Tushare Pro 接口
        pro = ts.pro_api(token)
        # 获取最基础的交易日历数据，仅取一条证明接口可用
        df = pro.trade_cal(exchange='', start_date='20240101', end_date='20240110')
        if not df.empty:
            print("✅ Tushare 测试成功! 成功获取到测试数据，Token有效。")
            return True
        else:
            print("⚠️ Tushare 测试异常: 接口未报错但返回数据为空，请检查权限。")
            return False
    except Exception as e:
        print(f"❌ Tushare 测试失败: {str(e)}")
        return False

def test_database():
    db_url = settings.db.database_url
    if "your_db_password" in db_url:
        print("⚠️  警告: 检测到数据库密码为默认示例密码，可能会连接失败。")
        
    engine = create_engine(db_url)
    try:
        # 尝试建立连接并执行最简单的 SQL 语句
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                print(f"✅ 数据库测试成功! 成功连接到: {settings.db.host}:{settings.db.port}/{settings.db.name}")
                return True
    except OperationalError as e:
        error_msg = str(e).split('\n')[0]
        print(f"❌ 数据库测试失败: 无法连接到数据库。详细信息: \n{error_msg}")
        return False
    except Exception as e:
        print(f"❌ 数据库测试发生未知错误: {str(e)}")
        return False

def test_data_layer() -> bool:
    """
    数据层冒烟测试：不调用 Tushare，使用 mock DataFrame 验证:
      1. 4 张核心表已建好
      2. writer / upsert 全链路正确写入 & 幂等覆盖
    """
    try:
        from src.database.session import get_session, get_engine
        from src.database.models import TradeCal, StockBasic, StockDaily, AdjFactor
        from src.data.storage.writer import (
            write_trade_cal, write_stock_basic,
            write_stock_daily, write_adj_factor,
        )

        # ── 1. 检查 4 张表是否存在 ──────────────────────────────────────────
        engine = get_engine()
        inspector = inspect(engine)
        existing = set(inspector.get_table_names())
        required = {"trade_cal", "stock_basic", "stock_daily", "adj_factor"}
        missing = required - existing
        if missing:
            print(f"❌ 数据层测试失败: 以下表不存在: {missing}")
            print("   请先执行: alembic upgrade head")
            return False
        print(f"✅ 表结构检查通过: {sorted(required)}")

        # ── 2. mock 数据 upsert 写入测试 ───────────────────────────────────
        today = datetime.date.today()
        today_str = today.strftime("%Y%m%d")

        # trade_cal
        df_cal = pd.DataFrame([{
            "exchange": "TEST", "cal_date": today_str,
            "is_open": 1, "pretrade_date": today_str,
        }])
        with get_session() as s:
            write_trade_cal(s, df_cal)

        # stock_basic
        df_basic = pd.DataFrame([{
            "ts_code": "000000.TEST", "symbol": "000000", "name": "测试股票",
            "list_status": "L", "list_date": "20100101",
        }])
        with get_session() as s:
            write_stock_basic(s, df_basic)

        # stock_daily
        df_daily = pd.DataFrame([{
            "ts_code": "000000.TEST", "trade_date": today_str,
            "open": 10.0, "high": 11.0, "low": 9.5, "close": 10.5,
            "pre_close": 10.0, "change": 0.5, "pct_chg": 5.0,
            "vol": 10000.0, "amount": 105000.0,
        }])
        with get_session() as s:
            write_stock_daily(s, df_daily)

        # adj_factor
        df_adj = pd.DataFrame([{
            "ts_code": "000000.TEST", "trade_date": today_str, "adj_factor": 1.0,
        }])
        with get_session() as s:
            write_adj_factor(s, df_adj)

        # ── 3. 回读验证 ────────────────────────────────────────────────────
        with get_session() as s:
            row = s.query(StockDaily).filter_by(
                ts_code="000000.TEST", trade_date=today
            ).first()
            assert row is not None, "stock_daily 回读失败"
            assert float(row.close) == 10.5, f"close 值错误: {row.close}"

        # ── 4. 幂等测试：再写一次同数据，不应报错 ──────────────────────────
        df_daily["close"] = 11.0  # 修改 close，验证 update 覆盖
        with get_session() as s:
            write_stock_daily(s, df_daily)
        with get_session() as s:
            row2 = s.query(StockDaily).filter_by(
                ts_code="000000.TEST", trade_date=today
            ).first()
            assert float(row2.close) == 11.0, f"upsert update 失败: {row2.close}"

        # ── 5. 清理测试数据 ─────────────────────────────────────────────────
        with get_session() as s:
            s.query(StockDaily).filter_by(ts_code="000000.TEST").delete()
            s.query(AdjFactor).filter_by(ts_code="000000.TEST").delete()
            s.query(StockBasic).filter_by(ts_code="000000.TEST").delete()
            s.query(TradeCal).filter_by(exchange="TEST").delete()

        print("✅ 数据层测试通过: 写入 → 回读 → 幂等 upsert → 清理，全部正常")
        return True

    except Exception as e:
        print(f"❌ 数据层测试失败: {e}")
        return False


if __name__ == "__main__":
    print(f"{'='*40}")
    print("开始测试系统依赖环境连通性...")
    print(f"{'='*40}\n")

    # tushare_ok = test_tushare()
    print("-" * 40)
    db_ok = test_database()

    print("-" * 40)
    data_ok = test_data_layer() if db_ok else False

    all_ok = db_ok and data_ok
    print(f"\n{'='*40}")
    if all_ok:
        print("🎉 全部测试通过！数据层已就绪，可开始同步 Tushare 数据。")
    else:
        print("⚠️ 存在未通过的测试，请根据报错信息检查 .env 或运行 alembic upgrade head。")
    print(f"{'='*40}")

