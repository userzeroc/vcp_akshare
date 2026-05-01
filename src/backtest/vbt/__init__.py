"""
backtest_vbt — 基于 VectorBT 的向量化回测引擎

模块结构:
  indicators.py   — 公共向量化指标（MA / ATR / 成交量均线）
  signals/        — 策略信号生成（VCP / 动量突破）
  engine.py       — VbtBacktestEngine（封装 vbt.Portfolio.from_signals）
  report.py       — 格式化结果输出 + Plotly 权益曲线
"""
