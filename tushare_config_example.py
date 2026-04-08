"""
Tushare 配置文件示例
请前往 https://tushare.pro/register 注册获取 Token
"""
import tushare as ts

# 设置你的 Tushare Token
# 请替换为你的 Token: https://tushare.pro/register
TUSHARE_TOKEN = "your_token_here"

# 初始化 Tushare Pro API
pro = ts.pro_api(TUSHARE_TOKEN)
