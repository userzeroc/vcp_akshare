"""
A股策略扫描工具 (A-Share Strategy Scanner)
========================================

功能：针对给定股票列表，检查最新一个交易日是否触发了买入信号。
用法：PYTHONPATH=. python -m src.tools.scanner --codes 600089.SH,601012.SH --strategy vcp
"""

import logging
import argparse
import pandas as pd
from datetime import datetime, timedelta
from typing import List

from src.data.reader import StockReader
from src.strategy.factory import StrategyFactory
from src.backtest.engine import BacktestEngine

logger = logging.getLogger(__name__)


def scan_stocks(codes: List[str], strategy_type: str):
    reader = StockReader()
    
    # 策略名称映射
    strategy_alias = {
        'vcp': 'VCP',
        'momentum': 'Momentum',
    }
    strategy_name = strategy_alias.get(strategy_type.lower())
    if not strategy_name:
        print(f"❌ 不支持的策略类型: {strategy_type}")
        return

    print(f"\n{'='*70}")
    print(f"🔍 正在使用 [{strategy_type.upper()}] 策略扫描 {len(codes)} 只股票...")
    print(f"{'='*70}\n")
    
    # 设置表格标题
    header = f"{'代码':<12} | {'最新日期':<12} | {'信号':<8} | {'价格':<8} | {'理由'}"
    print(header)
    print("-" * 80)

    engine = BacktestEngine(initial_capital=1000000.0, debug=False)

    for code in codes:
        try:
            # 获取最近 300 天数据（确保指标计算所需的足够数据量）
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=450)).strftime('%Y%m%d')
            
            df = reader.get_daily_adj(code, start_date, end_date, mode='qfq')
            if df.empty:
                print(f"{code:<12} | {'无数据':<12} | {'-':<8} | {'-':<8} | 数据加载失败")
                continue
            
            # 通过工厂创建策略实例（自动加载个股配置参数）
            strategy = StrategyFactory.create(strategy_name, ts_code=code)
            
            # 运行策略
            result = engine.run(strategy, df)
            
            # 获取最新交易日期
            latest_trade_date = df['trade_date'].max()
            if hasattr(latest_trade_date, 'date'):
                latest_trade_date = latest_trade_date.date()
                
            # 查找最后一笔信号
            hit = False
            last_signal = None
            if result.signals:
                # 过滤出买入信号
                buy_signals = [s for s in result.signals if s.signal_type == 'buy']
                if buy_signals:
                    last_signal = buy_signals[-1]
                    # 如果买入信号的日期就是最新日期，则判定为触发
                    if last_signal.date >= latest_trade_date:
                        hit = True
            
            status = "🚀 BUY" if hit else "⚪️ WAIT"
            price_str = f"{last_signal.price:>8.2f}" if hit else f"{df['close'].iloc[-1]:>8.2f}"
            reason = last_signal.reason if hit else "未触发信号"
            
            print(f"{code:<12} | {str(latest_trade_date):<12} | {status:<8} | {price_str} | {reason}")
            
        except Exception as e:
            print(f"{code:<12} | {'ERROR':<12} | {'-':<8} | {'-':<8} | {str(e)}")

    print("-" * 80)
    print(f"\n✨ 扫描完成。")

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    parser = argparse.ArgumentParser(description='A股策略扫描工具')
    parser.add_argument('--codes', type=str, required=True, help='股票代码列表，逗号分隔 (如 600089.SH,601012.SH)')
    parser.add_argument('--strategy', type=str, default='vcp', choices=['vcp', 'momentum'], help='选择使用的策略')
    
    args = parser.parse_args()
    
    stock_list = [c.strip() for c in args.codes.split(',')]
    scan_stocks(stock_list, args.strategy)
