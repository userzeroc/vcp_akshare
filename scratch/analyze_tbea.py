import pandas as pd
import matplotlib.pyplot as plt
from src.data.reader.stock_reader import StockReader
import datetime

def analyze_tbea_holder_vs_price():
    reader = StockReader()
    ts_code = "600089.SH"
    end_date = "20260430"
    start_date = "20230101"

    print(f"正在读取 {ts_code} 的数据 ({start_date} - {end_date})...")

    # 1. 获取股东人数数据
    df_holder = reader.get_holder_number(ts_code, start_date=start_date, end_date=end_date)
    if df_holder.empty:
        print("未找到股东人数数据")
        return

    # 2. 获取日线数据 (收盘价)
    df_daily = reader.get_daily(ts_code, start_date=start_date, end_date=end_date)
    if df_daily.empty:
        print("未找到日线数据")
        return

    # 数据整理
    df_holder['ann_date'] = pd.to_datetime(df_holder['ann_date'])
    df_daily['trade_date'] = pd.to_datetime(df_daily['trade_date'])

    # 合并数据：将股东人数映射到对应的交易日价格
    # 股东人数是公告日数据，我们看公告时的价格，以及报告期末的价格
    df_merged = pd.merge_asof(
        df_holder.sort_values('ann_date'),
        df_daily[['trade_date', 'close']].sort_values('trade_date'),
        left_on='ann_date',
        right_on='trade_date',
        direction='backward'
    )

    print("\n=== 特变电工 (600089.SH) 股东人数与股价关联分析 ===")
    print(df_merged[['ann_date', 'end_date', 'holder_num', 'close']].tail(10))

    # 计算简单相关系数
    correlation = df_merged['holder_num'].corr(df_merged['close'])
    print(f"\n股东人数与收盘价的相关系数: {correlation:.4f}")

    if correlation < -0.5:
        print("结论: 呈现显著负相关。股东人数减少（筹码集中）时，股价往往上涨；或股东人数增加（筹码分散）时，股价下跌。")
    elif correlation > 0.5:
        print("结论: 呈现显著正相关。")
    else:
        print("结论: 相关性不显著。")

    # 计算变动趋势
    first_holder = df_merged['holder_num'].iloc[0]
    last_holder = df_merged['holder_num'].iloc[-1]
    holder_change = (last_holder - first_holder) / first_holder * 100

    first_price = df_merged['close'].iloc[0]
    last_price = df_merged['close'].iloc[-1]
    price_change = (last_price - first_price) / first_price * 100

    print(f"\n三年间总变动:")
    print(f"  股东人数变动: {holder_change:.2f}% ({first_holder:,} -> {last_holder:,})")
    print(f"  股价变动:     {price_change:.2f}% ({first_price:.2} -> {last_price:.2f})")

if __name__ == "__main__":
    analyze_tbea_holder_vs_price()
