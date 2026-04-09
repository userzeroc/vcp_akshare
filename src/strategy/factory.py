
from typing import Type, Any, Dict
from .base import BaseStrategy
from .vcp_strategy import VCPStrategy
from .momentum_breakout import MomentumBreakoutStrategy
from .manager import StrategyManager

class StrategyFactory:
    """
    策略工厂类
    负责根据股票代码和策略名称创建已注入定制参数的策略实例
    """
    
    # 策略类映射
    _STRATEGY_MAP = {
        "VCPStrategy": VCPStrategy,
        "MomentumBreakoutStrategy": MomentumBreakoutStrategy,
        "VCP": VCPStrategy,  # 别名
        "Momentum": MomentumBreakoutStrategy  # 别名
    }
    
    _manager = StrategyManager()

    @classmethod
    def create(cls, strategy_name: str, ts_code: str = None, **kwargs) -> BaseStrategy:
        """
        创建策略实例
        :param strategy_name: 策略名称 (VCPStrategy 或 MomentumBreakoutStrategy)
        :param ts_code: 股票代码 (用于查找定制参数)
        :param kwargs: 手动指定的参数覆盖 (优先级最高)
        """
        strategy_class = cls._STRATEGY_MAP.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"未知策略类型: {strategy_name}. 可用类型: {list(cls._STRATEGY_MAP.keys())}")
        
        # 1. 获取默认参数 (从类定义中提取，暂时通过实例化一个空的再更新，
        # 或是直接依赖 Python 的关键字参数解包机制)
        
        # 2. 获取个股定制参数 (从配置文件)
        custom_params = {}
        if ts_code:
            custom_params = cls._manager.get_stock_params(ts_code, strategy_name)
            # 如果是别名，尝试查找完整类名的配置
            if not custom_params:
                full_name = strategy_class.__name__
                custom_params = cls._manager.get_stock_params(ts_code, full_name)
        
        # 3. 合并参数优先级: 手动传入 > 配置文件 > 类默认值
        final_params = {**custom_params, **kwargs}
        
        print(f"🛠️ [Factory] 实例化 {strategy_class.__name__} (股票: {ts_code if ts_code else 'N/A'})")
        if custom_params:
            print(f"   注入配置参数: {custom_params}")
            
        return strategy_class(**final_params)

    @classmethod
    def reload_config(cls):
        """刷新配置文件"""
        cls._manager.reload()
