"""
stock_personality.py — 股性分析核心编排器
"""
import datetime
from typing import Optional
import pandas as pd

from src.data.reader.stock_reader import StockReader
from .personality_config import (
    PersonalityConfig, CATEGORY_DEFS,
    is_excluded_stock, get_board_config,
)
from .personality_metrics import (
    PersonalityResult, ClassificationDetail,
)
from ._temperament import analyze_temperament
from ._habit import analyze_habit
from ._volume_profile import analyze_volume_profile
from ._market_position import analyze_market_position


class StockPersonalityAnalyzer:
    """股性分析核心类"""

    def __init__(self, reader: StockReader = None, config: PersonalityConfig = None):
        self.reader = reader or StockReader()
        self.config = config or PersonalityConfig()
        self._stock_info_cache = {}

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def analyze(self, ts_code: str) -> Optional[PersonalityResult]:
        """分析单只股票的股性。返回 None 表示被剔除。"""
        info = self._get_stock_info(ts_code)
        if info is None:
            print(f"[跳过] {ts_code}: 未找到股票信息")
            return None

        name, market, industry = info['name'], info['market'], info['industry']

        if is_excluded_stock(name, market):
            print(f"[剔除] {ts_code} ({name}): ST股/北交所，不参与分析")
            return None

        board_cfg = get_board_config(market)
        cfg = self.config

        # 计算日期范围
        end_date = self.reader.get_latest_date(ts_code)
        if end_date is None:
            print(f"[跳过] {ts_code}: 无日线数据")
            return None
        start_date = end_date - datetime.timedelta(days=int(cfg.lookback_days * 1.5))

        # 拉取数据
        df_daily = self.reader.get_daily(ts_code, start_date=start_date.strftime('%Y%m%d'),
                                          end_date=end_date.strftime('%Y%m%d'))
        if df_daily.empty or len(df_daily) < 60:
            print(f"[跳过] {ts_code}: 日线数据不足")
            return None

        # 截取到 lookback_days
        if len(df_daily) > cfg.lookback_days:
            df_daily = df_daily.iloc[-cfg.lookback_days:]

        df_basic = self.reader.get_daily_basic(
            ts_code,
            start_date=df_daily.iloc[0]['trade_date'].strftime('%Y%m%d') if hasattr(df_daily.iloc[0]['trade_date'], 'strftime') else str(df_daily.iloc[0]['trade_date']),
            end_date=end_date.strftime('%Y%m%d'),
        )

        df_index = self.reader.get_index_daily(
            board_cfg['benchmark_code'],
            start_date=df_daily.iloc[0]['trade_date'].strftime('%Y%m%d') if hasattr(df_daily.iloc[0]['trade_date'], 'strftime') else str(df_daily.iloc[0]['trade_date']),
            end_date=end_date.strftime('%Y%m%d'),
        )

        # 四维度分析
        temperament = analyze_temperament(df_daily, df_basic, board_cfg['limit_up_pct'], cfg)
        habit = analyze_habit(df_daily, cfg)
        volume = analyze_volume_profile(df_daily, df_basic, cfg)
        position = analyze_market_position(df_daily, df_index,
                                           board_cfg['benchmark_name'],
                                           board_cfg['benchmark_code'], cfg)

        # 综合归类
        category, confidence, secondary = self._classify(temperament, habit, volume, position)
        cat_def = CATEGORY_DEFS[category]

        # 构建K线数据（供HTML报告）
        kline_data = []
        for _, row in df_daily.iterrows():
            d = row['trade_date']
            ds = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)
            kline_data.append([ds, row['open'], row['close'], row['low'], row['high']])

        limit_up_dates = [e.date for e in (temperament.consecutive_events if hasattr(temperament, '_limit_events') else [])]
        # 简单用涨停mask重建
        limit_up_dates = []
        fail_board_dates = []
        for _, row in df_daily.iterrows():
            d = row['trade_date']
            ds = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)
            if row['pct_chg'] >= board_cfg['limit_up_pct']:
                limit_up_dates.append(ds)
            elif row['high'] >= row['pre_close'] * (1 + board_cfg['limit_up_pct'] / 100):
                fail_board_dates.append(ds)

        # 真命天子均线数据
        best_ma_values = []
        if habit.best_ma > 0 and len(df_daily) >= habit.best_ma:
            ma_series = df_daily['close'].rolling(habit.best_ma).mean()
            for i, (_, row) in enumerate(df_daily.iterrows()):
                if pd.notna(ma_series.iloc[i]):
                    d = row['trade_date']
                    ds = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)
                    best_ma_values.append([ds, round(float(ma_series.iloc[i]), 2)])

        period_start = df_daily.iloc[0]['trade_date']
        period_end = df_daily.iloc[-1]['trade_date']
        ps = period_start.strftime('%Y-%m-%d') if hasattr(period_start, 'strftime') else str(period_start)
        pe = period_end.strftime('%Y-%m-%d') if hasattr(period_end, 'strftime') else str(period_end)

        result = PersonalityResult(
            ts_code=ts_code, name=name, market=market, industry=industry or "",
            analysis_period=f"{ps} ~ {pe}",
            temperament=temperament, habit=habit,
            volume_profile=volume, market_position=position,
            category=category, category_name=cat_def['name'],
            category_emoji=cat_def['emoji'], tactic=cat_def['tactic'],
            confidence=confidence, secondary_traits=secondary,
            scores={
                "temperament": temperament.score,
                "habit": habit.score,
                "volume_profile": volume.score,
                "market_position": position.score,
            },
            kline_data=kline_data,
            limit_up_dates=limit_up_dates,
            fail_board_dates=fail_board_dates,
            best_ma_values=best_ma_values,
        )

        return result

    def analyze_batch(self, ts_codes: list) -> list:
        """批量分析"""
        results = []
        for i, code in enumerate(ts_codes):
            print(f"[{i+1}/{len(ts_codes)}] 分析 {code} ...")
            r = self.analyze(code)
            if r:
                results.append(r)
        return results

    def analyze_industry(self, industry: str) -> list:
        """按行业分析"""
        stocks = self.reader.get_stock_list(list_status='L')
        codes = stocks[stocks['industry'] == industry]['ts_code'].tolist()
        print(f"行业「{industry}」共 {len(codes)} 只股票")
        return self.analyze_batch(codes)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_stock_info(self, ts_code: str) -> Optional[dict]:
        if ts_code not in self._stock_info_cache:
            df = self.reader.get_stock_list(list_status=None)
            row = df[df['ts_code'] == ts_code]
            if row.empty:
                self._stock_info_cache[ts_code] = None
            else:
                r = row.iloc[0]
                self._stock_info_cache[ts_code] = {
                    'name': r['name'], 'market': r.get('market', '主板'),
                    'industry': r.get('industry', ''),
                }
        return self._stock_info_cache[ts_code]

    def _classify(self, temp, habit, vol, pos) -> tuple:
        """综合归类 + 置信度"""
        scores = {
            "B": self._score_category_b(temp, vol),
            "D": self._score_category_d(temp, vol, pos),
            "C": self._score_category_c(temp, habit),
            "A": self._score_category_a(habit, vol, pos),
        }

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best = ranked[0]
        total = sum(v for _, v in ranked)

        confidence = round(best[1] / total * 100, 1) if total > 0 else 25.0
        secondary = [
            ClassificationDetail(
                category=cat, confidence=round(sc / total * 100, 1),
                category_name=CATEGORY_DEFS[cat]['name'],
            )
            for cat, sc in ranked[1:] if sc > 0
        ]

        return best[0], confidence, secondary

    def _score_category_b(self, temp, vol) -> float:
        """妖股/龙头评分"""
        s = 0
        if temp.has_monster_gene:
            s += 30
        s += min(temp.limit_up_frequency * 5, 25)
        if vol.capital_type == "游资主导":
            s += 15
        if temp.avg_amplitude > 5:
            s += 10
        s += temp.limit_up_quality_score * 0.1
        return max(0, s)

    def _score_category_d(self, temp, vol, pos) -> float:
        """僵尸股评分 — 真正的僵尸股是弱势+低活跃，不是机构控盘白马"""
        # 机构控盘+缩量良好的股票不是僵尸股
        if vol.capital_type == "机构控盘" and vol.shrink_quality == "优质缩量":
            return 0
        s = 0
        if temp.avg_amplitude < 2:
            s += 20
        if vol.avg_turnover < 1 and vol.avg_turnover > 0:
            # 仅在非机构控盘时加分
            if vol.capital_type != "机构控盘":
                s += 25
            else:
                s += 5
        elif vol.avg_turnover < 2 and vol.capital_type != "机构控盘":
            s += 15
        if pos.position_type == "弱势":
            s += 25  # 弱势是僵尸股的核心特征
        if temp.limit_up_count == 0 and pos.position_type == "弱势":
            s += 10
        if vol.activity_trend == "股性正在死亡":
            s += 15
        return max(0, s)

    def _score_category_c(self, temp, habit) -> float:
        """渣男股评分"""
        s = 0
        if temp.fail_board_rate > 50:
            s += 25
        elif temp.fail_board_rate > 30:
            s += 15
        if habit.a_kill_count >= 3:
            s += 20
        if habit.best_ma_success_rate < 40:
            s += 10
        if temp.avg_amplitude > 4 and temp.fail_board_rate > 30:
            s += 15
        return max(0, s)

    def _score_category_a(self, habit, vol, pos) -> float:
        """白马股评分"""
        s = 15  # 基础分，白马是默认归类
        if vol.shrink_quality == "优质缩量":
            s += 20
        if vol.capital_type == "机构控盘":
            s += 25  # 机构控盘是白马核心特征
        if habit.trend_type == "阶梯上涨":
            s += 15
        elif habit.trend_type == "混合型":
            s += 5
        if habit.best_ma_success_rate > 60:
            s += 12
        elif habit.best_ma_success_rate > 40:
            s += 5
        if pos.position_type == "龙头":
            s += 10
        elif pos.position_type == "跟随":
            s += 3
        if pos.anti_drop_score > 60:
            s += 5
        return max(0, s)
