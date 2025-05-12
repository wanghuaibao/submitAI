#!/usr/bin/env python3
"""
测试 OpenAI 客户端连接
"""
import os
import asyncio
import argparse
from submitAI.openai_client import OpenAIClient

async def main(api_key: str):
    """运行 OpenAI 客户端测试

    Args:
        api_key: OpenAI API 密钥
    """
    print("初始化 OpenAI 客户端...")
    client = OpenAIClient(api_key)
    
    print("发送简单的测试请求...")
    try:
        messages = [
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "你好，这是一条测试消息。请用中文回复：'OpenAI API 连接测试成功！'"}
        ]
        
        response = await client.chat_completion(messages, temperature=0.7)
        
        print("\n请求成功！")
        print("API 响应:", response)
        
        # 提取并显示助手的回复
        assistant_message = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        print("\n助手回复:", assistant_message)
        
    except Exception as e:
        print(f"请求失败，错误: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='测试 OpenAI API 连接')
    parser.add_argument('--api_key', help='OpenAI API 密钥', default=os.environ.get('OPENAI_API_KEY'))
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("错误: 未提供 OpenAI API 密钥，请通过 --api_key 参数提供或设置 OPENAI_API_KEY 环境变量")
    else:
        asyncio.run(main(args.api_key)) 