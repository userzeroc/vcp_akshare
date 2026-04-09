import pandas as pd
import plotly.graph_objects as go
from src.data.reader import StockReader
from scipy.signal import find_peaks
import numpy as np


if __name__ == "__main__":
    reader = StockReader()
    stock_code = "600089.SH"
    # 获取洛阳钼业日线数据
    # df = reader.get_daily(stock_code, "20200101", "20210101")
    # print(df.head())

    # 获取洛阳钼业前复权日线数据
    df_qfq = reader.get_daily_adj(stock_code, "20250101", "20260101", mode="qfq")
    print(df_qfq.head())

    # 检查是否有 trade_date，有的话将其设为日期格式并作为索引，方便绘图
    if 'trade_date' in df_qfq.columns:
        df_qfq['trade_date'] = pd.to_datetime(df_qfq['trade_date'])
        df_qfq.set_index('trade_date', inplace=True)
        # 按时间正序排列
        df_qfq.sort_index(inplace=True) 

    # 计算每日开盘价和收盘价的平均值
    # Tushare 的列名通常为 'open' 和 'close'
    df_qfq['avg_price'] = (df_qfq['open'] + df_qfq['close']) / 2

    # --- 波动统计逻辑 ---
    y = df_qfq['avg_price'].values
    # 设定显著性阈值，比如要求波动大于平均价格的 5% 才算一次显著波动
    prominence_threshold = y.mean() * 0.05 
    
    # 找波峰 (Peaks)
    peaks, _ = find_peaks(y, prominence=prominence_threshold, distance=5)
    # 找波谷 (Troughs，通过将数据取反来找)
    troughs, _ = find_peaks(-y, prominence=prominence_threshold, distance=5)
    
    # 组合并排序
    peaks_df = pd.DataFrame({'idx': peaks, 'type': 'peak'})
    troughs_df = pd.DataFrame({'idx': troughs, 'type': 'trough'})
    extrema = pd.concat([peaks_df, troughs_df]).sort_values('idx').reset_index(drop=True)
    
    # 过滤出交替的波峰和波谷
    filtered_extrema = []
    last_type = None
    for _, row in extrema.iterrows():
        if row['type'] != last_type:
            filtered_extrema.append(row)
            last_type = row['type']
    extrema = pd.DataFrame(filtered_extrema)
    
    waves = []
    if not extrema.empty:
        for i in range(1, len(extrema)):
            start_idx = extrema.iloc[i-1]['idx']
            end_idx = extrema.iloc[i]['idx']
            start_type = extrema.iloc[i-1]['type']
            
            start_date = df_qfq.index[start_idx]
            end_date = df_qfq.index[end_idx]
            
            start_price = y[start_idx]
            end_price = y[end_idx]
            
            # 持续多少个交易日
            duration_days = end_idx - start_idx
            
            # 幅度百分比
            amplitude = ((end_price - start_price) / start_price) * 100
            
            waves.append({
                '阶段': '上涨' if start_type == 'trough' else '下跌',
                '起始日期': start_date.strftime('%Y-%m-%d'),
                '结束日期': end_date.strftime('%Y-%m-%d'),
                '起始价格 (元)': round(start_price, 2),
                '结束价格 (元)': round(end_price, 2),
                '持续时间 (交易日)': duration_days,
                '波动幅度 (%)': round(amplitude, 2)
            })
            
    waves_df = pd.DataFrame(waves)
    print("\n" + "="*40)
    print("--- 波动统计摘要 ---")
    print(f"设定阈值: 波动幅度 > 平均价格的 5% ({prominence_threshold:.2f} 元)")
    print(f"总共发生显著波动次数: {len(waves_df)} 次")
    
    if not waves_df.empty:
        uptrends = waves_df[waves_df['阶段'] == '上涨']
        downtrends = waves_df[waves_df['阶段'] == '下跌']
        
        print(f"\n上涨阶段共计: {len(uptrends)} 次")
        if len(uptrends) > 0:
            print(f"平均上涨幅度: {uptrends['波动幅度 (%)'].mean():.2f}%, 平均上涨时间: {uptrends['持续时间 (交易日)'].mean():.0f} 个交易日")
            
        print(f"\n下跌阶段共计: {len(downtrends)} 次")
        if len(downtrends) > 0:
            print(f"平均下跌幅度: {downtrends['波动幅度 (%)'].mean():.2f}%, 平均下跌时间: {downtrends['持续时间 (交易日)'].mean():.0f} 个交易日")

        print("\n详细波动记录:")
        print(waves_df.to_string(index=False))
    print("="*40 + "\n")

    # --- 绘制图表 (使用 Dash 实现交互关联) ---
    import dash
    from dash import dcc, html, Input, Output, dash_table
    import dash_bootstrap_components as dbc
    
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    
    def create_base_figure():
        fig = go.Figure()
        
        # 折线图
        fig.add_trace(go.Scatter(
            x=df_qfq.index,
            y=df_qfq['avg_price'],
            mode='lines',
            name='Avg of Open and Close',
            line=dict(color='blue'),
            opacity=0.6
        ))

        # 波峰
        if len(peaks) > 0:
            fig.add_trace(go.Scatter(
                x=df_qfq.index[peaks],
                y=y[peaks],
                mode='markers',
                name='Peaks (High)',
                marker=dict(symbol='triangle-down', size=10, color='red')
            ))

        # 波谷
        if len(troughs) > 0:
            fig.add_trace(go.Scatter(
                x=df_qfq.index[troughs],
                y=y[troughs],
                mode='markers',
                name='Troughs (Low)',
                marker=dict(symbol='triangle-up', size=10, color='green')
            ))
            
        fig.update_layout(
            title=f'{stock_code} Price Swings & Fluctuations Analysis',
            xaxis_title='Date',
            yaxis_title='Price',
            legend_title='Legend',
            template='plotly_white',
            height=500,
            margin=dict(l=40, r=40, t=40, b=40)
        )
        return fig
        
    app.layout = dbc.Container([
        dbc.Row(dbc.Col(html.H3(f"{stock_code} 波动统计交互分析"), className="text-center mt-4 mb-4")),
        dbc.Row(dbc.Col(dcc.Graph(id='price-chart', figure=create_base_figure()))),
        dbc.Row(dbc.Col(
            dash_table.DataTable(
                id='waves-table',
                columns=[{"name": str(i), "id": str(i)} for i in waves_df.columns],
                data=waves_df.to_dict('records'),
                row_selectable="single",
                selected_rows=[],
                page_size=15,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'center', 'fontFamily': 'sans-serif'},
                style_header={
                    'backgroundColor': 'paleturquoise',
                    'fontWeight': 'bold'
                },
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': 'lavender'}
                ]
            )
        ))
    ], fluid=True)
    
    @app.callback(
        Output('price-chart', 'figure'),
        Input('waves-table', 'selected_rows')
    )
    def update_graph(selected_rows):
        fig = create_base_figure()
        
        if selected_rows:
            selected_idx = selected_rows[0]
            row_data = waves_df.iloc[selected_idx]
            start_date = row_data['起始日期']
            end_date = row_data['结束日期']
            phase = row_data['阶段']
            
            # 高亮颜色：上涨为淡红，下跌为淡绿
            color = 'LightPink' if phase == '上涨' else 'LightGreen'
            
            fig.add_vrect(
                x0=start_date, x1=end_date,
                fillcolor=color,
                opacity=0.4,
                layer="below", line_width=0,
            )
            
        return fig
        
    print("\n启动 Dash 交互式服务器中...")
    print("请在浏览器中访问: http://127.0.0.1:8051")
    app.run(debug=False, port=8051)