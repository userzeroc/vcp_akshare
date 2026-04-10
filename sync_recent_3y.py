
import logging
import sys
import os

# 确保 src 目录在路径中
sys.path.append(os.getcwd())

from src.data.sync.full_sync import run_full_sync

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # 计算三年前的日期
    # 当前建议日期: 20230410 (对应 2026-04-10)
    START_DATE = "20260101"
    
    print(f"\n" + "="*50)
    print(f"🚀 开始同步 2023-04-10 至今（近三年）的全市场数据")
    print(f"   该操作将逐日同步日线行情及复权因子，请保持网络连接。")
    print("="*50 + "\n")
    
    try:
        run_full_sync(start_date=START_DATE)
    except KeyboardInterrupt:
        print("\n🛑 同步已由用户中断。")
    except Exception as e:
        print(f"\n❌ 同步过程中发生错误: {e}")
