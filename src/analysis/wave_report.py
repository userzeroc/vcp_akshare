"""
wave_report.py
==============
波动分析结果的格式化输出与统计摘要。

职责：
- 将 WaveResult 转化为人类可读的终端输出（CLI 用）
- 提供结构化 dict 供 Dash / 其他调用方消费（API 用）
- 不包含任何检测逻辑，只消费 WaveResult
"""

from .wave_detector import WaveResult, WaveConfig


# ---------------------------------------------------------------------------
# CLI 输出
# ---------------------------------------------------------------------------

def print_wave_summary(result: WaveResult) -> None:
    """
    在终端打印显著波动与噪音波动的完整统计摘要。

    Parameters
    ----------
    result : WaveResult
        由 WaveDetector.detect() 返回的结果对象。
    """
    cfg = result.config
    waves_df = result.waves_df
    noise_df = result.noise_df

    # ── 显著波动摘要 ──────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("【显著波动统计摘要】")
    sig_pct = cfg.signal_prominence_ratio * 100
    print(f"阈值：单次波动幅度 > 均价的 {sig_pct:.1f}%")

    if waves_df.empty:
        print("未检测到显著波动。")
    else:
        uptrends = waves_df[waves_df['阶段'] == '上涨']
        downtrends = waves_df[waves_df['阶段'] == '下跌']

        print(f"总共发生显著波动：{len(waves_df)} 次"
              f"（上涨 {len(uptrends)} 次，下跌 {len(downtrends)} 次）")

        if not uptrends.empty:
            print(f"\n  上涨段  平均幅度: +{uptrends['波动幅度 (%)'].mean():.2f}%"
                  f"  平均持续: {uptrends['持续时间 (交易日)'].mean():.0f} 个交易日")
        if not downtrends.empty:
            print(f"  下跌段  平均幅度: {downtrends['波动幅度 (%)'].mean():.2f}%"
                  f"  平均持续: {downtrends['持续时间 (交易日)'].mean():.0f} 个交易日")

        print("\n详细波动记录：")
        print(waves_df.to_string(index=False))

    # ── 噪音波动摘要 ──────────────────────────────────────────────────────
    print("\n" + "-" * 50)
    print("【噪音波动统计摘要】")
    print(f"阈值：波动幅度在 {cfg.noise_amplitude_min}% 到 {cfg.noise_amplitude_max}% 之间")

    if noise_df.empty:
        print("未检测到符合条件的噪音波动。")
    else:
        up_n = noise_df[noise_df['噪音类型'] == '反弹噪音 (上涨)']
        dn_n = noise_df[noise_df['噪音类型'] == '回调噪音 (下跌)']

        print(f"总共发生噪音波动：{len(noise_df)} 次"
              f"（反弹 {len(up_n)} 次，回调 {len(dn_n)} 次）")

        if not up_n.empty:
            print(f"\n  反弹噪音  平均幅度: +{up_n['幅度 (%)'].mean():.2f}%"
                  f"  平均持续: {up_n['时长 (交易日)'].mean():.1f} 天")
        if not dn_n.empty:
            print(f"  回调噪音  平均幅度: {dn_n['幅度 (%)'].mean():.2f}%"
                  f"  平均持续: {dn_n['时长 (交易日)'].mean():.1f} 天")

    print("=" * 50 + "\n")


# ---------------------------------------------------------------------------
# 结构化统计（供 Dash / API 使用）
# ---------------------------------------------------------------------------

def get_wave_stats(result: WaveResult) -> dict:
    """
    返回波动统计的结构化字典，供 Dash 回调或其他模块消费。

    Parameters
    ----------
    result : WaveResult

    Returns
    -------
    dict
        包含以下 key：
        - signal_count   : int，显著波动总次数
        - uptrend_count  : int，上涨次数
        - downtrend_count: int，下跌次数
        - avg_up_amp     : float，平均上涨幅度(%)
        - avg_dn_amp     : float，平均下跌幅度(%)
        - avg_up_days    : float，平均上涨持续（交易日）
        - avg_dn_days    : float，平均下跌持续（交易日）
        - noise_count    : int，噪音波动总次数
        - noise_up_count : int，反弹噪音次数
        - noise_dn_count : int，回调噪音次数
        - waves_df       : pd.DataFrame，显著波动明细
        - noise_df       : pd.DataFrame，噪音波动明细
    """
    waves_df = result.waves_df
    noise_df = result.noise_df

    up = waves_df[waves_df['阶段'] == '上涨'] if not waves_df.empty else waves_df
    dn = waves_df[waves_df['阶段'] == '下跌'] if not waves_df.empty else waves_df
    n_up = noise_df[noise_df['噪音类型'] == '反弹噪音 (上涨)'] if not noise_df.empty else noise_df
    n_dn = noise_df[noise_df['噪音类型'] == '回调噪音 (下跌)'] if not noise_df.empty else noise_df

    return {
        'signal_count': len(waves_df),
        'uptrend_count': len(up),
        'downtrend_count': len(dn),
        'avg_up_amp': round(up['波动幅度 (%)'].mean(), 2) if not up.empty else 0.0,
        'avg_dn_amp': round(dn['波动幅度 (%)'].mean(), 2) if not dn.empty else 0.0,
        'avg_up_days': round(up['持续时间 (交易日)'].mean(), 1) if not up.empty else 0.0,
        'avg_dn_days': round(dn['持续时间 (交易日)'].mean(), 1) if not dn.empty else 0.0,
        'noise_count': len(noise_df),
        'noise_up_count': len(n_up),
        'noise_dn_count': len(n_dn),
        'waves_df': waves_df,
        'noise_df': noise_df,
    }
