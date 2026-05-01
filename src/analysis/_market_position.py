"""维度四：江湖地位 —— 板块联动与大盘逆反"""
import numpy as np
import pandas as pd
from .personality_metrics import MarketPositionMetrics
from .personality_config import PersonalityConfig


def analyze_market_position(
    df: pd.DataFrame,
    df_index: pd.DataFrame,
    benchmark_name: str,
    benchmark_code: str,
    config: PersonalityConfig,
) -> MarketPositionMetrics:
    """
    分析江湖地位维度。
    df: 个股日线 (trade_date, pct_chg)
    df_index: 基准指数日线 (trade_date, pct_chg)
    """
    m = MarketPositionMetrics()
    m.benchmark_index = benchmark_name
    m.benchmark_code = benchmark_code

    if df.empty or df_index.empty:
        m.diagnosis = "数据不足，无法分析板块联动"
        return m

    # 对齐交易日
    stock_returns = df.set_index('trade_date')['pct_chg']
    index_returns = df_index.set_index('trade_date')['pct_chg']
    aligned = pd.DataFrame({
        'stock': stock_returns,
        'index': index_returns,
    }).dropna()

    if len(aligned) < 30:
        m.diagnosis = "对齐数据不足30天，无法分析"
        return m

    sr = aligned['stock'].values
    ir = aligned['index'].values

    # ── Beta系数 ──
    cov = np.cov(sr, ir)
    var_index = cov[1, 1]
    m.beta = round(float(cov[0, 1] / var_index), 2) if var_index > 0 else 1.0

    # ── 大盘下跌日表现 ──
    bear_mask = ir < config.market_down_threshold
    bull_mask = ir > config.market_up_threshold

    if bear_mask.sum() > 0:
        m.bear_day_avg_return = round(float(sr[bear_mask].mean()), 2)
    if bull_mask.sum() > 0:
        m.bull_day_avg_return = round(float(sr[bull_mask].mean()), 2)

    # ── 抗跌评分 ──
    # 大盘跌日，个股跌得少或不跌 → 高分
    if bear_mask.sum() > 0:
        avg_bear_index = ir[bear_mask].mean()
        if avg_bear_index < 0:
            # 抗跌比 = 个股跌幅 / 大盘跌幅，越小越抗跌
            resist_ratio = m.bear_day_avg_return / avg_bear_index
            m.anti_drop_score = round(max(0, min(100, (1 - resist_ratio + 0.5) * 50)), 1)
        else:
            m.anti_drop_score = 50.0
    else:
        m.anti_drop_score = 50.0

    # ── 领涨评分 ──
    # 大盘反弹日（前日跌今日涨），个股涨幅超过大盘涨幅的比例
    if bull_mask.sum() > 0:
        outperform_count = (sr[bull_mask] > ir[bull_mask]).sum()
        m.lead_rally_score = round(float(outperform_count / bull_mask.sum() * 100), 1)
    else:
        m.lead_rally_score = 50.0

    # ── 类型判定 ──
    if m.anti_drop_score > 65 and m.lead_rally_score > 55:
        m.position_type = "龙头"
    elif m.anti_drop_score < 35 and m.lead_rally_score < 45:
        m.position_type = "弱势"
    else:
        m.position_type = "跟随"

    m.score = _score_position(m)
    m.diagnosis = _diagnose_position(m)

    return m


def _score_position(m: MarketPositionMetrics) -> float:
    s = 50.0
    if m.position_type == "龙头":
        s += 20
    elif m.position_type == "弱势":
        s -= 20
    s += (m.anti_drop_score - 50) * 0.3
    s += (m.lead_rally_score - 50) * 0.2
    return round(max(0, min(100, s)), 1)


def _diagnose_position(m: MarketPositionMetrics) -> str:
    parts = []

    if m.position_type == "龙头":
        parts.append(f"板块龙头特质：跟涨不跟跌，Beta={m.beta}")
        parts.append(f"大盘跌日平均收益{m.bear_day_avg_return}%（抗跌评分{m.anti_drop_score}）")
        parts.append(f"大盘涨日平均收益{m.bull_day_avg_return}%（领涨评分{m.lead_rally_score}）")
        parts.append("建议加入核心池，大盘企稳时优先关注")
    elif m.position_type == "弱势":
        parts.append(f"典型弱势股：跟跌不跟涨，Beta={m.beta}")
        parts.append(f"大盘跌日平均收益{m.bear_day_avg_return}%，大盘涨日仅{m.bull_day_avg_return}%")
        parts.append("建议拉黑，绝不碰")
    else:
        parts.append(f"跟随型：Beta={m.beta}，与大盘({m.benchmark_index})同步性较高")
        parts.append(f"抗跌评分{m.anti_drop_score}，领涨评分{m.lead_rally_score}")

    return "；".join(parts) + "。"
