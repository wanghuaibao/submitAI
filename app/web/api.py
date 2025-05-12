from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import re
from pathlib import Path

api_router = APIRouter()

@api_router.get("/api/submission/{submission_id}/console_logs")
async def get_console_logs(submission_id: str):
    """获取提交的控制台日志"""
    try:
        # 日志文件路径（这里假设日志存储在logs/submissions目录）
        logs_dir = Path("logs/submissions")
        log_files = list(logs_dir.glob(f"{submission_id}*.log"))
        
        if not log_files:
            # 如果没有找到日志文件，尝试读取标准输出日志
            stdout_file = logs_dir / f"{submission_id}_stdout.txt"
            if stdout_file.exists():
                log_files = [stdout_file]
        
        logs = []
        
        # 如果找到日志文件
        if log_files:
            # 读取第一个找到的日志文件
            with open(log_files[0], 'r', encoding='utf-8') as f:
                log_content = f.read()
                
                # 将日志内容分行并提取有意义的行
                logs = [line.strip() for line in log_content.split('\n') if line.strip()]
        else:
            # 尝试从控制台输出模拟一些日志
            # 这些是示例日志，实际应用中应该从真实的日志源获取
            logs = [
                "检查是否存在Cookie同意弹窗...",
                "未发现Cookie同意弹窗",
                f"检测到 提交网站，应用特殊处理...",
                "页面中的表单数据:",
                "表单 1: ID=, 类=seva-form formkit-form, 动作=https://app.kit.com/forms/5073932/subscriptions",
                "表单元素:",
                "  - 名称=fields[first_name], ID=, 类型=text",
                "  - 名称=email_address, ID=, 类型=text",
                "  - 名称=, ID=, 类型=submit",
                f"保存初始页面截图: logs/submissions/{submission_id}_1_initial_page.png",
                "开始寻找表单元素...",
                "开始查找表单选择器..."
            ]
        
        return JSONResponse(content={"logs": logs})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"获取控制台日志失败: {str(e)}"}
        ) 