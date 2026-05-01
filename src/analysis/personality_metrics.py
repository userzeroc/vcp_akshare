"""
personality_metrics.py
======================
股性分析指标数据类。

定义四个维度的指标 dataclass 和综合分析结果容器。
每个维度包含：原始数值指标 + 文字诊断 + 评分(0-100)。
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 维度一：脾气 —— 波动率与涨停基因
# ---------------------------------------------------------------------------

@dataclass
class LimitUpEvent:
    """单次涨停事件"""
    date: str                    # 涨停日期
    pct_chg: float               # 涨跌幅(%)
    turnover_rate: Optional[float]  # 当日换手率(%)
    quality: str                 # "放量首板" / "缩量一字板" / "尾盘偷袭板" / "普通涨停"


@dataclass
class ConsecutiveLimitEvent:
    """连板事件"""
    start_date: str              # 起始日期
    end_date: str                # 结束日期
    count: int                   # 连板天数


@dataclass
class TemperamentMetrics:
    """维度一：脾气 —— 波动率与涨停基因（测爆发力）"""

    # ── 涨停相关 ──
    limit_up_count: int = 0               # 涨停板次数
    limit_up_frequency: float = 0.0       # 涨停频率 (次/年)
    max_consecutive_limit: int = 0        # 最大连板数
    consecutive_events: list = field(default_factory=list)  # ConsecutiveLimitEvent 列表
    has_monster_gene: bool = False         # 妖股基因标记 (连板>=2)

    # ── 涨停质量分层 ──
    quality_big_volume_count: int = 0     # 放量首板次数
    quality_no_volume_count: int = 0      # 缩量一字板次数
    quality_late_count: int = 0           # 尾盘偷袭板次数
    limit_up_quality_score: float = 0.0   # 涨停质量评分(0-100)

    # ── 振幅相关 ──
    avg_amplitude: float = 0.0            # 平均日内振幅(%)
    median_amplitude: float = 0.0         # 中位数振幅(%)
    amplitude_p90: float = 0.0            # 90分位振幅(%)

    # ── 炸板相关 ──
    touch_limit_count: int = 0            # 盘中触及涨停次数
    fail_board_count: int = 0             # 炸板次数
    fail_board_rate: float = 0.0          # 炸板率(%)

    # ── 综合 ──
    diagnosis: str = ""                   # 文字诊断
    score: float = 0.0                    # 维度评分 (0-100)


# ---------------------------------------------------------------------------
# 维度二：习惯 —— 均线契合度与趋势延续性
# ---------------------------------------------------------------------------

@dataclass
class HabitMetrics:
    """维度二：习惯 —— 均线契合度与趋势延续性（定买卖点）"""

    # ── 趋势连贯性 ──
    avg_uptrend_days: float = 0.0         # 平均上涨波段天数
    max_uptrend_days: int = 0             # 最长上涨波段天数
    a_kill_count: int = 0                 # A字杀次数
    staircase_score: float = 0.0          # 阶梯上涨评分(0-100)
    trend_type: str = ""                  # "阶梯上涨" / "A字杀" / "混合型"

    # ── 真命天子均线 ──
    best_ma: int = 0                      # 最佳防守均线窗口
    best_ma_success_rate: float = 0.0     # 最佳均线触碰反弹成功率(%)
    ma_success_rates: dict = field(default_factory=dict)  # {5: 60.0, 10: 75.0, ...}

    # ── 综合 ──
    diagnosis: str = ""
    score: float = 0.0


# ---------------------------------------------------------------------------
# 维度三：饭量 —— 量价配合度
# ---------------------------------------------------------------------------

@dataclass
class VolumeProfileMetrics:
    """维度三：饭量 —— 量价配合度（看资金性质）"""

    # ── 换手率 ──
    max_turnover: float = 0.0             # 最大换手率(%)
    min_turnover: float = 0.0             # 最小换手率(%)
    avg_turnover: float = 0.0             # 平均换手率(%)
    high_turnover_days: int = 0           # 换手率>15%的天数
    capital_type: str = ""                # "游资主导" / "机构控盘" / "混合型"

    # ── 缩量回调 ──
    volume_shrink_ratio: float = 0.0      # 回调量/上涨量 比值
    shrink_quality: str = ""              # "优质缩量" / "放量回调" / "无明显模式"

    # ── 近期活跃度对比 ──
    recent_avg_amplitude: float = 0.0     # 近3月平均振幅
    historical_avg_amplitude: float = 0.0 # 近3年平均振幅
    activity_trend: str = ""              # "股性正在觉醒" / "股性正在死亡" / "股性稳定"
    activity_ratio: float = 0.0           # 近期/历史 比值

    # ── 数据覆盖 ──
    data_coverage_note: str = ""          # 数据覆盖说明

    # ── 综合 ──
    diagnosis: str = ""
    score: float = 0.0


# ---------------------------------------------------------------------------
# 维度四：江湖地位 —— 板块联动与大盘逆反
# ---------------------------------------------------------------------------

@dataclass
class MarketPositionMetrics:
    """维度四：江湖地位 —— 板块联动与大盘逆反（找龙头）"""

    benchmark_index: str = ""             # 使用的基准指数名称
    benchmark_code: str = ""              # 基准指数代码
    beta: float = 0.0                     # Beta系数
    bear_day_avg_return: float = 0.0      # 大盘下跌日个股平均收益(%)
    bull_day_avg_return: float = 0.0      # 大盘上涨日个股平均收益(%)
    anti_drop_score: float = 0.0          # 抗跌评分(0-100)
    lead_rally_score: float = 0.0         # 领涨评分(0-100)
    position_type: str = ""               # "龙头" / "跟随" / "弱势"

    # ── 综合 ──
    diagnosis: str = ""
    score: float = 0.0


# ---------------------------------------------------------------------------
# 综合结果
# ---------------------------------------------------------------------------

@dataclass
class ClassificationDetail:
    """归类置信度详情"""
    category: str               # "A" / "B" / "C" / "D"
    confidence: float           # 置信度(0-100)
    category_name: str          # "白马/核心资产" 等


@dataclass
class PersonalityResult:
    """股性分析完整结果"""

    # ── 基本信息 ──
    ts_code: str = ""
    name: str = ""
    market: str = ""                      # 主板/创业板/科创板
    industry: str = ""
    analysis_period: str = ""             # "2023-05-01 ~ 2026-04-30"

    # ── 四维度指标 ──
    temperament: TemperamentMetrics = field(default_factory=TemperamentMetrics)
    habit: HabitMetrics = field(default_factory=HabitMetrics)
    volume_profile: VolumeProfileMetrics = field(default_factory=VolumeProfileMetrics)
    market_position: MarketPositionMetrics = field(default_factory=MarketPositionMetrics)

    # ── 综合归类 ──
    category: str = ""                    # 主类别 "A" / "B" / "C" / "D"
    category_name: str = ""               # "白马/核心资产" / "题材龙头/妖股" / ...
    category_emoji: str = ""              # 🐎 / 🐉 / 💔 / 💀
    tactic: str = ""                      # 交易战术建议
    confidence: float = 0.0               # 主类别置信度(0-100)
    secondary_traits: list = field(default_factory=list)  # ClassificationDetail 列表

    # ── 评分汇总 ──
    scores: dict = field(default_factory=dict)  # {"temperament": 75, "habit": 60, ...}

    # ── K线数据（供报告可视化使用）──
    kline_data: list = field(default_factory=list)   # [(date, open, close, low, high), ...]
    limit_up_dates: list = field(default_factory=list)    # 涨停日列表
    fail_board_dates: list = field(default_factory=list)  # 炸板日列表
    a_kill_ranges: list = field(default_factory=list)     # A字杀区间 [(start, end), ...]
    best_ma_values: list = field(default_factory=list)    # 真命天子均线数据 [(date, value), ...]
