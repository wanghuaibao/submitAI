import os
import asyncio
from submitAI.openai_client import OpenAIClient

async def test_openai_client():
    # 设置API密钥
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("错误: 未设置OPENAI_API_KEY环境变量")
        return
    
    # 创建客户端
    client = OpenAIClient(api_key)
    
    # 测试聊天完成功能
    try:
        print("测试OpenAI聊天完成...")
        response = await client.chat_completion([
            {"role": "user", "content": "Hello, how are you?"}
        ])
        
        print("API响应成功:")
        print(f"模型: {response.get('model')}")
        if 'choices' in response and len(response['choices']) > 0:
            content = response['choices'][0]['message']['content']
            print(f"回复: {content[:100]}...")
        else:
            print("响应中没有有效内容")
            
    except Exception as e:
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_openai_client()) 