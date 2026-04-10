
"""
A股本地化 VCP (Volatility Contraction Pattern) 策略
==================================================

核心逻辑：
1. Stage 2 趋势过滤：股价、均线呈多头排列，年线向上。
2. 波动收缩 (VCP) 检测：寻找价格波幅逐渐减小的形态。
3. 地量确认：突破前夕成交量极度萎缩。
4. A股本地化：尾盘入场确认、时间止损（3日不涨即撤）。
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from datetime import date
from .base import BaseStrategy, Signal, Trade, Position, BacktestResult

logger = logging.getLogger(__name__)


class VCPStrategy(BaseStrategy):
    def __init__(
        self,
        ma_50: int = 50,
        ma_120: int = 120,
        ma_150: int = 150,
        ma_200: int = 200,
        contraction_window: int = 120,   # 形态溯源窗口
        max_t1_depth: float = 0.50,      # 第一波最大回调深度 (50%)
        last_t_depth: float = 0.10,      # A股最后一次波幅收缩要求 (放宽至10%)
        vol_exhaust_ratio: float = 0.50, # "地量"要求：成交量 < 近期均量的 1/2
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

        # 策略内部状态
        self._days_in_trade = 0
        self._setup_ready_counter = 0
        self._pending_pivot = None
        self._pending_reason = ""

    # ------------------------------------------------------------------
    # BaseStrategy 接口实现
    # ------------------------------------------------------------------

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
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
        df['base_high'] = df['high'].rolling(self.contraction_window).max()
        df['rolling_range_pct'] = (df['high'].rolling(10).max() - df['low'].rolling(10).min()) / df['low'].rolling(10).min()
        
        # 3. 成交量均线
        df['vol_ma50'] = df['vol'].rolling(50).mean()
        df['vol_ma20'] = df['vol'].rolling(20).mean()

        # 4. MA200 斜率
        df['ma200_slope'] = (df['ma200'] - df['ma200'].shift(20)) / df['ma200'].shift(20)

        return df

    def get_warmup_period(self) -> int:
        return self.ma_200

    def reset_state(self):
        """重置策略内部状态"""
        self._days_in_trade = 0
        self._setup_ready_counter = 0
        self._pending_pivot = None
        self._pending_reason = ""

    def on_buy(self, current_date: date):
        """买入后重置状态"""
        self._days_in_trade = 0
        self._setup_ready_counter = 0
        self._pending_pivot = None

    def on_sell(self, current_date: date):
        """卖出后重置持仓天数"""
        self._days_in_trade = 0

    def check_buy(self, row: pd.Series, df: pd.DataFrame, i: int, **kwargs) -> Tuple[bool, Optional[float], str]:
        """检查 VCP 买入条件"""
        current_date = row['trade_date'].date() if hasattr(row['trade_date'], 'date') else row['trade_date']
        close_price = row['close']

        # 检测 VCP 形态是否就绪
        is_ready_now, shape_reason, pivot = self._detect_vcp_shape(row, df.iloc[max(0, i-60):i+1])

        if is_ready_now:
            self._setup_ready_counter = self.setup_ready_days
            self._pending_pivot = pivot
            self._pending_reason = shape_reason
            logger.debug("🔍 [VCP Setup] %s | Pivot: %.2f | 进入%d日观察期",
                         current_date, pivot, self.setup_ready_days)

        if self._setup_ready_counter > 0 and self._pending_pivot:
            self._setup_ready_counter -= 1
            if self._check_stage2(row) and close_price > self._pending_pivot:
                if row['vol'] > row['vol_ma20'] * 1.5:
                    buy_reason = f"VCP突破; {self._pending_reason}"
                    return True, close_price, buy_reason

        return False, None, ""

    def check_sell(self, row: pd.Series, position: Position, **kwargs) -> Tuple[bool, str]:
        """检查 VCP 卖出条件"""
        self._days_in_trade += 1
        close_price = row['close']
        pnl_pct = (close_price - position.entry_price) / position.entry_price * 100

        if pnl_pct <= self.hard_stop_loss:
            return True, f"硬止损 {pnl_pct:.1f}%"

        if self._days_in_trade == self.time_stop_days:
            if pnl_pct < self.min_profit_3d:
                return True, f"时间止损({self._days_in_trade}日涨幅{pnl_pct:.1f}%不足)"

        if close_price < row['ma50']:
            return True, "跌破MA50基准线"

        return False, ""

    # ------------------------------------------------------------------
    # VCP 形态检测内部逻辑 (保持不变)
    # ------------------------------------------------------------------

    def _check_stage2(self, row: pd.Series) -> bool:
        """检查是否处于 Minervini 第二阶段上涨趋势"""
        if pd.isna(row['ma200']): return False
        
        cond1 = row['close'] > row['ma200']
        cond2 = row['close'] > row['ma150']
        cond3 = row['ma150'] > row['ma200']
        cond4 = row['ma50'] > row['ma150']
        
        cond_slope = row['ma200_slope'] > 0 if pd.notna(row['ma200_slope']) else False
        
        return cond1 and cond2 and cond3 and cond4 and cond_slope

    def _detect_vcp_shape(self, row: pd.Series, df_slice: pd.DataFrame) -> Tuple[bool, str, Optional[float]]:
        """检测收缩形态并寻找枢轴点 Pivot"""
        if pd.isna(row['base_high']): return False, "数据不足", None
        
        dist_from_high = (row['base_high'] - row['close']) / row['base_high']
        if dist_from_high > 0.25:
            return False, "距离高点太远", None
        
        if row['rolling_range_pct'] > self.last_t_depth:
            return False, f"波幅未收缩({row['rolling_range_pct']:.2%})", None
            
        if row['vol'] > row['vol_ma50'] * self.vol_exhaust_ratio:
            return False, "地量不明显", None
            
        pivot = df_slice['high'].iloc[:-1].tail(20).max()
        return True, "符合VCP收缩", pivot
