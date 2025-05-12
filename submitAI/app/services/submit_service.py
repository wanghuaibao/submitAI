import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.models.submission import SubmissionTask, SubmissionResult, SubmissionStatus
from app.core.config import settings

# 导入原始提交工具代码
from submit_a_tool import DirectorySubmitter

async def create_submission_task(task: SubmissionTask) -> None:
    """
    创建并启动提交任务
    """
    # 更新任务状态
    task.status = SubmissionStatus.RUNNING
    task.updated_at = datetime.now()
    
    # 创建异步任务运行提交
    asyncio.create_task(run_submission_task(task))

async def run_submission_task(task: SubmissionTask) -> None:
    """
    运行提交任务
    """
    try:
        # 创建处理目录
        os.makedirs("inputs", exist_ok=True)
        
        # 准备站点信息
        site_info = f"""
Name: {task.request.product_name}
Website: {task.request.product_url}
Description: {task.request.product_description}
Category: {task.request.product_category or ""}
"""

        # 将站点信息写入文件
        site_info_path = f"inputs/site_info_{task.id}.txt"
        with open(site_info_path, "w") as f:
            f.write(site_info)
            
        # 设置环境变量
        if task.request.openai_api_key:
            os.environ["OPENAI_API_KEY"] = task.request.openai_api_key
        elif settings.DEFAULT_OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.DEFAULT_OPENAI_API_KEY
            
        if task.request.claude_api_key:
            os.environ["CLAUDE_API_KEY"] = task.request.claude_api_key
        elif settings.DEFAULT_CLAUDE_API_KEY:
            os.environ["CLAUDE_API_KEY"] = settings.DEFAULT_CLAUDE_API_KEY
            
        if task.request.email_password:
            os.environ["GMAIL_PASSWORD"] = task.request.email_password
            
        os.environ["GMAIL_ADDRESS"] = task.request.email
        os.environ["SUBMIT_ACCOUNT_PASSWORD"] = "SubmitPassword123"  # 默认密码
            
        # 初始化提交器
        directory_submitter = DirectorySubmitter()
        
        # 对每个目标目录网站进行提交
        for directory_url in task.request.target_directories:
            try:
                # 运行提交
                result = await directory_submitter.submit_single_directory(
                    directory_url,
                    site_info,
                    task.request.email
                )
                
                # 创建结果对象
                submission_result = SubmissionResult(
                    directory_url=directory_url,
                    has_submission_form=result.has_submission_form,
                    is_success=result.is_success,
                    short_reason_if_failed=result.short_reason_if_failed,
                    submitted_at=datetime.now()
                )
                
                # 添加到任务结果
                task.results.append(submission_result)
                task.updated_at = datetime.now()
                
            except Exception as e:
                # 处理错误
                submission_result = SubmissionResult(
                    directory_url=directory_url,
                    has_submission_form=False,
                    is_success=False,
                    short_reason_if_failed=f"Error: {str(e)[:100]}",
                    submitted_at=datetime.now()
                )
                task.results.append(submission_result)
                task.updated_at = datetime.now()
        
        # 完成任务
        task.status = SubmissionStatus.COMPLETED
        task.completed_at = datetime.now()
        task.updated_at = datetime.now()
        
    except Exception as e:
        # 任务失败
        task.status = SubmissionStatus.FAILED
        task.updated_at = datetime.now()
        
        # 可以在这里添加错误日志
        print(f"任务失败: {str(e)}") 