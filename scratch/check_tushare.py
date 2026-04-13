import os
import sys
from unittest.mock import patch

# 确保能找到 src
sys.path.append(os.getcwd())

def test_tushare_proxy_config():
    print("Testing Tushare Proxy Configuration...")
    
    test_token = "test_token_123"
    test_url = "https://test-proxy.workers.dev"
    
    # 模拟环境变量
    with patch.dict(os.environ, {
        "TUSHARE_TOKEN": test_token,
        "TUSHARE_HTTP_URL": test_url
    }):
        # 重新加载 settings 和 client 以应用新的环境变量
        import importlib
        import src.config.settings
        import src.data.fetchers.tushare_client
        
        importlib.reload(src.config.settings)
        importlib.reload(src.data.fetchers.tushare_client)
        
        # 此时 src.config.settings.settings 应该是新加载的
        from src.config.settings import settings
        
        print(f"Config Token: {settings.tushare.token}")
        print(f"Config URL: {settings.tushare.http_url}")
        
        # 尝试实例化 _TushareClient (直接测试构造逻辑，不依赖单例)
        from src.data.fetchers.tushare_client import _TushareClient
        client_instance = _TushareClient()
        
        # 验证私有变量是否被正确注入
        actual_token = getattr(client_instance._api, "_DataApi__token", None)
        actual_url = getattr(client_instance._api, "_DataApi__http_url", None)
        
        print(f"Injected Token: {actual_token}")
        print(f"Injected URL: {actual_url}")
        
        assert actual_token == test_token, f"Token mismatch: {actual_token}"
        assert actual_url == test_url, f"URL mismatch: {actual_url}"
        
        print("\n✅ Verification Successful: Tushare client correctly applies proxy configuration from settings.")

def check_current_env():
    """检查当前 .env 实际生效的配置"""
    from src.config.settings import settings
    from src.data.fetchers.tushare_client import _TushareClient
    
    print("\n--- Current Environment Config ---")
    print(f"Token: {settings.tushare.token[:6]}...{settings.tushare.token[-4:]}")
    print(f"Proxy URL: {settings.tushare.http_url or 'None (Direct Mode)'}")
    
    try:
        client = _TushareClient()
        actual_url = getattr(client._api, "_DataApi__http_url", "Default")
        print(f"Active API URL: {actual_url}")
        
        # 尝试一次极简调用
        df = client.query("trade_cal", exchange="SSE", start_date="20240101", end_date="20240101")
        if not df.empty:
            print("✅ API Connectivity: OK")
    except Exception as e:
        print(f"❌ API Connectivity: Failed - {e}")

if __name__ == "__main__":
    # 1. 运行模拟测试
    try:
        test_tushare_proxy_config()
    except Exception as e:
        print(f"\n❌ Unit Test Failed: {e}")
    
    # 2. 检查实际环境
    check_current_env()
