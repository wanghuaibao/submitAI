import json
import aiohttp
import os
from typing import List, Dict, Any, Optional
from .proxy_helper import get_aiohttp_proxy

class OpenAIClient:
    """OpenAI API客户端，用于调用AI完成表单填写和提交"""
    
    def __init__(self, api_key: str):
        """初始化OpenAI API客户端
        
        Args:
            api_key: OpenAI API密钥
        """
        self.api_key = api_key
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-3.5-turbo"
        
    async def chat_completion(self, 
                            messages: List[Dict[str, str]], 
                            temperature: float = 0.7, 
                            max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """发送聊天完成请求到OpenAI API
        
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
        # 将表单HTML截断到合理的长度，避免超出token限制
        max_html_length = 6000  # 降低为6000字符，减少token用量
        if len(form_html) > max_html_length:
            print(f"表单HTML过长 ({len(form_html)} 字符)，截断至 {max_html_length} 字符")
            form_html = form_html[:max_html_length] + "\n... [内容已截断] ..."
            
        # 将表单字段转换为JSON字符串
        fields_json = json.dumps(form_fields, indent=2, ensure_ascii=False)
        
        # 限制字段内容长度，避免大文本字段占用太多token
        if len(fields_json) > 2000:
            print(f"表单字段内容过长 ({len(fields_json)} 字符)，缩减内容")
            # 创建精简版字段
            simplified_fields = {}
            for k, v in form_fields.items():
                if isinstance(v, str) and len(v) > 200:
                    simplified_fields[k] = v[:200] + "... [内容已截断]"
                else:
                    simplified_fields[k] = v
            fields_json = json.dumps(simplified_fields, indent=2, ensure_ascii=False)
        
        # 构建提示词 - 增强版
        prompt = (
            "你是一名专业的AI表单分析专家。你的任务是详细分析下面的HTML表单结构，并提供精确的字段映射策略。\n\n"
            "HTML表单：\n```html\n" + form_html + "\n```\n\n"
            "我们的产品信息：\n```json\n" + fields_json + "\n```\n\n"
            "请执行以下步骤：\n"
            "1. 首先识别表单中的所有输入字段，包括类型、是否必填、ID、名称等属性\n"
            "2. 分析每个字段的占位符、标签文本和上下文，理解其预期输入内容\n"
            "3. 找出表单字段与我们产品信息之间的最佳匹配关系\n"
            "4. 特别注意特殊输入类型，如下拉选择框、复选框、单选按钮、文件上传等\n"
            "5. 对于没有直接匹配的字段，提供最佳推荐填充策略\n\n"
            "返回一个JSON对象，包含以下内容：\n"
            "{\n"
            '  "form_analysis": {\n'
            '    "form_type": "提交AI工具/联系表单/注册表单等",\n'
            '    "total_fields": 字段总数,\n'
            '    "required_fields": 必填字段数,\n'
            '    "special_requirements": "任何特殊要求或限制"\n'
            '  },\n'
            '  "field_mappings": [\n'
            '    {\n'
            '      "form_field": "表单字段ID或名称",\n'
            '      "our_field": "匹配的我们字段名",\n'
            '      "type": "字段类型(text/select/checkbox/radio/file等)",\n'
            '      "required": true/false,\n'
            '      "mapping_confidence": "high/medium/low",\n'
            '      "recommendation": "如何填写的建议"\n'
            '    },\n'
            '    ...\n'
            '  ],\n'
            '  "unmapped_form_fields": ["表单中未能映射的字段列表"],\n'
            '  "unmapped_our_fields": ["我们的信息中未使用的字段"],\n'
            '  "filling_strategy": "总体填表策略和建议",\n'
            '  "special_instructions": "任何特殊处理说明"\n'
            "}\n\n"
            "确保你的分析尽可能详细和准确，这将直接用于自动填写表单。"
        )
        
        # 调用API
        messages = [
            {"role": "system", "content": "你是一个专业的网页分析助手，擅长分析HTML表单结构并提供字段映射。你总是尽可能精确地分析，不仅基于字段名称，还会考虑标签文本、占位符、字段类型和上下文来确定最佳映射。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.chat_completion(messages, temperature=0.2, max_tokens=2000) # 降低为2000
            
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
            except Exception as e:
                # 如果无法解析为JSON，返回原始文本和错误消息
                return {"error": f"无法解析AI响应: {str(e)}", "raw_response": ai_response}
        except Exception as e:
            # API调用错误处理
            return {"error": f"API调用失败: {str(e)}"}
    
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
        max_html_length = 5000  # 更加严格地限制HTML长度
        if len(form_html) > max_html_length:
            print(f"表单HTML过长 ({len(form_html)} 字符)，截断至 {max_html_length} 字符")
            form_html = form_html[:max_html_length] + "\n... [内容已截断] ..."
        
        # 将表单字段转换为JSON字符串，同时限制大文本字段
        simplified_fields = {}
        for k, v in form_fields.items():
            if isinstance(v, str) and len(v) > 150:  # 更严格地限制字段长度
                simplified_fields[k] = v[:150] + "... [内容已截断]"
            else:
                simplified_fields[k] = v
        
        fields_json = json.dumps(simplified_fields, indent=2, ensure_ascii=False)
        
        # 构建提示词 - 优化版
        prompt = (
            f"为以下URL的表单制定填写计划: {target_url}\n\n"
            f"表单HTML片段:\n```html\n{form_html}\n```\n\n"
            f"产品信息:\n```json\n{fields_json}\n```\n\n"
            "提供一个详细的表单填写计划，包括:\n"
            "1. 每个表单字段的匹配策略\n"
            "2. 特殊字段(下拉菜单、单选、多选等)的处理方法\n"
            "3. 建议的填写值\n\n"
            "以JSON格式返回，包含:\n"
            "- field_mappings: 字段ID/名称到填写值的映射\n"
            "- special_instructions: 任何特殊处理说明\n"
            "- submission_strategy: 提交表单的建议"
        )
        
        # 调用API
        messages = [
            {"role": "system", "content": "你是一个专业的网页自动化助手，擅长分析HTML表单结构并生成精确的填表指令。你的输出必须是机器可读的JSON格式。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.chat_completion(messages, temperature=0.2, max_tokens=2000)  # 降低为2000
            
            # 获取响应
            ai_response = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return ai_response
        except Exception as e:
            # 处理API调用失败
            return f"{{\"error\": \"API调用失败: {str(e)}\"}}"
    
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
        
        # 提取目标网站的域名和名称
        import re
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', target_url)
        website_domain = domain_match.group(1) if domain_match else target_url
        website_name = website_domain.split('.')[0].capitalize()
        
        # 构建提示词 - 增强版
        prompt = (
            f"你是AI工具提交专家，特别擅长针对不同目录网站优化提交内容。需要将我们的AI工具提交到以下网站：{target_url} ({website_name})。\n\n"
            f"我的产品详细信息如下：\n{fields_text}\n\n"
            f"基于对{website_name}网站的了解，请针对该平台的特点和受众，生成优化的提交内容，包括：\n\n"
            "1. 简短描述(150字以内)：清晰简洁，突出卖点，让用户立即理解工具价值\n"
            f"2. 详细描述：为{website_name}平台量身定制，包含以下要素：\n"
            "   - 开场：引人注目的介绍\n"
            "   - 主要功能：以用户视角描述核心功能\n"
            "   - 使用场景：具体实用案例\n"
            "   - 差异化优势：与竞品相比的独特之处\n"
            "   - 技术亮点：适当提及底层技术(如适用)\n"
            "   - 价格/可访问性信息：免费部分、定价模式等\n"
            "   - 号召性用语：鼓励用户尝试\n"
            f"3. 标签：5-8个最适合在{website_name}上分类和搜索的相关标签\n"
            "4. 其他需调整的字段：基于该网站特点可能需要调整的其他内容\n\n"
            "请以JSON格式返回，确保内容：\n"
            "- 风格专业但友好，避免过度营销语言\n"
            "- 突出实际价值而非夸大宣传\n"
            "- 针对该特定平台用户优化\n"
            "- 遵循现代AI工具目录的最佳实践\n"
            "- 包含结构化格式，便于阅读\n\n"
            "JSON结构应包含：short_description, detailed_description, tags, special_fields(如需)"
        )
        return prompt 