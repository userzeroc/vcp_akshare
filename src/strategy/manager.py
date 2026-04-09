
import json
import os
from typing import Dict, Any, Optional

class StrategyManager:
    """
    策略配置管理器
    负责加载配置文件并为特定股票提供参数注入
    """
    
    def __init__(self, config_path: str = "configs/stock_strategies.json"):
        self.config_path = config_path
        self.configs = self._load_configs()

    def _load_configs(self) -> Dict[str, Any]:
        """加载 JSON 配置文件"""
        if not os.path.exists(self.config_path):
            print(f"提示: 配置文件 {self.config_path} 不存在，将使用策略默认参数。")
            return {}
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"错误: 加载配置文件失败: {e}")
            return {}

    def get_stock_params(self, ts_code: str, strategy_name: str) -> Dict[str, Any]:
        """
        获取特定股票对特定策略的参数覆盖
        """
        # 支持模糊匹配（比如配置里是 601899.SH，传入参数也是 601899.SH）
        stock_config = self.configs.get(ts_code, {})
        return stock_config.get(strategy_name, {})

    def reload(self):
        """重新加载配置"""
        self.configs = self._load_configs()
