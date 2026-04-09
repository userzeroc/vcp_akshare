"""
调试脚本：分析买入条件各因子的满足情况
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from src.data.reader import StockReader

def analyze_buy_conditions():
    """分析各条件的满足情况"""
    reader = StockReader()
    df = reader.get_daily_adj("600089.SH", "20200101", "20260101", mode="qfq")
    
    # 计算指标
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').reset_index(drop=True)
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['vol_ma20'] = df['vol'].rolling(window=20).mean()
    df['vol_ratio'] = df['vol'] / df['vol_ma20']
    
    # 跳过预热期
    warmup = 60
    df_valid = df.iloc[warmup:].copy()
    
    print("=" * 60)
    print("特变电工(600089.SH) 买入条件分析")
    print("=" * 60)
    
    print(f"\n数据范围: {df_valid['trade_date'].min().strftime('%Y-%m-%d')} ~ {df_valid['trade_date'].max().strftime('%Y-%m-%d')}")
    print(f"总交易日: {len(df_valid)} 天")
    
    # 条件A: 价格 > MA60
    cond_a = df_valid['close'] > df_valid['ma60']
    print(f"\n【条件A】价格 > MA60:")
    print(f"  满足天数: {cond_a.sum()} ({cond_a.mean()*100:.1f}%)")
    
    # 条件B: 涨幅 > 5%
    cond_b = df_valid['pct_chg'] > 5.0
    print(f"\n【条件B】涨幅 > 5%:")
    print(f"  满足天数: {cond_b.sum()} ({cond_b.mean()*100:.1f}%)")
    
    # 条件C: 成交量 > 2倍MA20
    cond_c = df_valid['vol'] > df_valid['vol_ma20'] * 2.0
    print(f"\n【条件C】成交量 > 2倍MA20:")
    print(f"  满足天数: {cond_c.sum()} ({cond_c.mean()*100:.1f}%)")
    
    # 三条件同时满足
    cond_all = cond_a & cond_b & cond_c
    print(f"\n【三条件同时满足】")
    print(f"  满足天数: {cond_all.sum()} ({cond_all.mean()*100:.1f}%)")
    
    # 显示满足条件的日期
    if cond_all.sum() > 0:
        print(f"\n满足三条件的日期:")
        for idx in df_valid[cond_all].index:
            row = df_valid.loc[idx]
            date_str = row['trade_date'].strftime('%Y-%m-%d')
            print(f"  {date_str}: 收盘={row['close']:.2f}, 涨幅={row['pct_chg']:.2f}%, 量比={row['vol_ratio']:.2f}x")
    
    # 放宽条件分析
    print(f"\n" + "=" * 60)
    print("放宽条件分析（不同参数组合）")
    print("=" * 60)
    
    for min_pct in [5.0, 4.0, 3.0, 2.0]:
        for vol_mult in [2.0, 1.8, 1.5]:
            cond_test = cond_a & (df_valid['pct_chg'] > min_pct) & (df_valid['vol'] > df_valid['vol_ma20'] * vol_mult)
            print(f"  涨幅>{min_pct}% + 量>{vol_mult}x MA20: {cond_test.sum()} 次")
    
    # 分析涨幅分布
    print(f"\n【涨幅分布】")
    pct_bins = [-100, -5, -2, 0, 2, 5, 10, 100]
    pct_labels = ['<-5%', '-5%~2%', '-2%~0%', '0%~2%', '2%~5%', '5%~10%', '>10%']
    df_valid['pct_bin'] = pd.cut(df_valid['pct_chg'], bins=pct_bins, labels=pct_labels)
    print(df_valid['pct_bin'].value_counts().sort_index())

if __name__ == "__main__":
    analyze_buy_conditions()
