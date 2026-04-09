
"""
动量突破策略 (Momentum Breakout Strategy)
==========================================

针对"特变电工(600089.SH)"特性设计的趋势跟随策略：
- 急涨慢跌、长周期洗盘、脉冲式爆发
- 平时绝对空仓，信号出现立刻满仓
- 截断亏损，让利润奔跑
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from datetime import date
from .base import BaseStrategy, Signal, Trade, Position, BacktestResult

class MomentumBreakoutStrategy(BaseStrategy):
    """
    动量突破策略
    
    核心思想：
    - 平时绝对空仓，只在大级别趋势向好且短线爆量异动时介入
    - 一旦趋势走坏，立刻止损离场
    """
    
    def __init__(
        self,
        ma_long_period: int = 60,
        ma_short_period: int = 20,
        min_pct_chg: float = 5.0,
        vol_multiplier: float = 2.0,
        vol_ma_period: int = 20,
        hard_stop_loss: float = -8.0,
        position_size: float = 1.0,
        use_atr_filter: bool = False,
        atr_period: int = 20,
        atr_threshold_ratio: float = 0.5,
        avoid_earnings: bool = False,
        earnings_lead_days: int = 3,
        # 优化参数
        bias_threshold: float = 0.25,      # 乖离率阈值 (防止追高)
        use_trailing_stop: bool = True,    # 启用动态追踪止盈
        atr_multiplier: float = 2.5,        # ATR 追踪倍数
    ):
        self.ma_long_period = ma_long_period
        self.ma_short_period = ma_short_period
        self.min_pct_chg = min_pct_chg
        self.vol_multiplier = vol_multiplier
        self.vol_ma_period = vol_ma_period
        self.hard_stop_loss = hard_stop_loss
        self.position_size = position_size
        self.use_atr_filter = use_atr_filter
        self.atr_period = atr_period
        self.atr_threshold_ratio = atr_threshold_ratio
        self.avoid_earnings = avoid_earnings
        self.earnings_lead_days = earnings_lead_days
        self.bias_threshold = bias_threshold
        self.use_trailing_stop = use_trailing_stop
        self.atr_multiplier = atr_multiplier
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        df = df.copy()
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)
        
        df['ma60'] = df['close'].rolling(window=self.ma_long_period).mean()
        df['ma20'] = df['close'].rolling(window=self.ma_short_period).mean()
        df['vol_ma20'] = df['vol'].rolling(window=self.vol_ma_period).mean()
        
        # 计算乖离率
        df['bias60'] = (df['close'] - df['ma60']) / df['ma60']
        
        # 计算 ATR (用于追踪止盈)
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                np.abs(df['high'] - df['close'].shift(1)),
                np.abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
        
        if self.use_atr_filter:
            df['atr_ratio'] = df['atr'] / df['atr'].rolling(window=self.atr_period).mean()
        
        return df
    
    def _check_buy_conditions(self, row: pd.Series) -> Tuple[bool, str]:
        """检查买入条件"""
        reasons = []
        
        cond_a = row['close'] > row['ma60']
        if not cond_a:
            return False, "条件A未满足"
        reasons.append("MA60多头")
        
        cond_b = row['pct_chg'] > self.min_pct_chg
        if not cond_b:
            return False, f"涨幅{row['pct_chg']:.2f}% < {self.min_pct_chg}%"
        reasons.append(f"涨幅{row['pct_chg']:.2f}%")
        
        cond_c = row['vol'] > row['vol_ma20'] * self.vol_multiplier
        if not cond_c:
            return False, "量能不足"
        reasons.append("倍量突破")
        
        if pd.notna(row['bias60']):
            if row['bias60'] > self.bias_threshold:
                return False, f"乖离率过高({row['bias60']:.2f} > {self.bias_threshold})"
        
        if self.use_atr_filter and pd.notna(row.get('atr_ratio')):
            if row['atr_ratio'] >= self.atr_threshold_ratio:
                return False, "ATR未处于低位"
            reasons.append("低波动横盘")
        
        return True, "; ".join(reasons)
    
    def _check_sell_conditions(self, row: pd.Series, position: Position) -> Tuple[bool, str]:
        """检查卖出条件"""
        current_price = row['close']
        entry_price = position.entry_price
        signal_low = position.signal_low
        pnl_pct = (current_price - entry_price) / entry_price * 100
        
        if signal_low and current_price < signal_low:
            return True, f"跌破信号日低点 {signal_low:.2f}"
        
        if pnl_pct <= self.hard_stop_loss:
            return True, f"亏损{pnl_pct:.2f}%达到硬止损"
        
        if self.use_trailing_stop and position.highest_price and pd.notna(row['atr']):
            trailing_line = position.highest_price - self.atr_multiplier * row['atr']
            if current_price < trailing_line:
                return True, f"触发ATR追踪止盈({current_price:.2f} < {trailing_line:.2f})"
        
        if row['close'] < row['ma20']:
            return True, f"跌破MA20 {row['ma20']:.2f}"
        
        return False, ""
    
    def run(
        self, 
        df: pd.DataFrame, 
        initial_capital: float = 1000000.0,
        earnings_dates: Optional[List[str]] = None,
        debug: bool = True
    ) -> BacktestResult:
        """运行回测流程"""
        df = self._calculate_indicators(df)
        
        cash = initial_capital
        position = Position()
        trades: List[Trade] = []
        equity_curve: List[Tuple[date, float]] = []
        signals: List[Signal] = []
        
        earnings_dates_set = set()
        if earnings_dates:
            earnings_dates_set = {pd.to_datetime(d).date() for d in earnings_dates}
        
        warmup = max(self.ma_long_period, self.vol_ma_period)
        
        for i in range(warmup, len(df)):
            row = df.iloc[i]
            # 统一日期格式为 datetime.date
            current_date = row['trade_date'].date() if hasattr(row['trade_date'], 'date') else row['trade_date']
            close_price = row['close']
            
            # ============ 持仓中 ============
            if position.is_long:
                if close_price > position.highest_price:
                    position.highest_price = close_price
                
                sell_triggered, sell_reason = self._check_sell_conditions(row, position)
                
                if self.avoid_earnings and current_date in earnings_dates_set:
                    sell_triggered = True
                    sell_reason = f"规避财报"
                
                if sell_triggered:
                    trade = Trade(
                        entry_date=position.entry_date,
                        entry_price=position.entry_price,
                        quantity=position.quantity,
                        stop_loss_price=position.signal_low
                    )
                    trade.close(current_date, close_price, sell_reason)
                    trades.append(trade)
                    cash += (position.quantity * close_price)
                    equity_curve.append((current_date, cash))
                    if debug:
                        print(f"[SELL] {current_date} @ {close_price:.2f} | PnL: {trade.pnl_pct:+.1f}% | Reason: {sell_reason}")
                    position = Position()
                    signals.append(Signal(current_date, 'sell', close_price, sell_reason))
                else:
                    equity_curve.append((current_date, cash + position.quantity * close_price))
            
            # ============ 空仓中 ============
            else:
                equity_curve.append((current_date, cash))
                
                # 规避财报黑名单期
                if self.avoid_earnings and self.earnings_lead_days > 0:
                    in_blackout = False
                    for j in range(i, min(i + self.earnings_lead_days, len(df))):
                        future_date = df.iloc[j]['trade_date'].date() if hasattr(df.iloc[j]['trade_date'], 'date') else df.iloc[j]['trade_date']
                        if future_date in earnings_dates_set:
                            in_blackout = True
                            break
                    if in_blackout: continue
                
                buy_triggered, buy_reason = self._check_buy_conditions(row)
                
                if buy_triggered and i + 1 < len(df):
                    next_row = df.iloc[i + 1]
                    buy_price = next_row['open']
                    buy_date = next_row['trade_date'].date() if hasattr(next_row['trade_date'], 'date') else next_row['trade_date']
                    
                    quantity = int(cash * self.position_size / buy_price / 100) * 100
                    if quantity > 0:
                        cash -= quantity * buy_price
                        position = Position(
                            is_long=True,
                            entry_date=buy_date,
                            entry_price=buy_price,
                            quantity=quantity,
                            signal_low=row['low'],
                            highest_price=buy_price
                        )
                        # 修正买入当日的权益曲线
                        equity_curve[-1] = (current_date, cash + quantity * buy_price)
                        if debug:
                            print(f"[BUY] {buy_date} @ {buy_price:.2f} | Reason: {buy_reason}")
                        signals.append(Signal(buy_date, 'buy', buy_price, buy_reason))
            
            # 最后一天平仓
            if i == len(df) - 1 and position.is_long:
                trade = Trade(position.entry_date, position.entry_price, position.quantity, position.signal_low)
                trade.close(current_date, close_price, "回测结束强制平仓")
                trades.append(trade)
                cash += (position.quantity * close_price)
                equity_curve[-1] = (current_date, cash)

        result = self._calculate_metrics(trades, equity_curve, initial_capital)
        result.signals = signals
        return result

def print_backtest_report(result: BacktestResult, stock_code: str = ""):
    """保持向后兼容的打印函数"""
    temp_strategy = MomentumBreakoutStrategy()
    temp_strategy.print_report(result, stock_code)
