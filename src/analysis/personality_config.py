"""
personality_config.py — 股性分析配置与工具函数
"""
import re
import numpy as np
from dataclasses import dataclass, field


@dataclass
class PersonalityConfig:
    lookback_days: int = 750           # 3年
    ma_windows: list = field(default_factory=lambda: [5, 10, 20, 60])

    # 涨停阈值（自适应时会被覆盖）
    limit_up_pct_main: float = 9.8     # 主板
    limit_up_pct_gem: float = 19.5     # 创业板/科创板

    # 振幅
    high_amplitude_threshold: float = 5.0
    low_amplitude_threshold: float = 2.0

    # 炸板
    fail_board_close_ratio: float = 0.99

    # 换手率
    high_turnover_threshold: float = 15.0
    low_turnover_threshold: float = 3.0

    # 缩量
    volume_shrink_ratio: float = 0.5

    # 时间衰减（近6月=1.0, 6-12月=0.7, 1-2年=0.4, 2-3年=0.2）
    decay_weights: list = field(default_factory=lambda: [
        (126, 1.0), (252, 0.7), (504, 0.4), (750, 0.2)
    ])

    # A字杀参数
    a_kill_rise_days: int = 3
    a_kill_rise_pct: float = 15.0
    a_kill_fall_days: int = 5
    a_kill_fall_pct: float = 10.0

    # 均线触碰反弹窗口
    ma_bounce_window: int = 5
    ma_touch_tolerance: float = 0.01   # ±1%

    # 大盘涨跌日判定
    market_up_threshold: float = 1.0
    market_down_threshold: float = -1.0


# 板块配置映射
BOARD_CONFIG = {
    "主板": {
        "limit_up_pct": 9.8,
        "benchmark_code": "000001.SH",
        "benchmark_name": "上证指数",
    },
    "创业板": {
        "limit_up_pct": 19.5,
        "benchmark_code": "399006.SZ",
        "benchmark_name": "创业板指",
    },
    "科创板": {
        "limit_up_pct": 19.5,
        "benchmark_code": "000688.SH",
        "benchmark_name": "科创50",
    },
}

# 分类定义
CATEGORY_DEFS = {
    "A": {"name": "白马/核心资产", "emoji": "🐎",
           "tactic": "网格交易/定投。绝不追高，大跌大买，用时间换空间。沿大均线（如60日线）慢牛操作。"},
    "B": {"name": "题材龙头/妖股", "emoji": "🐉",
           "tactic": "右侧跟随，严设止损。顺势而为，跌破5日线无条件清仓，绝不扛单。适合高弹性卫星仓位。"},
    "C": {"name": "渣男/宽幅震荡股", "emoji": "💔",
           "tactic": "反人性操作。涨到压力位必卖，跌到支撑位敢买。绝对不要在这种股里谈格局。"},
    "D": {"name": "僵尸股", "emoji": "💀",
           "tactic": "直接删自选，无论跌了多少都不买，防止资金被埋。"},
}


def is_excluded_stock(name: str, market: str) -> bool:
    """判断是否应剔除（ST股 + 北交所）"""
    if market == "北交所":
        return True
    if re.search(r'ST', name, re.IGNORECASE):
        return True
    return False


def get_board_config(market: str) -> dict:
    """根据市场类型获取板块配置"""
    return BOARD_CONFIG.get(market, BOARD_CONFIG["主板"])


def compute_decay_weights(n: int, config: PersonalityConfig) -> np.ndarray:
    """计算时间衰减权重数组，索引0=最早，索引n-1=最新"""
    weights = np.ones(n)
    for boundary, w in config.decay_weights:
        # 从末尾往前数，超过boundary的部分用权重w
        cutoff = max(0, n - boundary)
        weights[:cutoff] = np.minimum(weights[:cutoff], w)
    return weights
