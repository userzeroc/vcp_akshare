import sys
import os
import logging

# 1. 环境准备：确保能找到 src 目录
sys.path.append(os.getcwd())

from src.data.reader.stock_reader import StockReader
from src.strategy.factory import StrategyFactory
from src.backtest.engine import BacktestEngine
from src.backtest.reports import print_report

def run_backtest(ts_code: str, strategy_name: str):
    """
    个股回测标准流程
    :param ts_code: 股票代码 (例如: 601899.SH)
    :param strategy_name: 策略标识 (例如: VCP 或 Momentum)
    """
    # [步骤 1] 初始化数据读取器
    reader = StockReader()
    print(f"正在获取 {ts_code} 的历史行情数据...")
    df = reader.get_daily_adj(ts_code, start_date="20200101", mode="qfq")
    
    if df.empty:
        print(f"错误: 未找到股票 {ts_code} 的数据，请先同步。")
        return

    # [步骤 2] 通过工厂实例化策略
    # 工厂会自动检查 configs/stock_strategies.json 是否有该个股的定制参数
    strategy = StrategyFactory.create(strategy_name, ts_code=ts_code)

    # [步骤 3] 通过 BacktestEngine 运行回测
    print(f"开始运行 {strategy_name} 回测流程...")
    engine = BacktestEngine(initial_capital=1000000.0, debug=True)
    result = engine.run(strategy, df)
    
    # [步骤 4] 使用标准化报表
    print_report(result, stock_info=f"{ts_code} ({strategy_name})")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    # 您只需修改这里即可测试不同股票
    target_stock = "601899.SH"
    target_strategy = "VCP"
    
    run_backtest(target_stock, target_strategy)
