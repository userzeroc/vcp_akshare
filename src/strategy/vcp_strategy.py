"""
A股本地化 VCP (Volatility Contraction Pattern) 策略
==================================================

核心逻辑：
1. Stage 2 趋势过滤：股价、均线呈多头排列，年线向上。
2. 波动收缩 (VCP) 检测：寻找价格波幅逐渐减小的形态。
3. 地量确认：突破前夕成交量极度萎缩。
4. A股本地化：尾盘入场确认、时间止损（3日不涨即撤）。
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import date
from .momentum_breakout import Signal, Trade, Position, BacktestResult


class VCPStrategy:
    def __init__(
        self,
        ma_50: int = 50,
        ma_120: int = 120,
        ma_150: int = 150,
        ma_200: int = 200,
        contraction_window: int = 120,   # 形态溯源窗口
        max_t1_depth: float = 0.50,      # 第一波最大回调深度 (50%)
        last_t_depth: float = 0.10,      # A股最后一次波幅收缩要求 (放宽至10%)
        vol_exhaust_ratio: float = 0.50, # “地量”要求：成交量 < 近期均量的 1/2
        hard_stop_loss: float = -7.0,    # 硬止损限制 (-7%)
        time_stop_days: int = 3,         # A股特供：时间止损 (3日不脱离成本)
        min_profit_3d: float = 1.0,      # 3日内最小涨幅要求 (1%)
        setup_ready_days: int = 5        # 形态就绪后的等待窗口 (5日)
    ):
        self.ma_50 = ma_50
        self.ma_120 = ma_120
        self.ma_150 = ma_150
        self.ma_200 = ma_200
        self.contraction_window = contraction_window
        self.max_t1_depth = max_t1_depth
        self.last_t_depth = last_t_depth
        self.vol_exhaust_ratio = vol_exhaust_ratio
        self.hard_stop_loss = hard_stop_loss
        self.time_stop_days = time_stop_days
        self.min_profit_3d = min_profit_3d
        self.setup_ready_days = setup_ready_days

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 VCP 核心指标"""
        df = df.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)

        # 1. 均线系统 (Stage 2)
        df['ma50'] = df['close'].rolling(self.ma_50).mean()
        df['ma120'] = df['close'].rolling(self.ma_120).mean()
        df['ma150'] = df['close'].rolling(self.ma_150).mean()
        df['ma200'] = df['close'].rolling(self.ma_200).mean()

        # 2. VCP 辅助指标
        # 溯源高点
        df['base_high'] = df['high'].rolling(self.contraction_window).max()
        # 波动率 (10日价格区间)
        df['rolling_range_pct'] = (df['high'].rolling(10).max() - df['low'].rolling(10).min()) / df['low'].rolling(10).min()
        
        # 3. 成交量均线
        df['vol_ma50'] = df['vol'].rolling(50).mean()
        df['vol_ma20'] = df['vol'].rolling(20).mean()

        # 4. MA200 斜率 (20日变化率)
        df['ma200_slope'] = (df['ma200'] - df['ma200'].shift(20)) / df['ma200'].shift(20)

        return df

    def _check_stage2(self, row: pd.Series) -> bool:
        """检查是否处于 Minervini 第二阶段上涨趋势"""
        if pd.isna(row['ma200']): return False
        
        cond1 = row['close'] > row['ma200']
        cond2 = row['close'] > row['ma150']
        cond3 = row['ma150'] > row['ma200']
        cond4 = row['ma50'] > row['ma150']
        
        # MA200 必须处于上升趋势 (过去20天涨幅 > 0)
        cond_slope = row['ma200_slope'] > 0 if pd.notna(row['ma200_slope']) else False
        
        return cond1 and cond2 and cond3 and cond4 and cond_slope

    def _detect_vcp_shape(self, row: pd.Series, df_slice: pd.DataFrame) -> Tuple[bool, str, Optional[float]]:
        """检测收缩形态并寻找枢轴点 Pivot"""
        if pd.isna(row['base_high']): return False, "数据不足", None
        
        # 核心收缩逻辑：
        # 这里采用简化规则：
        # 1. 当前股价距离 Base High 不远 (15% 以内)
        # 2. 最近 10 天的波动率已经收缩到阈值 (8% 左右)
        # 3. 成交量相比 MA50 显著萎缩
        
        dist_from_high = (row['base_high'] - row['close']) / row['base_high']
        if dist_from_high > 0.25:
            return False, "距离高点太远", None
        
        if row['rolling_range_pct'] > self.last_t_depth:
            return False, f"波幅未收缩({row['rolling_range_pct']:.2%})", None
            
        if row['vol'] > row['vol_ma50'] * self.vol_exhaust_ratio:
            return False, "地量不明显", None
            
        # 枢轴点 (Pivot) 定义为【之前】20 天的高点 (排除当日)
        pivot = df_slice['high'].iloc[:-1].tail(20).max()
        
        return True, "符合VCP收缩", pivot

    def run(
        self, 
        df: pd.DataFrame, 
        initial_capital: float = 1000000.0,
        debug: bool = True
    ) -> BacktestResult:
        """运行 VCP 策略回测"""
        df = self._calculate_indicators(df)
        
        cash = initial_capital
        position = Position()
        trades: List[Trade] = []
        equity_curve: List[Tuple[date, float]] = []
        signals: List[Signal] = []
        
        # 状态跟踪
        days_in_trade = 0
        setup_ready_counter = 0
        pending_pivot = None
        pending_reason = ""
        
        warmup = self.ma_200
        for i in range(warmup, len(df)):
            row = df.iloc[i]
            current_date = row['trade_date'].date()
            close_price = row['close']
            
            # ============ 持仓中 ============
            if position.is_long:
                days_in_trade += 1
                
                # 1. 检查硬止损
                pnl_pct = (close_price - position.entry_price) / position.entry_price * 100
                sell_triggered = False
                sell_reason = ""
                
                if pnl_pct <= self.hard_stop_loss:
                    sell_triggered = True
                    sell_reason = f"硬止损 {pnl_pct:.1f}%"
                
                # 2. 检查 VCP 时间止损 (A股特技：突破不涨即平仓)
                elif days_in_trade == self.time_stop_days:
                    if pnl_pct < self.min_profit_3d:
                        sell_triggered = True
                        sell_reason = f"时间止损({days_in_trade}日涨幅{pnl_pct:.1f}%不足)"
                
                # 3. 破位止损 (跌破 MA50)
                elif close_price < row['ma50']:
                    sell_triggered = True
                    sell_reason = "跌破MA50基准线"

                if sell_triggered:
                    trade = Trade(
                        entry_date=position.entry_date,
                        entry_price=position.entry_price,
                        quantity=position.quantity,
                        stop_loss_price=position.entry_price * (1 + self.hard_stop_loss/100)
                    )
                    trade.close(current_date, close_price, sell_reason)
                    trades.append(trade)
                    cash += (position.quantity * close_price)
                    equity_curve.append((current_date, cash))
                    if debug:
                        print(f"[SELL] {current_date} @ {close_price:.2f} | PnL: {trade.pnl_pct:+.1f}% | {sell_reason}")
                    position = Position()
                    signals.append(Signal(current_date, 'sell', close_price, sell_reason))
                    days_in_trade = 0
                else:
                    equity_curve.append((current_date, cash + position.quantity * close_price))

            # ============ 空仓中 ============
            else:
                equity_curve.append((current_date, cash))
                
                # 1. 检测 Setup (收缩形态)
                is_ready_now, shape_reason, pivot = self._detect_vcp_shape(row, df.iloc[i-60:i+1])
                
                if is_ready_now:
                    setup_ready_counter = self.setup_ready_days
                    pending_pivot = pivot
                    pending_reason = shape_reason
                    if debug:
                        print(f"🔍 [VCP Setup] {current_date} | Pivot: {pivot:.2f} | 进入{self.setup_ready_days}日观察期")

                # 2. 在就绪窗口内检查 Trigger (突破)
                if setup_ready_counter > 0 and pending_pivot:
                    setup_ready_counter -= 1
                    
                    # 检查 Stage 2 趋势 (必须满足)
                    if self._check_stage2(row):
                        # 突破判定 (Pivot 排除当日后的收盘价突破)
                        if close_price > pending_pivot:
                            # 确认量能
                            if row['vol'] > row['vol_ma20'] * 1.5:
                                buy_price = close_price # 模拟尾盘/打板入场
                                quantity = int(cash / buy_price / 100) * 100
                                if quantity > 0:
                                    cash -= quantity * buy_price
                                    position = Position(
                                        is_long=True,
                                        entry_date=current_date,
                                        entry_price=buy_price,
                                        quantity=quantity,
                                        signal_low=row['low']
                                    )
                                    if debug:
                                        print(f"🚀 [VCP BUY] {current_date} @ {buy_price:.2f} | Breakout Pivot: {pending_pivot:.2f} | (窗口剩余{setup_ready_counter}天)")
                                    signals.append(Signal(current_date, 'buy', buy_price, f"VCP突破; {pending_reason}"))
                                    days_in_trade = 0
                                    setup_ready_counter = 0 # 重置
                                    pending_pivot = None
                            elif debug and i % 5 == 0:
                                print(f"DEBUG: {current_date} | Price OK, but Vol not confirmed ({row['vol']:.0f} < {row['vol_ma20']*1.5:.0f})")
                    else:
                        if debug and i % 20 == 0:
                            print(f"DEBUG: {current_date} | Setup Valid, but Stage 2 Filtered")

        # ... (Metrics calculation same as Momentum strategy) ...
        result = self._calculate_metrics(trades, equity_curve, initial_capital)
        result.signals = signals
        return result

    def _calculate_metrics(
        self,
        trades: List[Trade],
        equity_curve: List[Tuple[date, float]],
        initial_capital: float
    ) -> BacktestResult:
        """计算性能指标"""
        result = BacktestResult()
        result.trades = trades
        result.equity_curve = equity_curve
        
        if not trades:
            return result
        
        result.total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        result.winning_trades = len(winning_trades)
        result.losing_trades = len(losing_trades)
        
        result.win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        result.avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        result.avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        if result.avg_loss != 0:
            result.profit_loss_ratio = abs(result.avg_win / result.avg_loss)
        else:
            result.profit_loss_ratio = float('inf') if winning_trades else 0
        
        final_value = equity_curve[-1][1] if equity_curve else initial_capital
        result.total_return = (final_value - initial_capital) / initial_capital * 100
        
        if len(equity_curve) >= 2:
            years = (equity_curve[-1][0] - equity_curve[0][0]).days / 365.25
            if years > 0 and final_value > 0 and initial_capital > 0:
                result.annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100
        
        peak = initial_capital
        max_dd = 0
        max_dd_pct = 0
        for dt, value in equity_curve:
            if value > peak:
                peak = value
            dd = peak - value
            dd_pct = dd / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        result.max_drawdown = max_dd
        result.max_drawdown_pct = max_dd_pct
        
        return result
