#!/usr/bin/env python3
"""
测试示例 - 展示如何使用 UserOnlineManager

注意：这只是一个示例，展示了程序的功能
实际使用时需要在 config.json 中配置有效的 Discord token
"""

import asyncio
import logging
from config import get_config

# 简单测试配置加载
app_config = get_config()

print("=" * 60)
print("配置信息检查")
print("=" * 60)

# 检查环境
env = app_config.get('app.environment', 'test')
print(f"当前环境: {env}")

# 检查 token
tokens = app_config.get_tokens()
print(f"Token 数量: {len(tokens)}")
for i, token in enumerate(tokens):
    # 只显示 token 的前后几个字符
    masked_token = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else "***"
    print(f"  Token {i}: {masked_token}")

# 检查代理配置
proxy_enabled = app_config.get('proxy.enabled', False)
print(f"\n代理启用: {proxy_enabled}")
if proxy_enabled:
    webshare_key = app_config.get('proxy.webshare_api_key', '')
    masked_key = f"{webshare_key[:10]}...{webshare_key[-5:]}" if len(webshare_key) > 15 else "***"
    print(f"Webshare API Key: {masked_key}")
    print(f"代理使用比例: {app_config.get('proxy.use_proxy_ratio', 0.5)}")

# 检查重连配置
print(f"\n重连配置:")
print(f"  最大重试次数: {app_config.get('reconnect.max_attempts', 5)}")
print(f"  重试延迟: {app_config.get('reconnect.retry_delay', 5)} 秒")
print(f"  退避乘数: {app_config.get('reconnect.backoff_multiplier', 1.5)}")

print("\n" + "=" * 60)
print("配置检查完成")
print("=" * 60)
print("\n如果要运行实际程序，请执行: python main.py")
