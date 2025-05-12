#!/usr/bin/env python3
"""
测试代理设置是否正确配置
"""
import os
import asyncio
from submitAI.proxy_helper import get_aiohttp_proxy, test_proxy_connection

async def main():
    # 打印当前的代理设置
    print("当前配置的 HTTPS_PROXY 环境变量:", os.environ.get('HTTPS_PROXY'))
    print("当前配置的 https_proxy 环境变量:", os.environ.get('https_proxy'))
    print("当前配置的 HTTP_PROXY 环境变量:", os.environ.get('HTTP_PROXY'))
    print("当前配置的 http_proxy 环境变量:", os.environ.get('http_proxy'))
    
    # 获取通过我们的函数检测到的代理
    print("\n通过 get_aiohttp_proxy() 检测到的代理设置:", get_aiohttp_proxy())
    
    # 测试连接
    print("\n开始测试与 OpenAI API 的连接...")
    result = await test_proxy_connection("https://api.openai.com/v1/models")
    print("连接测试结果:", result)
    
    # 通过显式设置环境变量测试
    if not get_aiohttp_proxy():
        print("\n未检测到代理设置，尝试显式设置为 http://127.0.0.1:7890...")
        os.environ['https_proxy'] = 'http://127.0.0.1:7890'
        print("设置后通过 get_aiohttp_proxy() 检测到的代理:", get_aiohttp_proxy())
        
        # 再次测试连接
        print("\n使用显式设置的代理再次测试连接...")
        result = await test_proxy_connection("https://api.openai.com/v1/models")
        print("连接测试结果:", result)

if __name__ == "__main__":
    asyncio.run(main()) 