import asyncio
import json
import os
import uuid
import aiohttp
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from .openai_client import OpenAIClient

# 导入浏览器自动化模块
from browser_use import Browser, BrowserConfig, Agent, SubmissionResult


class SubmissionProcessor:
    """处理提交请求，并管理提交状态"""

    def __init__(self, openai_api_key: Optional[str] = None):
        """初始化提交处理器
        
        Args:
            openai_api_key: OpenAI API密钥，用于AI辅助提交
        """
        # 确保目录存在
        os.makedirs("submissions", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        os.makedirs("logs/submissions", exist_ok=True)
        
        # 初始化OpenAI客户端（如果提供了API密钥）
        self.ai_client = None
        if openai_api_key:
            self.ai_client = OpenAIClient(openai_api_key)
            
        # 初始化浏览器代理
        self.browser_agent = None
        
    async def process_submission(self, submission_id: str):
        """处理一个提交请求"""
        # 读取提交信息
        submission_path = f"submissions/{submission_id}.json"
        if not os.path.exists(submission_path):
            self._log_error(f"提交 {submission_id} 不存在")
            return False
        
        # 加载提交信息
        try:
            with open(submission_path, "r", encoding="utf-8") as f:
                submission = json.load(f)
                
            # 更新状态为处理中
            submission["status"] = "running"
            self._save_submission(submission)
            
            # 创建浏览器代理（如果还没有创建）
            if not self.browser_agent:
                try:
                    # 创建浏览器配置
                    browser_config = BrowserConfig(
                        headless=True,  # 无界面模式
                        timeout=60000,  # 60秒超时
                        device_scale_factor=1.0,
                        viewport_width=1280,
                        viewport_height=800,
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
                    )
                    
                    # 创建浏览器代理
                    self._log_info(f"正在初始化浏览器代理...")
                    self.browser_agent = Agent(browser_config=browser_config)
                    
                    # 初始化时不再调用initialize方法，留到处理每个目录前调用
                    self._log_info(f"浏览器代理创建成功")
                except Exception as e:
                    error_message = f"创建浏览器代理失败: {str(e)}"
                    self._log_error(error_message)
                    
                    # 更新状态为失败
                    submission["status"] = "failed"
                    for result in submission["results"]:
                        result["is_success"] = False
                        result["submitted_at"] = datetime.now().isoformat()
                        result["short_reason_if_failed"] = "浏览器代理创建失败"
                    
                    self._save_submission(submission)
                    return False
            
            # 处理每个目标目录前初始化浏览器
            for i, result in enumerate(submission["results"]):
                target_url = result["directory_url"]
                
                # 记录日志
                self._log_info(f"开始处理提交 {submission_id} 到 {target_url}")
                
                # 每个目标目录前重新初始化浏览器
                active_browser = False
                if self.browser_agent:
                    try:
                        self._log_info(f"正在为 {target_url} 初始化浏览器...")
                        # 先关闭可能已存在的浏览器实例
                        await self.browser_agent.close()
                        
                        # 初始化浏览器，确保每轮提交都使用新的浏览器会话
                        initialized = await self.browser_agent.initialize()
                        if initialized:
                            active_browser = True
                            self._log_info(f"浏览器初始化成功，准备提交到 {target_url}")
                        else:
                            self._log_error(f"浏览器初始化失败，无法提交到 {target_url}")
                            # 更新结果
                            result["is_success"] = False
                            result["submitted_at"] = datetime.now().isoformat()
                            result["short_reason_if_failed"] = "浏览器初始化失败"
                            self._save_submission(submission)
                            continue  # 跳过此目标
                    except Exception as e:
                        self._log_error(f"浏览器初始化异常: {str(e)}")
                        # 更新结果
                        result["is_success"] = False
                        result["submitted_at"] = datetime.now().isoformat()
                        result["short_reason_if_failed"] = f"浏览器初始化异常: {str(e)[:80]}"
                        self._save_submission(submission)
                        continue  # 跳过此目标
                
                try:
                    # 如果有AI客户端，使用智能提交
                    if self.ai_client:
                        self._log_info(f"使用AI辅助提交到 {target_url}")
                        await self._ai_submit_to_directory(submission, i)
                    else:
                        # 否则使用普通提交
                        self._log_info(f"使用普通提交到 {target_url}")
                        await self._submit_to_directory(submission, i)
                except Exception as e:
                    # 处理目标提交的错误
                    error_message = f"提交到 {target_url} 失败: {str(e)}"
                    self._log_error(error_message)
                    
                    # 更新结果
                    result["is_success"] = False
                    result["submitted_at"] = datetime.now().isoformat()
                    result["short_reason_if_failed"] = error_message[:100]
                    
                    # 保存更新后的提交
                    self._save_submission(submission)
            
            # 完成所有提交后，更新整体状态
            # 检查是否所有提交都失败了
            all_failed = all(result["is_success"] is False for result in submission["results"])
            if all_failed:
                submission["status"] = "failed"
                self._log_error(f"所有提交都失败，整体状态设为失败")
            else:
                submission["status"] = "completed"
                self._log_info(f"提交处理完成")
                
            self._save_submission(submission)
            
            return True
            
        except Exception as e:
            error_message = f"处理提交 {submission_id} 失败: {str(e)}"
            self._log_error(error_message)
            
            # 更新提交状态为失败
            try:
                with open(submission_path, "r", encoding="utf-8") as f:
                    submission = json.load(f)
                submission["status"] = "failed"
                
                # 更新所有未处理的结果
                for result in submission["results"]:
                    if result["is_success"] is None:
                        result["is_success"] = False
                        result["submitted_at"] = datetime.now().isoformat()
                        result["short_reason_if_failed"] = "处理过程中出现错误"
                
                self._save_submission(submission)
            except Exception as save_ex:
                self._log_error(f"更新提交状态失败: {str(save_ex)}")
                
            return False
        finally:
            # 保持浏览器代理活跃，不关闭
            self._log_info(f"提交 {submission_id} 处理完毕")
    
    async def _ai_submit_to_directory(self, submission: Dict[str, Any], result_index: int):
        """使用AI辅助提交到目录网站
        
        Args:
            submission: 提交信息
            result_index: 目标结果索引
        """
        # 获取目标结果对象
        result = submission["results"][result_index]
        target_url = result["directory_url"]
        
        try:
            # 记录日志
            self._log_info(f"使用AI辅助提交到 {target_url}")
            
            # 1. 获取表单字段信息
            form_fields = self._extract_form_fields(submission)
            
            # 2. 使用AI生成优化的提交内容
            optimized_content = await self.ai_client.generate_submission_content(form_fields, target_url)
            
            # 3. 记录生成的内容
            log_path = f"logs/submissions/{submission['id']}_{result_index}_content.json"
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(optimized_content, f, indent=2, ensure_ascii=False)
            
            # 4. 根据目标网站调用不同的处理逻辑
            if "neilpatel" in target_url.lower():
                submission_result = await self._submit_to_neilpatel(submission, result_index, form_fields, optimized_content)
            elif "aitoolslist" in target_url.lower():
                submission_result = await self._submit_to_aitoolslist(submission, result_index, form_fields, optimized_content)
            else:
                # 通用提交处理
                task_description = f"提交产品 {submission['product_name']} 到 {target_url}"
                
                # 5. 合并AI生成的内容和原始表单数据
                enhanced_form_fields = form_fields.copy()
                
                # 更新简短描述和详细描述（如果AI生成了）
                if isinstance(optimized_content, dict):
                    if 'short_description' in optimized_content and optimized_content['short_description']:
                        enhanced_form_fields['short_description'] = optimized_content['short_description']
                    
                    if 'detailed_description' in optimized_content and optimized_content['detailed_description']:
                        enhanced_form_fields['product_description'] = optimized_content['detailed_description']
                    
                    # 处理标签
                    if 'tags' in optimized_content and isinstance(optimized_content['tags'], list):
                        enhanced_form_fields['product_tags'] = optimized_content['tags']
                
                # 6. 执行表单提交
                submission_result = await self.browser_agent.run(
                    task_description=task_description,
                    form_data=enhanced_form_fields,
                    target_url=target_url,
                    submission_id=f"{submission['id']}_{result_index}"
                )
            
            # 7. 更新结果
            result["has_submission_form"] = submission_result.has_submission_form
            result["is_success"] = submission_result.is_success
            result["submitted_at"] = datetime.now().isoformat()
            result["ai_enhanced"] = True
            
            if not submission_result.is_success:
                result["short_reason_if_failed"] = submission_result.short_reason_if_failed
            
            # 保存更新后的提交
            self._save_submission(submission)
            
            # 记录日志
            status = "成功" if submission_result.is_success else "失败"
            self._log_info(f"完成AI辅助提交到 {target_url}: {status}")
            
        except Exception as e:
            # 处理错误
            error_message = f"AI辅助提交到 {target_url} 失败: {str(e)}"
            self._log_error(error_message)
            
            # 更新结果
            result["is_success"] = False
            result["submitted_at"] = datetime.now().isoformat()
            result["short_reason_if_failed"] = error_message[:100]  # 截断错误信息
            
            # 保存更新后的提交
            self._save_submission(submission)
    
    async def _submit_to_directory(self, submission: Dict[str, Any], result_index: int):
        """使用浏览器代理直接提交到目录网站
        
        Args:
            submission: 提交信息
            result_index: 目标结果索引
        """
        # 获取目标结果对象
        result = submission["results"][result_index]
        target_url = result["directory_url"]
        
        try:
            # 记录日志
            self._log_info(f"提交到 {target_url}")
            
            # 1. 提取表单字段
            form_fields = self._extract_form_fields(submission)
            
            # 2. 使用浏览器代理执行提交
            task_description = f"提交产品 {submission['product_name']} 到 {target_url}"
            
            submission_result = await self.browser_agent.run(
                task_description=task_description,
                form_data=form_fields,
                target_url=target_url,
                submission_id=f"{submission['id']}_{result_index}"
            )
            
            # 3. 更新结果
            result["has_submission_form"] = submission_result.has_submission_form
            result["is_success"] = submission_result.is_success
            result["submitted_at"] = datetime.now().isoformat()
            
            if not submission_result.is_success:
                result["short_reason_if_failed"] = submission_result.short_reason_if_failed
            
            # 保存更新后的提交
            self._save_submission(submission)
            
            # 记录日志
            status = "成功" if submission_result.is_success else "失败"
            self._log_info(f"完成提交到 {target_url}: {status}")
            
        except Exception as e:
            # 处理错误
            error_message = f"提交到 {target_url} 失败: {str(e)}"
            self._log_error(error_message)
            
            # 更新结果
            result["is_success"] = False
            result["submitted_at"] = datetime.now().isoformat()
            result["short_reason_if_failed"] = error_message[:100]  # 截断错误信息
            
            # 保存更新后的提交
            self._save_submission(submission)
    
    async def shutdown(self):
        """关闭处理器并释放资源"""
        if self.browser_agent:
            try:
                await self.browser_agent.close()
                self._log_info("浏览器代理已关闭")
            except Exception as e:
                self._log_error(f"关闭浏览器代理失败: {str(e)}")
            finally:
                self.browser_agent = None
        return True
    
    def _extract_form_fields(self, submission: Dict[str, Any]) -> Dict[str, Any]:
        """从提交信息中提取表单字段
        
        Args:
            submission: 提交信息
            
        Returns:
            表单字段
        """
        # 创建基本的表单字段
        form_fields = {
            "product_name": submission.get("product_name", ""),
            "product_url": submission.get("product_url", ""),
            "short_description": submission.get("short_description", ""),
            "product_description": submission.get("product_description", ""),
            "product_category": submission.get("product_category", ""),
            "pricing_model": submission.get("pricing_model", ""),
            "email": submission.get("email", ""),
            "logo_path": submission.get("logo_path", ""),
            "screenshot_path": submission.get("screenshot_path", "")
        }
        
        # 处理标签
        if "product_tags" in submission and submission["product_tags"]:
            if isinstance(submission["product_tags"], list):
                form_fields["product_tags"] = submission["product_tags"]
            else:
                form_fields["product_tags"] = submission["product_tags"].split(",")
        
        return form_fields
    
    def _save_submission(self, submission):
        """保存提交信息到文件"""
        try:
            with open(f"submissions/{submission['id']}.json", "w", encoding="utf-8") as f:
                json.dump(submission, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log_error(f"保存提交 {submission['id']} 失败: {str(e)}")
    
    def _log_info(self, message):
        """记录信息日志"""
        timestamp = datetime.now().isoformat()
        print(f"[INFO] {timestamp}: {message}")
        self._append_log("info", message)
    
    def _log_error(self, message):
        """记录错误日志"""
        timestamp = datetime.now().isoformat()
        print(f"[ERROR] {timestamp}: {message}")
        self._append_log("error", message)
    
    def _append_log(self, level, message):
        """添加日志到日志文件"""
        log_file = f"logs/submitter_{datetime.now().strftime('%Y-%m-%d')}.log"
        try:
            # 确保日志目录存在
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            with open(log_file, "a", encoding="utf-8") as f:
                timestamp = datetime.now().isoformat()
                f.write(f"[{level.upper()}] {timestamp}: {message}\n")
        except:
            # 忽略日志写入错误
            pass
    
    async def _submit_to_neilpatel(self, submission: Dict[str, Any], result_index: int, 
                           form_fields: Dict[str, Any], optimized_content: Dict[str, Any]) -> SubmissionResult:
        """提交到Neil Patel AI Tools目录
        
        Args:
            submission: 提交信息
            result_index: 结果索引
            form_fields: 基础表单字段
            optimized_content: AI优化的内容
            
        Returns:
            提交结果
        """
        target_url = submission["results"][result_index]["directory_url"]
        self._log_info(f"使用专用逻辑提交到Neil Patel AI Tools目录: {target_url}")
        
        # 创建浏览器代理（如果还没有）
        if not self.browser_agent:
            # 创建浏览器配置
            browser_config = BrowserConfig(
                headless=True,  # 无界面模式
                timeout=60000,  # 60秒超时
                viewport_width=1280,
                viewport_height=800
            )
            
            # 创建浏览器代理
            self.browser_agent = Agent(browser_config=browser_config)
        
        # 1. 构建Neil Patel专用表单数据
        np_form_fields = {
            "tool_name": form_fields["product_name"],
            "tool_url": form_fields["product_url"],
            "tool_description": optimized_content.get("detailed_description", form_fields["product_description"]),
            "tool_short_description": optimized_content.get("short_description", form_fields["short_description"]),
            "tool_categories": form_fields["product_category"],
            "pricing_type": self._map_pricing_model(form_fields["pricing_model"]),
            "email": form_fields["email"],
            "logo_path": form_fields["logo_path"],
            "screenshot_path": form_fields["screenshot_path"]
        }
        
        # 处理标签
        if "tags" in optimized_content and isinstance(optimized_content["tags"], list):
            np_form_fields["tool_tags"] = ",".join(optimized_content["tags"])
        elif "product_tags" in form_fields:
            if isinstance(form_fields["product_tags"], list):
                np_form_fields["tool_tags"] = ",".join(form_fields["product_tags"])
            else:
                np_form_fields["tool_tags"] = form_fields["product_tags"]
        
        # 2. 执行表单提交
        task_description = f"提交产品 {submission['product_name']} 到 Neil Patel AI Tools目录"
        submission_result = await self.browser_agent.run(
            task_description=task_description,
            form_data=np_form_fields,
            target_url=target_url,
            submission_id=f"{submission['id']}_{result_index}"
        )
        
        return submission_result
    
    async def _submit_to_aitoolslist(self, submission: Dict[str, Any], result_index: int, 
                             form_fields: Dict[str, Any], optimized_content: Dict[str, Any]) -> SubmissionResult:
        """提交到AI Tools List目录
        
        Args:
            submission: 提交信息
            result_index: 结果索引
            form_fields: 基础表单字段
            optimized_content: AI优化的内容
            
        Returns:
            提交结果
        """
        target_url = submission["results"][result_index]["directory_url"]
        self._log_info(f"使用专用逻辑提交到AI Tools List目录: {target_url}")
        
        # 创建浏览器代理（如果还没有）
        if not self.browser_agent:
            # 创建浏览器配置
            browser_config = BrowserConfig(
                headless=True,  # 无界面模式
                timeout=60000,  # 60秒超时
                viewport_width=1280,
                viewport_height=800
            )
            
            # 创建浏览器代理
            self.browser_agent = Agent(browser_config=browser_config)
        
        # 1. 构建AI Tools List专用表单数据
        atl_form_fields = {
            "tool_name": form_fields["product_name"],
            "tool_website": form_fields["product_url"],
            "description": optimized_content.get("detailed_description", form_fields["product_description"]),
            "short_description": optimized_content.get("short_description", form_fields["short_description"]),
            "category": form_fields["product_category"],
            "pricing": self._map_pricing_model(form_fields["pricing_model"]),
            "contact_email": form_fields["email"],
            "logo_path": form_fields["logo_path"],
            "screenshot_path": form_fields["screenshot_path"]
        }
        
        # 处理标签/关键词
        if "tags" in optimized_content and isinstance(optimized_content["tags"], list):
            atl_form_fields["keywords"] = ",".join(optimized_content["tags"][:5])  # 限制为5个关键词
        elif "product_tags" in form_fields:
            if isinstance(form_fields["product_tags"], list):
                atl_form_fields["keywords"] = ",".join(form_fields["product_tags"][:5])
            else:
                atl_form_fields["keywords"] = form_fields["product_tags"]
        
        # 2. 执行表单提交
        task_description = f"提交产品 {submission['product_name']} 到 AI Tools List目录"
        submission_result = await self.browser_agent.run(
            task_description=task_description,
            form_data=atl_form_fields,
            target_url=target_url,
            submission_id=f"{submission['id']}_{result_index}"
        )
        
        return submission_result
    
    def _map_pricing_model(self, pricing_model: str) -> str:
        """映射定价模型到目标网站可接受的值
        
        Args:
            pricing_model: 原始定价模型
            
        Returns:
            映射后的定价模型
        """
        pricing_map = {
            "free": "Free",
            "freemium": "Freemium",
            "paid": "Paid",
            "subscription": "Subscription",
            "one_time": "One-time"
        }
        
        return pricing_map.get(pricing_model.lower(), pricing_model) 