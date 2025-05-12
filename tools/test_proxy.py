#!/usr/bin/env python3
"""
测试代理连接的工具脚本
用于验证代理设置是否生效，以及是否能访问API
"""

import sys
import os
import requests
import asyncio
import aiohttp
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from submitAI.proxy_helper import get_requests_proxies, get_aiohttp_proxy, test_proxy_connection
except ImportError:
    print("找不到代理助手模块，可能项目结构已变更")
    sys.exit(1)

def print_proxy_settings():
    """打印当前代理设置"""
    http_proxy = os.environ.get('http_proxy')
    https_proxy = os.environ.get('https_proxy')
    all_proxy = os.environ.get('all_proxy')
    
    print("当前代理设置:")
    print(f"  HTTP代理: {http_proxy or '未设置'}")
    print(f"  HTTPS代理: {https_proxy or '未设置'}")
    print(f"  ALL代理: {all_proxy or '未设置'}")
    print()

def test_requests_connection(url="https://api.openai.com"):
    """使用requests测试连接"""
    print(f"使用requests测试连接到 {url}...")
    proxies = get_requests_proxies()
    print(f"使用代理: {proxies}")
    
    try:
        response = requests.get(url, proxies=proxies, timeout=10)
        print(f"✅ 连接成功: 状态码 {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ 连接失败: {str(e)}")
        return False

async def test_aiohttp_connection(url="https://api.openai.com"):
    """使用aiohttp测试连接"""
    print(f"使用aiohttp测试连接到 {url}...")
    result = await test_proxy_connection(url)
    
    if result['success']:
        print(f"✅ 连接成功: 状态码 {result.get('status_code')}")
        return True
    else:
        print(f"❌ 连接失败: {result.get('message')}")
        return False

async def main():
    """主函数"""
    print("=" * 60)
    print("代理连接测试工具")
    print("=" * 60)
    print()
    
    print_proxy_settings()
    
    # 使用requests测试
    test_urls = [
        "https://api.openai.com",
        "https://www.google.com",
        "https://www.aitoolslist.io"
    ]
    
    for url in test_urls:
        print("-" * 40)
        test_requests_connection(url)
        await test_aiohttp_connection(url)
        print()
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main()) 