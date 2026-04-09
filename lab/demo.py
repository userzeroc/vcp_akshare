"""
demo.py
=======
探索性脚本：调用分析工具层，展示波动统计与 Dash 交互可视化。
"""

import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, dash_table
import dash_bootstrap_components as dbc

from src.data.reader import StockReader
from src.analysis import (
    prepare_price_series,
    WaveDetector,
    WaveConfig,
    print_wave_summary,
    get_wave_stats,
)


if __name__ == "__main__":
    # ── 1. 获取数据 ────────────────────────────────────────────────────────
    reader = StockReader()
    stock_code = "600089.SH"
    df_raw = reader.get_daily_adj(stock_code, "20200101", "20260101", mode="qfq")

    # ── 2. 预处理 ──────────────────────────────────────────────────────────
    df = prepare_price_series(df_raw)

    # ── 3. 波动检测（配置直接在代码中传入）────────────────────────────────
    config = WaveConfig(
        signal_prominence_ratio=0.05,   # 显著波：振幅 > 均价 5%
        noise_prominence_ratio=0.015,   # 噪音波：振幅 > 均价 1.5%
        signal_min_distance=5,
        noise_min_distance=2,
        noise_amplitude_min=1.5,
        noise_amplitude_max=5.0,
    )
    detector = WaveDetector(config)
    result = detector.detect(df)

    # ── 4. 打印统计摘要 ────────────────────────────────────────────────────
    print_wave_summary(result)

    # ── 5. 获取结构化统计（供 Dash 使用） ──────────────────────────────────
    stats = get_wave_stats(result)
    waves_df = stats['waves_df']
    y = df['avg_price'].values

    # ── 5.1 导出统计表为 JSON ──────────────────────────────────────────────
    json_output_path = f"wave_analysis_{stock_code.replace('.', '_')}.json"
    waves_df.to_json(json_output_path, orient='records', force_ascii=False, indent=2)
    print(f"\n波动统计表已导出至: {json_output_path}")

    # ── 6. Dash 交互式可视化 ───────────────────────────────────────────────
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

    def create_base_figure():
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['avg_price'],
            mode='lines',
            name='Avg of Open and Close',
            line=dict(color='blue'),
            opacity=0.6,
        ))

        if len(result.peaks) > 0:
            fig.add_trace(go.Scatter(
                x=df.index[result.peaks],
                y=y[result.peaks],
                mode='markers',
                name='Peaks (High)',
                marker=dict(symbol='triangle-down', size=10, color='red'),
            ))

        if len(result.troughs) > 0:
            fig.add_trace(go.Scatter(
                x=df.index[result.troughs],
                y=y[result.troughs],
                mode='markers',
                name='Troughs (Low)',
                marker=dict(symbol='triangle-up', size=10, color='green'),
            ))

        fig.update_layout(
            title=f'{stock_code} Price Swings & Fluctuations Analysis',
            xaxis_title='Date',
            yaxis_title='Price',
            legend_title='Legend',
            template='plotly_white',
            height=500,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        return fig

    app.layout = dbc.Container([
        dbc.Row(dbc.Col(
            html.H3(f"{stock_code} 波动统计交互分析"),
            className="text-center mt-4 mb-2",
        )),
        # 汇总数字卡片
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("显著波动", className="card-title"),
                html.H4(f"{stats['signal_count']} 次"),
            ])), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("上涨平均幅度", className="card-title"),
                html.H4(f"+{stats['avg_up_amp']:.2f}%"),
            ])), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("下跌平均幅度", className="card-title"),
                html.H4(f"{stats['avg_dn_amp']:.2f}%"),
            ])), width=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("噪音波动", className="card-title"),
                html.H4(f"{stats['noise_count']} 次"),
            ])), width=3),
        ], className="mb-3"),
        dbc.Row(dbc.Col(dcc.Graph(id='price-chart', figure=create_base_figure()))),
        dbc.Row(dbc.Col(
            dash_table.DataTable(
                id='waves-table',
                columns=[{"name": str(c), "id": str(c)} for c in waves_df.columns],
                data=waves_df.to_dict('records') if not waves_df.empty else [],
                row_selectable="single",
                selected_rows=[],
                page_size=15,
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'center', 'fontFamily': 'sans-serif'},
                style_header={'backgroundColor': 'paleturquoise', 'fontWeight': 'bold'},
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': 'lavender'},
                    {'if': {'filter_query': '{阶段} = 上涨'}, 'color': 'crimson'},
                    {'if': {'filter_query': '{阶段} = 下跌'}, 'color': 'forestgreen'},
                ],
            )
        )),
    ], fluid=True)

    @app.callback(
        Output('price-chart', 'figure'),
        Input('waves-table', 'selected_rows'),
    )
    def update_graph(selected_rows):
        fig = create_base_figure()
        if selected_rows and not waves_df.empty:
            row = waves_df.iloc[selected_rows[0]]
            color = 'LightPink' if row['阶段'] == '上涨' else 'LightGreen'
            fig.add_vrect(
                x0=row['起始日期'], x1=row['结束日期'],
                fillcolor=color, opacity=0.4,
                layer="below", line_width=0,
            )
        return fig

    print("\n启动 Dash 交互式服务器中...")
    print("请在浏览器中访问: http://127.0.0.1:8051")
    app.run(debug=False, port=8051)