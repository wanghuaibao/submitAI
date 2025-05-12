import json
import aiohttp
import os
from typing import List, Dict, Any, Optional
from .proxy_helper import get_aiohttp_proxy

class GrokAIClient:
    """Grok API客户端，用于调用AI完成表单填写和提交"""
    
    def __init__(self, api_key: str):
        """初始化Grok API客户端
        
        Args:
            api_key: Grok API密钥
        """
        self.api_key = api_key
        self.api_url = "https://api.x.ai/v1/chat/completions"
        self.model = "grok-3-latest"
        
    async def chat_completion(self, 
                            messages: List[Dict[str, str]], 
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """发送聊天完成请求到Grok API
        
        Args:
            messages: 消息列表
            temperature: 温度参数，控制输出随机性
            max_tokens: 最大生成令牌数
            
        Returns:
            API响应
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "messages": messages,
            "model": self.model,
            "temperature": temperature,
            "stream": False
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        # 获取代理设置
        proxy = get_aiohttp_proxy()
        
        # 使用代理设置创建会话
        async with aiohttp.ClientSession() as session:
            # 如果有代理设置，使用代理
            conn_kwargs = {}
            if proxy:
                conn_kwargs['proxy'] = proxy
                print(f"使用代理: {proxy}")
            
            async with session.post(self.api_url, headers=headers, json=payload, **conn_kwargs) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API调用失败，状态码: {response.status}, 错误: {error_text}")
                
                result = await response.json()
                return result
    
    async def generate_submission_content(self, 
                                    form_fields: Dict[str, Any], 
                                    target_url: str) -> Dict[str, Any]:
        """生成用于网站提交的内容
        
        Args:
            form_fields: 表单字段信息
            target_url: 目标提交网址
            
        Returns:
            生成的提交内容
        """
        # 构建提示词
        prompt = self._build_submission_prompt(form_fields, target_url)
        
        # 调用API
        messages = [
            {"role": "system", "content": "你是一个专业的AI工具提交助手，帮助用户将AI工具信息提交到目录网站。"
                               "你擅长理解网站表单结构，并生成最合适的提交内容，以增加审核通过率。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(messages, temperature=0.3)
        
        # 解析响应
        ai_response = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        try:
            # 尝试解析JSON响应
            result = json.loads(ai_response)
            return result
        except:
            # 如果不是有效的JSON，返回原始文本
            return {"error": "无法解析AI响应", "raw_response": ai_response}
    
    async def analyze_submission_form(self, form_html: str, form_fields: Dict[str, Any]) -> Dict[str, Any]:
        """分析提交表单结构并匹配我们的字段
        
        Args:
            form_html: 表单HTML内容
            form_fields: 我们的表单字段
            
        Returns:
            字段映射和填写策略
        """
        # 将表单字段转换为JSON字符串
        fields_json = json.dumps(form_fields, indent=2, ensure_ascii=False)
        
        # 构建提示词
        prompt = (
            "分析下面的HTML表单，并确定如何将我们的产品信息映射到表单字段中：\n\n"
            "HTML表单：\n```html\n" + form_html + "\n```\n\n"
            "我们的产品信息：\n```json\n" + fields_json + "\n```\n\n"
            "请提供一个JSON格式的映射，包含：\n"
            "1. 表单中的每个输入字段的ID或名称\n"
            "2. 对应的我们产品信息中的字段\n"
            "3. 如何处理特殊字段（如类别选择、复选框等）\n\n"
            "返回格式示例：\n"
            "{\n"
            '  "field_mappings": [\n'
            '    {"form_field": "name", "our_field": "product_name", "type": "text"},\n'
            '    {"form_field": "category", "our_field": "product_category", "type": "select", "value_mapping": {...}}\n'
            "  ],\n"
            '  "special_instructions": "..."\n'
            "}"
        )
        
        # 调用API
        messages = [
            {"role": "system", "content": "你是一个专业的网页分析助手，擅长分析HTML表单结构并提供字段映射。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(messages, temperature=0.2)
        
        # 解析响应
        ai_response = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        try:
            # 提取JSON部分
            import re
            json_match = re.search(r'```json\n(.*?)\n```', ai_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # 尝试直接解析整个响应
                result = json.loads(ai_response)
            return result
        except:
            # 如果无法解析为JSON，返回原始文本
            return {"error": "无法解析AI响应", "raw_response": ai_response}
    
    async def generate_form_filling_instructions(self, 
                                           form_html: str, 
                                           form_fields: Dict[str, Any],
                                           target_url: str) -> str:
        """生成表单填写指令
        
        Args:
            form_html: 表单HTML内容
            form_fields: 我们的表单字段
            target_url: 目标提交网址
            
        Returns:
            表单填写指令
        """
        # 限制HTML内容长度，避免超出token限制
        limited_html = form_html[:2000]
        
        # 将表单字段转换为JSON字符串
        fields_json = json.dumps(form_fields, indent=2, ensure_ascii=False)
        
        # 构建提示词
        prompt = (
            "我需要你帮我生成一组具体的指令，用于在以下URL的表单中填写我们的产品信息：" + target_url + "\n\n"
            "表单HTML片段:\n```html\n" + limited_html + "\n```\n\n"
            "我们的产品信息:\n```json\n" + fields_json + "\n```\n\n"
            "请生成详细的步骤说明，包括:\n"
            "1. 如何找到每个相关的表单字段\n"
            "2. 应该填入什么值\n"
            "3. 如何处理下拉菜单、复选框等特殊输入\n"
            "4. 提交后可能的验证步骤\n\n"
            "格式要求：生成纯文本步骤，以编号形式列出，便于程序解析。"
        )
        
        # 调用API
        messages = [
            {"role": "system", "content": "你是一个专业的网页自动化助手，擅长生成网页填表指令。"},
            {"role": "user", "content": prompt}
        ]
        
        response = await self.chat_completion(messages, temperature=0.2)
        
        # 获取响应
        ai_response = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ai_response
    
    def _build_submission_prompt(self, form_fields: Dict[str, Any], target_url: str) -> str:
        """构建提交提示词
        
        Args:
            form_fields: 表单字段
            target_url: 目标URL
            
        Returns:
            构建的提示词
        """
        # 将表单字段转换为格式化文本
        fields_text = "\n".join([f"- {k}: {v}" for k, v in form_fields.items() if v])
        
        # 构建提示词
        prompt = (
            "我需要将AI工具提交到以下目录网站：" + target_url + "\n\n"
            "我的产品信息如下：\n" + fields_text + "\n\n"
            "请为我生成以下内容，用于提交到该目录网站：\n"
            "1. 一个优化后的简短描述（最多150字）\n"
            "2. 一个详细描述（针对该网站优化，突出工具的核心功能和价值）\n"
            "3. 适合该网站的标签（以JSON数组格式）\n"
            "4. 任何其他需要特别调整的字段\n\n"
            "请以JSON格式返回结果，包含以下字段：\n"
            "- short_description\n"
            "- detailed_description\n"
            "- tags\n"
            "- special_fields（如有需要）\n\n"
            "确保返回的内容格式符合预期，并对描述进行优化，使其更容易被该目录网站接受。"
        )
        return prompt 