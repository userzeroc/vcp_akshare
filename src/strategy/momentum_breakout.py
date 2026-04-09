"""
动量突破策略 (Momentum Breakout Strategy)
==========================================

针对"特变电工(600089.SH)"特性设计的趋势跟随策略：
- 急涨慢跌、长周期洗盘、脉冲式爆发
- 平时绝对空仓，信号出现立刻满仓
- 截断亏损，让利润奔跑

买入规则（三条件共振突破）:
  A. 宏观趋势过滤：收盘价 > 60日均线 (MA60)
  B. 价格爆发信号：当日收盘涨幅 > 5%
  C. 资金异动信号：当日成交量 > 过去20日均量的2倍

卖出规则:
  A. 硬止损：收盘价跌破信号日大阳线最低价 或 亏损达-8%
  B. 移动止盈：收盘价跌破20日均线 (MA20)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import date


@dataclass
class Signal:
    """交易信号"""
    date: date
    signal_type: str  # 'buy', 'sell'
    price: float
    reason: str


@dataclass
class Trade:
    """单笔交易记录"""
    entry_date: date
    entry_price: float
    quantity: int
    stop_loss_price: float
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    
    def close(self, exit_date: date, exit_price: float, reason: str):
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.pnl = (exit_price - self.entry_price) * self.quantity
        self.pnl_pct = (exit_price - self.entry_price) / self.entry_price * 100
        self.exit_reason = reason


@dataclass
class Position:
    """持仓状态"""
    is_long: bool = False
    entry_date: Optional[date] = None
    entry_price: Optional[float] = None
    quantity: int = 0
    signal_low: Optional[float] = None  # 信号日最低价
    highest_price: Optional[float] = None  # 持仓期间最高价


@dataclass
class BacktestResult:
    """回测结果"""
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[date, float]] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    
    # 性能指标
    total_return: float = 0.0
    annualized_return: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_loss_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


class MomentumBreakoutStrategy:
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
        # v3.0 情绪参数
        use_sentiment_exit: bool = True,   # 启用情绪离场机制
        rsi_exhaustion: float = 85.0,      # RSI 狂热阈值
        roc_euphoria: float = 20.0,         # 3日爆发涨幅阈值
        vol_climax_mult: float = 3.0,      # 天量倍数
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
        self.use_sentiment_exit = use_sentiment_exit
        self.rsi_exhaustion = rsi_exhaustion
        self.roc_euphoria = roc_euphoria
        self.vol_climax_mult = vol_climax_mult
    
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
        
        # 计算 ATR (用于追踪止盈，即便是 use_atr_filter 为 False 也需要计算)
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
        
        # v3.0 计算情绪指标
        # 1. RSI(14)
        df['rsi'] = self._calculate_rsi(df['close'], 14)
        # 2. 3日变动率 (ROC3)
        df['roc3'] = df['close'].pct_change(3) * 100
        # 3. 成交量比率
        df['vol_ratio'] = df['vol'] / df['vol_ma20']
        
        return df
    
    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """计算 RSI"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        # 避免除以0
        loss = loss.replace(0, 0.0001)
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
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
        
        # 优化条件 D: 乖离率过滤 (防止涨幅过大后强弩之末)
        if pd.notna(row['bias60']):
            if row['bias60'] > self.bias_threshold:
                return False, f"乖离率过高({row['bias60']:.2f} > {self.bias_threshold})"
            # reasons.append("估值合理")
        
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
        
        if current_price < signal_low:
            return True, f"跌破信号日低点 {signal_low:.2f}"
        
        if pnl_pct <= self.hard_stop_loss:
            return True, f"亏损{pnl_pct:.2f}%达到硬止损"
        
        # 优化条件: ATR 动态追踪止盈 (吊灯止盈)
        if self.use_trailing_stop and position.highest_price and pd.notna(row['atr']):
            trailing_line = position.highest_price - self.atr_multiplier * row['atr']
            if current_price < trailing_line:
                return True, f"触发ATR追踪止盈({current_price:.2f} < {trailing_line:.2f})"
        
        if row['close'] < row['ma20']:
            return True, f"跌破MA20 {row['ma20']:.2f}"
        
        # 优化条件: 情绪护盾 (Euphoria Exit)
        if self.use_sentiment_exit:
            is_euphoric, reason = self._is_euphoric(row)
            if is_euphoric:
                return True, reason
        
        return False, ""
    
    def _is_euphoric(self, row: pd.Series) -> Tuple[bool, str]:
        """检测是否存在非理性繁荣/情绪过热"""
        # 1. RSI 超买极限
        if row['rsi'] > self.rsi_exhaustion:
            return True, f"情绪过热: RSI({row['rsi']:.1f}) > {self.rsi_exhaustion}"
        
        # 2. 垂直加速 (3日急涨)
        if row['roc3'] > self.roc_euphoria:
            return True, f"情绪过热: 3日急涨({row['roc3']:.1f}%) > {self.roc_euphoria}%"
        
        # 3. 高位天量 (Blow-off)
        if row['vol_ratio'] > self.vol_climax_mult and row['bias60'] > 0.3:
            return True, f"情绪过热: 高位天量(倍数:{row['vol_ratio']:.1f})"
            
        return False, ""
    
    def run(
        self, 
        df: pd.DataFrame, 
        initial_capital: float = 1000000.0,
        earnings_dates: Optional[List[str]] = None,
        debug: bool = True
    ) -> BacktestResult:
        """运行回测"""
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
        buy_count = 0
        sell_count = 0
        
        for i in range(warmup, len(df)):
            row = df.iloc[i]
            current_date = row['trade_date'].date() if isinstance(row['trade_date'], pd.Timestamp) else row['trade_date']
            close_price = row['close']
            
            # ============ 持仓中 - 检查卖出 ============
            if position.is_long:
                # 更新持仓期间最高价
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
                    # 修复 Bug: 应该回流总价值（本金 + 盈亏），而不仅仅是 PnL
                    cash += (position.quantity * close_price)
                    # 现金不能为负
                    cash = max(0, cash)
                    # 卖出后equity更新为纯现金
                    equity_curve.append((current_date, cash))
                    sell_count += 1
                    if debug:
                        print(f"[SELL #{sell_count}] {current_date} @ {close_price:.2f} | PnL: {trade.pnl:+.0f} | Cash: {cash:.2f} | Reason: {sell_reason}")
                    position = Position()
                    signals.append(Signal(current_date, 'sell', close_price, sell_reason))
                else:
                    # 持仓中：equity = cash + 持仓市值
                    current_value = cash + position.quantity * close_price
                    equity_curve.append((current_date, current_value))
            
            # ============ 空仓中 - 检查买入 ============
            else:
                # 空仓中：equity = cash
                equity_curve.append((current_date, cash))
                
                if self.avoid_earnings and self.earnings_lead_days > 0:
                    in_blackout = False
                    for j in range(i, min(i + self.earnings_lead_days + 5, len(df))):
                        future_date = df.iloc[j]['trade_date'].date() if isinstance(df.iloc[j]['trade_date'], pd.Timestamp) else df.iloc[j]['trade_date']
                        if future_date in earnings_dates_set:
                            in_blackout = True
                            break
                    if in_blackout:
                        continue
                
                buy_triggered, buy_reason = self._check_buy_conditions(row)
                
                if buy_triggered and i + 1 < len(df):
                    next_row = df.iloc[i + 1]
                    buy_price = next_row['open']
                    buy_date = next_row['trade_date'].date() if isinstance(next_row['trade_date'], pd.Timestamp) else next_row['trade_date']
                    
                    # 关键修复：确保有足够的可用资金
                    available_capital = max(0, cash * self.position_size)
                    quantity = int(available_capital / buy_price / 100) * 100
                    
                    if quantity > 0:
                        cost = quantity * buy_price
                        cash -= cost
                        
                        position = Position(
                            is_long=True,
                            entry_date=buy_date,
                            entry_price=buy_price,
                            quantity=quantity,
                            signal_low=row['low'],
                            highest_price=buy_price
                        )
                        
                        # 买入后立即更新equity_curve：用当天收盘价计算持仓市值
                        # 替换当天刚append的equity记录（用cash）改为持仓总价值
                        current_value = cash + position.quantity * buy_price
                        equity_curve[-1] = (current_date, current_value)  # 替换记录
                        
                        buy_count += 1
                        if debug:
                            print(f"[BUY #{buy_count}] {buy_date} @ {buy_price:.2f} | Stop: {row['low']:.2f} | Reason: {buy_reason}")
                        signals.append(Signal(buy_date, 'buy', buy_price, buy_reason))
            
            # 最后一天强制平仓
            if i == len(df) - 1 and position.is_long:
                trade = Trade(
                    entry_date=position.entry_date,
                    entry_price=position.entry_price,
                    quantity=position.quantity,
                    stop_loss_price=position.signal_low
                )
                trade.close(current_date, close_price, "回测结束强制平仓")
                trades.append(trade)
                # 修复 Bug: 应该回流总价值
                cash += (position.quantity * close_price)
        
        if debug:
            print(f"\n[DEBUG] Total Buys: {buy_count}, Total Sells: {sell_count}, Cash: {cash:.2f}")
        
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


