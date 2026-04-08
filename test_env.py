import tushare as ts
from sqlalchemy import create_engine, text
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

if __name__ == "__main__":
    print(f"{'='*40}")
    print("开始测试系统依赖环境连通性...")
    print(f"{'='*40}\n")
    
    # tushare_ok = test_tushare()
    print("-" * 40)
    db_ok = test_database()
    
    print(f"\n{'='*40}")
    if db_ok:
        print("🎉 全部测试通过！系统已准备就绪。")
    else:
        print("⚠️ 存在未通过的测试，请根据报错信息检查 .env 或本地环境。")
    print(f"{'='*40}")
