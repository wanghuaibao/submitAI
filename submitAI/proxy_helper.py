"""
代理助手模块，提供统一的代理配置和检测
"""

import os
import requests
import aiohttp
from typing import Dict, Optional, Any

def get_proxy_settings() -> Dict[str, Optional[str]]:
    """
    获取当前系统的代理设置
    
    Returns:
        包含http_proxy, https_proxy, all_proxy的字典
    """
    return {
        'http': os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY'),
        'https': os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY'),
        'all': os.environ.get('all_proxy') or os.environ.get('ALL_PROXY')
    }

def get_aiohttp_proxy() -> Optional[str]:
    """
    获取适用于aiohttp的代理设置
    
    Returns:
        代理URL或None
    """
    # 同时检查大写和小写的环境变量
    return (os.environ.get('https_proxy') or 
            os.environ.get('HTTPS_PROXY') or 
            os.environ.get('http_proxy') or 
            os.environ.get('HTTP_PROXY'))

def get_requests_proxies() -> Dict[str, Optional[str]]:
    """
    获取适用于requests库的代理设置
    
    Returns:
        包含http和https代理的字典
    """
    return {
        'http': os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY'),
        'https': os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    }

async def test_proxy_connection(url: str = "https://api.openai.com") -> Dict[str, Any]:
    """
    测试代理连接是否正常
    
    Args:
        url: 要测试的URL
        
    Returns:
        包含测试结果的字典
    """
    proxy = get_aiohttp_proxy()
    result = {
        'url': url,
        'proxy_used': proxy,
        'success': False,
        'message': ''
    }
    
    try:
        conn_kwargs = {}
        if proxy:
            conn_kwargs['proxy'] = proxy
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, **conn_kwargs) as response:
                result['status_code'] = response.status
                result['success'] = 200 <= response.status < 300
                result['message'] = 'Connection successful' if result['success'] else f'HTTP error: {response.status}'
    except Exception as e:
        result['message'] = f'Connection error: {str(e)}'
    
    return result

def apply_proxy_to_session(session: aiohttp.ClientSession) -> aiohttp.ClientSession:
    """
    将代理设置应用到现有的aiohttp会话
    
    Args:
        session: 现有的aiohttp会话
        
    Returns:
        应用了代理的会话
    """
    proxy = get_aiohttp_proxy()
    if proxy:
        session._connector._proxy = proxy
    return session 