def print_backtest_report(result: BacktestResult, stock_code: str = ""):
    """打印回测报告"""
    final_value = result.equity_curve[-1][1] if result.equity_curve else 1000000.0
    
    print("\n" + "=" * 70)
    print(f"  Momentum Breakout Strategy Backtest Report {stock_code}")
    print("=" * 70)
    
    print(f"\n[ Performance Summary ]")
    print(f"  Initial Capital:      1,000,000.00")
    print(f"  Final Equity:          {final_value:,.2f}")
    print(f"  Total Return:          {result.total_return:.2f}%")
    print(f"  Annualized Return:     {result.annualized_return:.2f}%")
    
    print(f"\n[ Risk Control ]")
    print(f"  Max Drawdown:          {result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")
    
    print(f"\n[ Trading Statistics ]")
    print(f"  Total Trades:          {result.total_trades}")
    print(f"  Winning Trades:        {result.winning_trades} ({result.win_rate:.1f}%)")
    print(f"  Losing Trades:         {result.losing_trades}")
    print(f"  Avg Win:               {result.avg_win:,.2f}")
    print(f"  Avg Loss:              {result.avg_loss:,.2f}")
    print(f"  Profit/Loss Ratio:     {result.profit_loss_ratio:.2f}")
    
    # Strategy evaluation
    print(f"\n[ Strategy Evaluation ]")
    if result.win_rate < 45:
        print(f"  [OK] Win Rate {result.win_rate:.1f}% (Trend strategy = low win rate)")
    else:
        print(f"  [!!] Win Rate {result.win_rate:.1f}% (Check for overfitting)")
    
    if result.profit_loss_ratio >= 2.5:
        print(f"  [OK] P/L Ratio {result.profit_loss_ratio:.2f} (>=2.5 target)")
    else:
        print(f"  [!!] P/L Ratio {result.profit_loss_ratio:.2f} (Below 2.5 target)")
    
    if result.max_drawdown_pct <= 25:
        print(f"  [OK] Max Drawdown {result.max_drawdown_pct:.2f}% (<=25% target)")
    else:
        print(f"  [!!] Max Drawdown {result.max_drawdown_pct:.2f}% (>25% warning)")
    
    if result.total_trades <= 25:
        print(f"  [OK] Trade Frequency {result.total_trades} (Low freq long-wave)")
    else:
        print(f"  [!!] Trade Frequency {result.total_trades} (May be overtrading)")
    
    # Trade details
    if result.trades:
        print(f"\n[ Trade Details ]")
        print("-" * 70)
        print(f"{'Entry Date':<12} {'Entry':>8} {'Exit Date':<12} {'Exit':>8} {'PnL':>12} {'%':>8} {'Reason'}")
        print("-" * 70)
        for t in result.trades:
            entry_str = t.entry_date.strftime('%Y-%m-%d') if hasattr(t.entry_date, 'strftime') else str(t.entry_date)
            exit_str = t.exit_date.strftime('%Y-%m-%d') if t.exit_date and hasattr(t.exit_date, 'strftime') else str(t.exit_date)
            pnl_str = f"{t.pnl:+,.0f}"
            pct_str = f"{t.pnl_pct:+.1f}%"
            reason = t.exit_reason[:20] if t.exit_reason else ""
            print(f"{entry_str:<12} {t.entry_price:>8.2f} {exit_str:<12} {t.exit_price:>8.2f} {pnl_str:>12} {pct_str:>8} {reason}")
        print("-" * 70)
    
    print("=" * 70 + "\n")
