"""维度一：脾气 —— 波动率与涨停基因"""
import numpy as np
import pandas as pd
from .personality_metrics import TemperamentMetrics, LimitUpEvent, ConsecutiveLimitEvent
from .personality_config import PersonalityConfig, compute_decay_weights


def analyze_temperament(
    df: pd.DataFrame,
    df_basic: pd.DataFrame,
    limit_up_pct: float,
    config: PersonalityConfig,
) -> TemperamentMetrics:
    """
    分析股票脾气维度。
    df: 日线数据 (trade_date, open, high, low, close, pre_close, pct_chg, vol)
    df_basic: 每日指标 (trade_date, turnover_rate) — 可能为空
    """
    m = TemperamentMetrics()
    if df.empty:
        return m

    n = len(df)
    weights = compute_decay_weights(n, config)

    # 合并换手率
    if not df_basic.empty and 'turnover_rate' in df_basic.columns:
        tr_map = dict(zip(df_basic['trade_date'], df_basic['turnover_rate']))
    else:
        tr_map = {}

    # ── 涨停检测 ──
    limit_up_mask = df['pct_chg'] >= limit_up_pct
    limit_up_indices = df.index[limit_up_mask].tolist()

    limit_events = []
    for idx in limit_up_indices:
        row = df.loc[idx]
        tr = tr_map.get(row['trade_date'])
        quality = _classify_limit_quality(row, tr)
        limit_events.append(LimitUpEvent(
            date=str(row['trade_date']),
            pct_chg=round(row['pct_chg'], 2),
            turnover_rate=round(tr, 2) if tr else None,
            quality=quality,
        ))

    m.limit_up_count = len(limit_events)
    years = n / 250.0
    m.limit_up_frequency = round(m.limit_up_count / years, 2) if years > 0 else 0

    # 涨停质量统计
    m.quality_big_volume_count = sum(1 for e in limit_events if e.quality == "放量首板")
    m.quality_no_volume_count = sum(1 for e in limit_events if e.quality == "缩量一字板")
    m.quality_late_count = sum(1 for e in limit_events if e.quality == "尾盘偷袭板")

    if m.limit_up_count > 0:
        m.limit_up_quality_score = round(
            (m.quality_big_volume_count * 100 + (m.limit_up_count - m.quality_no_volume_count - m.quality_late_count) * 60
             + m.quality_late_count * 30 + m.quality_no_volume_count * 10) / m.limit_up_count, 1
        )

    # ── 连板检测 ──
    consecutive_events = _detect_consecutive_limits(df, limit_up_mask)
    m.consecutive_events = consecutive_events
    m.max_consecutive_limit = max((e.count for e in consecutive_events), default=0)
    m.has_monster_gene = m.max_consecutive_limit >= 2

    # ── 振幅 ──
    amplitude = ((df['high'] - df['low']) / df['pre_close'].replace(0, np.nan) * 100).dropna()
    if len(amplitude) > 0:
        weighted_amp = amplitude.values * weights[:len(amplitude)]
        w_sum = weights[:len(amplitude)].sum()
        m.avg_amplitude = round(weighted_amp.sum() / w_sum, 2) if w_sum > 0 else 0
        m.median_amplitude = round(float(np.median(amplitude)), 2)
        m.amplitude_p90 = round(float(np.percentile(amplitude, 90)), 2)

    # ── 炸板 ──
    touch_mask = df['high'] >= df['pre_close'] * (1 + limit_up_pct / 100)
    m.touch_limit_count = int(touch_mask.sum())
    if m.touch_limit_count > 0:
        fail_mask = touch_mask & (df['close'] < df['high'] * config.fail_board_close_ratio)
        m.fail_board_count = int(fail_mask.sum())
        m.fail_board_rate = round(m.fail_board_count / m.touch_limit_count * 100, 1)

    # ── 评分 ──
    m.score = _score_temperament(m)
    m.diagnosis = _diagnose_temperament(m)

    return m


def _classify_limit_quality(row, turnover_rate) -> str:
    """涨停质量分层"""
    if turnover_rate is not None:
        if turnover_rate < 2.0:
            return "缩量一字板"
        if turnover_rate > 10.0:
            return "放量首板"
    # 简单判断是否一字板（开盘=收盘=最高）
    if row['open'] == row['close'] == row['high']:
        return "缩量一字板"
    return "普通涨停"


def _detect_consecutive_limits(df: pd.DataFrame, mask: pd.Series) -> list:
    """检测连板事件"""
    events = []
    streak_start = None
    streak_count = 0

    for i, is_limit in enumerate(mask):
        if is_limit:
            if streak_start is None:
                streak_start = i
            streak_count += 1
        else:
            if streak_count >= 2:
                events.append(ConsecutiveLimitEvent(
                    start_date=str(df.iloc[streak_start]['trade_date']),
                    end_date=str(df.iloc[i - 1]['trade_date']),
                    count=streak_count,
                ))
            streak_start = None
            streak_count = 0

    if streak_count >= 2:
        events.append(ConsecutiveLimitEvent(
            start_date=str(df.iloc[streak_start]['trade_date']),
            end_date=str(df.iloc[len(df) - 1]['trade_date']),
            count=streak_count,
        ))
    return events


def _score_temperament(m: TemperamentMetrics) -> float:
    s = 50.0
    s += min(m.limit_up_frequency * 5, 20)
    s += min(m.max_consecutive_limit * 8, 16)
    if m.avg_amplitude > 5:
        s += 10
    elif m.avg_amplitude < 2:
        s -= 15
    if m.fail_board_rate > 50:
        s -= 10
    s += m.limit_up_quality_score * 0.04
    return round(max(0, min(100, s)), 1)


def _diagnose_temperament(m: TemperamentMetrics) -> str:
    parts = []
    if m.has_monster_gene:
        parts.append(f"具备妖股基因：历史最高{m.max_consecutive_limit}连板，涨停{m.limit_up_count}次（{m.limit_up_frequency}次/年）")
    elif m.limit_up_count > 0:
        parts.append(f"有一定爆发力：涨停{m.limit_up_count}次（{m.limit_up_frequency}次/年），但无连板记录")
    else:
        parts.append("无涨停记录，爆发力极弱")

    if m.avg_amplitude > 5:
        parts.append(f"股性极活，日均振幅{m.avg_amplitude}%，适合做T")
    elif m.avg_amplitude < 2:
        parts.append(f"股性偏死，日均振幅仅{m.avg_amplitude}%")
    else:
        parts.append(f"振幅适中，日均{m.avg_amplitude}%")

    if m.fail_board_rate > 50:
        parts.append(f"炸板率高达{m.fail_board_rate}%，典型渣男股，不宜打板")
    elif m.touch_limit_count > 0:
        parts.append(f"炸板率{m.fail_board_rate}%，封板能力尚可")

    return "；".join(parts) + "。"
