"""维度三：饭量 —— 量价配合度"""
import numpy as np
import pandas as pd
from .personality_metrics import VolumeProfileMetrics
from .personality_config import PersonalityConfig, compute_decay_weights


def analyze_volume_profile(
    df: pd.DataFrame,
    df_basic: pd.DataFrame,
    config: PersonalityConfig,
) -> VolumeProfileMetrics:
    """
    分析量价配合度维度。
    df: 日线数据 (trade_date, pct_chg, vol)
    df_basic: 每日指标 (trade_date, turnover_rate) — 可能为空
    """
    m = VolumeProfileMetrics()
    if df.empty:
        return m

    n = len(df)

    # ── 换手率分析 ──
    if not df_basic.empty and 'turnover_rate' in df_basic.columns:
        tr = df_basic['turnover_rate'].dropna()
        if len(tr) > 0:
            m.max_turnover = round(float(tr.max()), 2)
            m.min_turnover = round(float(tr.min()), 2)
            m.avg_turnover = round(float(tr.mean()), 2)
            m.high_turnover_days = int((tr > config.high_turnover_threshold).sum())

            # 资金性质判定
            if m.avg_turnover > 10 or m.high_turnover_days > 20:
                m.capital_type = "游资主导"
            elif m.avg_turnover < 3 and m.max_turnover < 10:
                m.capital_type = "机构控盘"
            else:
                m.capital_type = "混合型"

        if len(tr) < n * 0.8:
            m.data_coverage_note = f"换手率数据仅覆盖{len(tr)}/{n}个交易日"
    else:
        m.data_coverage_note = "无换手率数据（daily_basic表未覆盖此时段）"
        m.capital_type = "数据不足"

    # ── 缩量回调分析 ──
    m.volume_shrink_ratio, m.shrink_quality = _analyze_shrink(df, config)

    # ── 近期活跃度对比 ──
    _analyze_activity_trend(df, m)

    # ── 评分与诊断 ──
    m.score = _score_volume(m)
    m.diagnosis = _diagnose_volume(m)

    return m


def _analyze_shrink(df: pd.DataFrame, config: PersonalityConfig) -> tuple:
    """分析缩量回调纯度"""
    pct = df['pct_chg'].values
    vol = df['vol'].values

    up_vols = vol[pct > 0.5]
    down_vols = vol[pct < -0.5]

    if len(up_vols) == 0 or len(down_vols) == 0:
        return 0.0, "无明显模式"

    ratio = round(float(np.mean(down_vols) / np.mean(up_vols)), 2)

    if ratio < config.volume_shrink_ratio:
        quality = "优质缩量"
    elif ratio > 1.0:
        quality = "放量回调"
    else:
        quality = "无明显模式"

    return ratio, quality


def _analyze_activity_trend(df: pd.DataFrame, m: VolumeProfileMetrics):
    """近3月 vs 近3年活跃度对比"""
    if len(df) < 63:
        m.activity_trend = "数据不足"
        m.activity_ratio = 1.0
        return

    # 振幅
    amp = ((df['high'] - df['low']) / df['pre_close'].replace(0, np.nan) * 100).dropna()
    if len(amp) < 63:
        m.activity_trend = "数据不足"
        return

    recent = amp.iloc[-63:].mean()
    historical = amp.mean()

    m.recent_avg_amplitude = round(float(recent), 2)
    m.historical_avg_amplitude = round(float(historical), 2)
    m.activity_ratio = round(float(recent / historical), 2) if historical > 0 else 1.0

    if m.activity_ratio > 1.5:
        m.activity_trend = "股性正在觉醒"
    elif m.activity_ratio < 0.6:
        m.activity_trend = "股性正在死亡"
    else:
        m.activity_trend = "股性稳定"


def _score_volume(m: VolumeProfileMetrics) -> float:
    s = 50.0
    if m.shrink_quality == "优质缩量":
        s += 15
    elif m.shrink_quality == "放量回调":
        s -= 10

    if m.capital_type == "机构控盘":
        s += 10
    elif m.capital_type == "游资主导":
        s += 5  # 游资不一定差，但风险高

    if m.activity_trend == "股性正在觉醒":
        s += 8
    elif m.activity_trend == "股性正在死亡":
        s -= 12

    return round(max(0, min(100, s)), 1)


def _diagnose_volume(m: VolumeProfileMetrics) -> str:
    parts = []
    if m.capital_type == "游资主导":
        parts.append(f"游资主导型：平均换手{m.avg_turnover}%，超高换手(>{15}%)天数{m.high_turnover_days}天，快进快出风险高")
    elif m.capital_type == "机构控盘":
        parts.append(f"机构控盘型：平均换手仅{m.avg_turnover}%，筹码稳定，适合中长线")
    elif m.capital_type != "数据不足":
        parts.append(f"混合型资金：平均换手{m.avg_turnover}%")

    if m.shrink_quality == "优质缩量":
        parts.append(f"量价配合良好，回调缩量比{m.volume_shrink_ratio}，主力锁仓迹象明显")
    elif m.shrink_quality == "放量回调":
        parts.append(f"回调放量（比值{m.volume_shrink_ratio}），警惕主力出货")

    if m.activity_trend == "股性正在觉醒":
        parts.append(f"近期活跃度飙升（近3月振幅{m.recent_avg_amplitude}% vs 历史{m.historical_avg_amplitude}%），关注资金异动")
    elif m.activity_trend == "股性正在死亡":
        parts.append(f"近期活跃度骤降（近3月振幅{m.recent_avg_amplitude}% vs 历史{m.historical_avg_amplitude}%），警惕沦为僵尸股")

    if m.data_coverage_note:
        parts.append(f"[注]{m.data_coverage_note}")

    return "；".join(parts) + "。" if parts else "数据不足，无法诊断。"
