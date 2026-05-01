"""维度二：习惯 —— 均线契合度与趋势延续性"""
import numpy as np
import pandas as pd
from .personality_metrics import HabitMetrics
from .personality_config import PersonalityConfig, compute_decay_weights


def analyze_habit(
    df: pd.DataFrame,
    config: PersonalityConfig,
) -> HabitMetrics:
    """
    分析股票习惯维度。
    df: 日线数据，须含 close, pct_chg, trade_date，按日期升序。
    """
    m = HabitMetrics()
    if df.empty or len(df) < 60:
        m.diagnosis = "数据不足，无法分析趋势习惯"
        return m

    close = df['close'].values
    pct_chg = df['pct_chg'].values
    n = len(df)

    # ── 计算均线 ──
    ma_dict = {}
    for w in config.ma_windows:
        if n >= w:
            ma_dict[w] = pd.Series(close).rolling(w).mean().values

    # ── 趋势连贯性分析 ──
    # 使用20日均线判断上涨波段
    ref_ma = 20 if 20 in ma_dict else (config.ma_windows[0] if ma_dict else None)
    if ref_ma and ref_ma in ma_dict:
        ma_vals = ma_dict[ref_ma]
        uptrend_durations = _detect_uptrend_durations(close, ma_vals)
        if uptrend_durations:
            m.avg_uptrend_days = round(np.mean(uptrend_durations), 1)
            m.max_uptrend_days = max(uptrend_durations)

    # ── A字杀检测 ──
    m.a_kill_count = _detect_a_kills(df, config)

    # ── 趋势类型判定 ──
    if m.a_kill_count >= 3 and m.avg_uptrend_days < 10:
        m.trend_type = "A字杀"
        m.staircase_score = max(0, 30 - m.a_kill_count * 5)
    elif m.avg_uptrend_days >= 20 and m.a_kill_count <= 1:
        m.trend_type = "阶梯上涨"
        m.staircase_score = min(100, 60 + m.avg_uptrend_days)
    else:
        m.trend_type = "混合型"
        m.staircase_score = 50

    # ── 真命天子均线 ──
    best_ma = 0
    best_rate = 0.0
    ma_rates = {}

    for w, ma_vals in ma_dict.items():
        rate = _calc_ma_bounce_rate(close, ma_vals, w, config)
        ma_rates[w] = round(rate, 1)
        if rate > best_rate:
            best_rate = rate
            best_ma = w

    m.best_ma = best_ma
    m.best_ma_success_rate = round(best_rate, 1)
    m.ma_success_rates = ma_rates

    # ── 评分与诊断 ──
    m.score = _score_habit(m)
    m.diagnosis = _diagnose_habit(m)

    return m


def _detect_uptrend_durations(close: np.ndarray, ma: np.ndarray) -> list:
    """检测收盘价连续在均线上方的波段持续天数"""
    durations = []
    streak = 0
    for i in range(len(close)):
        if np.isnan(ma[i]):
            continue
        if close[i] > ma[i]:
            streak += 1
        else:
            if streak >= 3:
                durations.append(streak)
            streak = 0
    if streak >= 3:
        durations.append(streak)
    return durations


def _detect_a_kills(df: pd.DataFrame, config: PersonalityConfig) -> int:
    """检测A字杀：连涨N天累计涨幅>X%后，随后M天累计跌幅>Y%"""
    count = 0
    pct = df['pct_chg'].values
    n = len(pct)
    i = 0
    while i < n - config.a_kill_rise_days - config.a_kill_fall_days:
        # 检查连涨
        rise_sum = sum(pct[i:i + config.a_kill_rise_days])
        if rise_sum >= config.a_kill_rise_pct:
            # 检查随后下跌
            fall_start = i + config.a_kill_rise_days
            fall_end = min(fall_start + config.a_kill_fall_days, n)
            fall_sum = sum(pct[fall_start:fall_end])
            if fall_sum <= -config.a_kill_fall_pct:
                count += 1
                i = fall_end
                continue
        i += 1
    return count


def _calc_ma_bounce_rate(
    close: np.ndarray, ma: np.ndarray, window: int, config: PersonalityConfig
) -> float:
    """计算均线触碰后反弹成功率"""
    touches = 0
    bounces = 0
    n = len(close)
    tolerance = config.ma_touch_tolerance

    i = window  # 从均线有效位置开始
    while i < n - config.ma_bounce_window:
        if np.isnan(ma[i]):
            i += 1
            continue

        # 从上方跌至均线附近
        prev_above = i > 0 and close[i - 1] > ma[i - 1] * (1 + tolerance) if not np.isnan(ma[i-1]) else False
        near_ma = abs(close[i] - ma[i]) / ma[i] <= tolerance

        if prev_above and near_ma:
            touches += 1
            # 检查后续N天是否站回均线上方
            bounced = False
            for j in range(1, config.ma_bounce_window + 1):
                if i + j < n and not np.isnan(ma[i + j]):
                    if close[i + j] > ma[i + j] * (1 + tolerance * 0.5):
                        bounced = True
                        break
            if bounced:
                bounces += 1
            i += config.ma_bounce_window  # 跳过反弹窗口避免重复计数
        else:
            i += 1

    return (bounces / touches * 100) if touches > 0 else 0.0


def _score_habit(m: HabitMetrics) -> float:
    s = 50.0
    s += m.staircase_score * 0.2
    if m.a_kill_count >= 3:
        s -= 15
    if m.best_ma_success_rate > 70:
        s += 15
    elif m.best_ma_success_rate > 50:
        s += 8
    if m.avg_uptrend_days > 20:
        s += 10
    return round(max(0, min(100, s)), 1)


def _diagnose_habit(m: HabitMetrics) -> str:
    parts = []
    if m.trend_type == "阶梯上涨":
        parts.append(f"趋势良好，属于阶梯上涨型，平均上涨波段{m.avg_uptrend_days}天")
    elif m.trend_type == "A字杀":
        parts.append(f"警惕！A字杀频发（{m.a_kill_count}次），暴涨后易暴跌，连涨两天建议止盈")
    else:
        parts.append(f"趋势混合型，上涨波段均{m.avg_uptrend_days}天，A字杀{m.a_kill_count}次")

    if m.best_ma > 0:
        parts.append(f"真命天子均线：{m.best_ma}日线（反弹成功率{m.best_ma_success_rate}%）")
        if m.best_ma_success_rate > 70:
            parts.append(f"建议在{m.best_ma}日线附近买入，跌破则离场")
    else:
        parts.append("无明显有效防守均线")

    return "；".join(parts) + "。"
