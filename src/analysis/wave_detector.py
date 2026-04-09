"""
wave_detector.py
================
波动检测核心模块。

职责：
- 通过 WaveConfig 统一管理所有检测阈值
- WaveDetector.detect() 一次调用，同时返回显著波动与噪音波动
- 输出标准化的 WaveResult dataclass，供报告层和可视化层消费
"""

from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy.signal import find_peaks


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

@dataclass
class WaveConfig:
    """
    波动检测参数配置。

    Attributes
    ----------
    signal_prominence_ratio : float
        显著波动的显著性阈值，相对于均价的比例。
        默认 0.05，即波动幅度须超过均价的 5%。
    noise_prominence_ratio : float
        噪音波动峰谷检测时的最小显著性，相对于均价的比例。
        默认 0.015（1.5%）。
    signal_min_distance : int
        相邻显著波峰/波谷之间的最小间隔（交易日数）。默认 5。
    noise_min_distance : int
        相邻噪音波峰/波谷之间的最小间隔（交易日数）。默认 2。
    noise_amplitude_min : float
        噪音波动幅度下限（%）。默认 1.5。
    noise_amplitude_max : float
        噪音波动幅度上限（%），通常等于显著波阈值对应的百分比。默认 5.0。
    """
    signal_prominence_ratio: float = 0.05
    noise_prominence_ratio: float = 0.015
    signal_min_distance: int = 5
    noise_min_distance: int = 2
    noise_amplitude_min: float = 1.5
    noise_amplitude_max: float = 5.0


# ---------------------------------------------------------------------------
# 结果
# ---------------------------------------------------------------------------

@dataclass
class WaveResult:
    """
    WaveDetector.detect() 的返回值。

    Attributes
    ----------
    peaks : np.ndarray
        显著波峰在价格序列中的位置索引数组。
    troughs : np.ndarray
        显著波谷在价格序列中的位置索引数组。
    waves_df : pd.DataFrame
        显著波动明细，每行代表一次完整的上涨或下跌波段。
        列：阶段、起始日期、结束日期、起始价格(元)、结束价格(元)、持续时间(交易日)、波动幅度(%)
    noise_df : pd.DataFrame
        噪音波动明细，每行代表一次小幅抖动。
        列：噪音类型、时长(交易日)、幅度(%)
    config : WaveConfig
        本次检测所使用的配置，方便报告层引用阈值信息。
    """
    peaks: np.ndarray
    troughs: np.ndarray
    waves_df: pd.DataFrame
    noise_df: pd.DataFrame
    config: WaveConfig


# ---------------------------------------------------------------------------
# 检测器
# ---------------------------------------------------------------------------

class WaveDetector:
    """
    波动检测器。

    Usage
    -----
    config = WaveConfig(signal_prominence_ratio=0.05)
    detector = WaveDetector(config)
    result = detector.detect(df)   # df 须带 avg_price 列
    """

    def __init__(self, config: WaveConfig = None):
        self.config = config or WaveConfig()

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def detect(self, df: pd.DataFrame) -> WaveResult:
        """
        对整理好的价格 DataFrame 执行波动检测。

        Parameters
        ----------
        df : pd.DataFrame
            须包含 avg_price 列，以日期为 DatetimeIndex，按升序排列。

        Returns
        -------
        WaveResult
        """
        cfg = self.config
        y = df['avg_price'].values
        mean_price = y.mean()

        # 显著波峰谷
        sig_prominence = mean_price * cfg.signal_prominence_ratio
        peaks, _ = find_peaks(y, prominence=sig_prominence, distance=cfg.signal_min_distance)
        troughs, _ = find_peaks(-y, prominence=sig_prominence, distance=cfg.signal_min_distance)

        sig_extrema = self._find_alternating_extrema(peaks, troughs)
        waves_list = self._build_waves(sig_extrema, y, df.index)
        waves_df = pd.DataFrame(waves_list)

        # 噪音波峰谷
        noise_prominence = mean_price * cfg.noise_prominence_ratio
        n_peaks, _ = find_peaks(y, prominence=noise_prominence, distance=cfg.noise_min_distance)
        n_troughs, _ = find_peaks(-y, prominence=noise_prominence, distance=cfg.noise_min_distance)

        n_extrema = self._find_alternating_extrema(n_peaks, n_troughs)
        noise_list = self._build_noise_waves(n_extrema, y)
        noise_df = pd.DataFrame(noise_list)

        return WaveResult(
            peaks=peaks,
            troughs=troughs,
            waves_df=waves_df,
            noise_df=noise_df,
            config=cfg,
        )

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _find_alternating_extrema(peaks: np.ndarray, troughs: np.ndarray) -> pd.DataFrame:
        """
        将波峰数组与波谷数组合并，过滤掉连续同类型的点，
        保证结果序列中峰谷严格交替出现。
        """
        peaks_df = pd.DataFrame({'idx': peaks, 'type': 'peak'})
        troughs_df = pd.DataFrame({'idx': troughs, 'type': 'trough'})
        combined = pd.concat([peaks_df, troughs_df]).sort_values('idx').reset_index(drop=True)

        filtered = []
        last_type = None
        for _, row in combined.iterrows():
            if row['type'] != last_type:
                filtered.append(row)
                last_type = row['type']

        return pd.DataFrame(filtered)

    @staticmethod
    def _build_waves(extrema: pd.DataFrame, y: np.ndarray, index: pd.Index) -> list:
        """
        将相邻的峰谷对配对成波段，计算每段的幅度和持续时间。
        """
        waves = []
        if extrema.empty:
            return waves

        for i in range(1, len(extrema)):
            start_idx = int(extrema.iloc[i - 1]['idx'])
            end_idx = int(extrema.iloc[i]['idx'])
            start_type = extrema.iloc[i - 1]['type']

            start_price = y[start_idx]
            end_price = y[end_idx]
            amplitude = ((end_price - start_price) / start_price) * 100

            waves.append({
                '阶段': '上涨' if start_type == 'trough' else '下跌',
                '起始日期': index[start_idx].strftime('%Y-%m-%d'),
                '结束日期': index[end_idx].strftime('%Y-%m-%d'),
                '起始价格 (元)': round(start_price, 2),
                '结束价格 (元)': round(end_price, 2),
                '持续时间 (交易日)': end_idx - start_idx,
                '波动幅度 (%)': round(amplitude, 2),
            })

        return waves

    def _build_noise_waves(self, extrema: pd.DataFrame, y: np.ndarray) -> list:
        """
        在噪音级别的峰谷序列中，筛选出幅度处于 [noise_min, noise_max) 区间的波段。
        """
        cfg = self.config
        noise_waves = []
        if extrema.empty:
            return noise_waves

        for i in range(1, len(extrema)):
            start_idx = int(extrema.iloc[i - 1]['idx'])
            end_idx = int(extrema.iloc[i]['idx'])
            start_type = extrema.iloc[i - 1]['type']

            start_price = y[start_idx]
            end_price = y[end_idx]
            amplitude = ((end_price - start_price) / start_price) * 100
            amplitude_abs = abs(amplitude)

            if cfg.noise_amplitude_min <= amplitude_abs < cfg.noise_amplitude_max:
                noise_waves.append({
                    '噪音类型': '反弹噪音 (上涨)' if start_type == 'trough' else '回调噪音 (下跌)',
                    '时长 (交易日)': end_idx - start_idx,
                    '幅度 (%)': round(amplitude, 2),
                })

        return noise_waves
