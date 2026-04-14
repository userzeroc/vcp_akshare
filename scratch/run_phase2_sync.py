import logging
import sys
import os
import datetime

# 保证能找到 src 目录
sys.path.append(os.getcwd())

from src.data.sync.full_sync import sync_stock_daily_all, sync_adj_factor_all

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger = logging.getLogger("phase2_sync")
    
    # 用户指令：从 2023 年开始同步
    START_DATE = "20230101"
    
    logger.info(f"===== Phase 2: Recent History Sync Started (from {START_DATE}) =====")
    
    # 1. 同步日线行情
    try:
        logger.info("[1/2] Syncing All-Market Stock Daily Quotes...")
        sync_stock_daily_all(start_date=START_DATE)
    except Exception as e:
        logger.error(f"Stock Daily Sync failed: {e}")
    
    # 2. 同步复权因子
    try:
        logger.info("[2/2] Syncing All-Market Adjustment Factors...")
        sync_adj_factor_all(start_date=START_DATE)
    except Exception as e:
        logger.error(f"Adj Factor Sync failed: {e}")

    logger.info("===== Phase 2: Recent History Sync Completed =====")
