"""
详细调试脚本：追踪回测逻辑
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from src.data.reader import StockReader

def debug_backtest():
    """详细调试回测逻辑"""
    reader = StockReader()
    df = reader.get_daily_adj("600089.SH", "20200101", "20260101", mode="qfq")
    
    # 计算指标
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').reset_index(drop=True)
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['vol_ma20'] = df['vol'].rolling(window=20).mean()
    
    # 跳过预热期
    warmup = 60
    
    print("=" * 60)
    print("详细调试回测逻辑")
    print("=" * 60)
    
    cash = 1000000.0
    position_open = False
    trade_count = 0
    
    for i in range(warmup, len(df)):
        row = df.iloc[i]
        current_date = row['trade_date'].date()
        
        # 检查买入条件
        cond_a = row['close'] > row['ma60']  # MA60过滤
        cond_b = row['pct_chg'] > 5.0         # 涨幅>5%
        cond_c = row['vol'] > row['vol_ma20'] * 2.0  # 倍量
        
        if cond_a and cond_b and cond_c:
            # 检查是否已经有持仓
            if position_open:
                print(f"⚠️  {current_date}: 信号触发但已有持仓，跳过")
                continue
            
            # 检查是否有次日数据
            if i + 1 >= len(df):
                print(f"⚠️  {current_date}: 是最后一天，无法买入")
                continue
            
            next_row = df.iloc[i + 1]
            buy_price = next_row['open']
            buy_date = next_row['trade_date'].date()
            
            # 计算买入数量
            available_capital = cash * 1.0  # 100%仓位
            quantity = int(available_capital / buy_price / 100) * 100
            
            if quantity <= 0:
                print(f"⚠️  {current_date}: 资金不足，无法买入")
                print(f"    可用资金: {available_capital}, 股价: {buy_price}")
                continue
            
            print(f"\n✅ 买入信号触发!")
            print(f"   信号日期: {current_date}")
            print(f"   收盘价: {row['close']:.2f}, 涨幅: {row['pct_chg']:.2f}%")
            print(f"   买入日期: {buy_date}, 开盘价: {buy_price:.2f}")
            print(f"   买入数量: {quantity}股, 成本: {quantity * buy_price:.2f}")
            print(f"   止损价: {row['low']:.2f}")
            
            # 模拟持仓
            entry_price = buy_price
            stop_loss = row['low']
            position_open = True
            trade_count += 1
            
            # 模拟卖出（用简单逻辑：持有N天后或止损）
            for j in range(i + 1, min(i + 60, len(df))):
                sell_row = df.iloc[j]
                sell_date = sell_row['trade_date'].date()
                sell_price = sell_row['close']
                
                pnl_pct = (sell_price - entry_price) / entry_price * 100
                
                # 止损条件
                if sell_price < stop_loss:
                    pnl = (sell_price - entry_price) * quantity
                    cash += pnl
                    print(f"\n❌ 止损出局!")
                    print(f"   卖出日期: {sell_date}, 卖出价: {sell_price:.2f}")
                    print(f"   盈亏: {pnl:.2f} ({pnl_pct:.2f}%)")
                    position_open = False
                    break
                
                # 持有20天后强制卖出（简化）
                if j >= i + 20:
                    pnl = (sell_price - entry_price) * quantity
                    cash += pnl
                    print(f"\n✅ 止盈出局!")
                    print(f"   卖出日期: {sell_date}, 卖出价: {sell_price:.2f}")
                    print(f"   盈亏: {pnl:.2f} ({pnl_pct:.2f}%)")
                    position_open = False
                    break
                
                # 跌破MA20
                if sell_price < sell_row['ma20']:
                    pnl = (sell_price - entry_price) * quantity
                    cash += pnl
                    print(f"\n✅ MA20止盈!")
                    print(f"   卖出日期: {sell_date}, 卖出价: {sell_price:.2f}")
                    print(f"   MA20: {sell_row['ma20']:.2f}")
                    print(f"   盈亏: {pnl:.2f} ({pnl_pct:.2f}%)")
                    position_open = False
                    break
    
    print(f"\n" + "=" * 60)
    print(f"回测总结:")
    print(f"  总交易次数: {trade_count}")
    print(f"  最终资金: {cash:.2f}")
    print("=" * 60)

if __name__ == "__main__":
    debug_backtest()
