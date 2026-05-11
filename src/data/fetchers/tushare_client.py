"""
Tushare API 客户端封装

职责:
  - 单例模式初始化 pro_api，避免重复创建连接
  - 统一限流：每次调用后 sleep，防止超过 Tushare 频率限制
  - 统一重试：网络抖动时指数退避重试，最多 3 次

Tushare 120分账号限流参考:
  - 每分钟调用次数约 100~200 次（具体以官网为准）
  - call_interval=0.4 秒 ≈ 每分钟最多 150 次，安全范围内

用法::

    from src.data.fetchers.tushare_client import client

    df = client.query("daily", ts_code="000001.SZ", start_date="20240101")
    df = client.query("stock_basic", exchange="SSE", list_status="L")
"""

import logging
import time

import pandas as pd
import tushare as ts

from src.config import settings

logger = logging.getLogger(__name__)

# 每次 API 调用后的基础等待时间（秒）
# 120 分账号建议 0.4~0.5 秒，可通过环境变量调整
_CALL_INTERVAL: float = 0.4
_MAX_RETRIES: int = 3


class _TushareClient:
    """
    Tushare Pro API 单例客户端。

    不要直接实例化此类，请使用模块级 `client` 单例。
    """

    def __init__(self) -> None:
        token = settings.tushare.token
        if not token:
            raise ValueError(
                "TUSHARE_TOKEN 未配置，请在 .env 文件中设置 TUSHARE_TOKEN=<your_token>"
            )
        
        # 1. 初始化标准 API
        ts.set_token(token)
        self._api = ts.pro_api()
        
        # 2. 如果配置了 http_url，则应用代理策略
        if settings.tushare.http_url:
            # 暴力注入私有变量以支持第三方代理/Workers 转发
            # 这是 Tushare 客户端的一个常用 Hook 方式
            self._api._DataApi__token = token
            self._api._DataApi__http_url = settings.tushare.http_url
            logger.info("Tushare Pro API 初始化完成 [策略: Proxy, URL: %s]", settings.tushare.http_url)
        else:
            logger.info("Tushare Pro API 初始化完成 [策略: Direct]")

    def query(self, api_name: str, **kwargs) -> pd.DataFrame:
        """
        统一查询入口，内置限流与重试。

        参数:
            api_name - Tushare 接口名，如 "daily" / "stock_basic" / "trade_cal"
            **kwargs - 传递给 Tushare 接口的字段参数

        返回:
            pd.DataFrame（若接口无数据则返回空 DataFrame）

        异常:
            连续 3 次失败后抛出最后一次异常
        """
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                df: pd.DataFrame = self._api.query(api_name, **kwargs)
                time.sleep(_CALL_INTERVAL)  # 基础限流
                if df is None:
                    return pd.DataFrame()
                return df
            except Exception as exc:
                last_exc = exc
                wait = 2 ** attempt  # 指数退避：2s, 4s, 8s
                logger.warning(
                    "Tushare %s 调用失败（第%d次），%ds 后重试: %s",
                    api_name, attempt, wait, exc,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"Tushare {api_name} 连续 {_MAX_RETRIES} 次调用失败"
        ) from last_exc


# 模块级单例（懒初始化，首次 import 时创建）
client = _TushareClient()
