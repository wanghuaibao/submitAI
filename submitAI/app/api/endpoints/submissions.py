from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Any, List, Optional
import uuid
from datetime import datetime
import os
from app.models.user import User
from app.api.deps import get_current_active_user
from app.models.submission import SubmissionRequest, SubmissionTask, SubmissionResult, SubmissionStatus
from app.services.submit_service import create_submission_task

router = APIRouter()

# 模拟数据库存储
submission_tasks = {}

@router.post("/create", response_model=SubmissionTask)
async def create_submission(
    product_name: str = Form(...),
    product_url: str = Form(...),
    product_description: str = Form(...),
    product_category: Optional[str] = Form(None),
    email: str = Form(...),
    email_password: Optional[str] = Form(None),
    openai_api_key: Optional[str] = Form(None),
    claude_api_key: Optional[str] = Form(None),
    target_directories: List[str] = Form(...),
    screenshot: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    创建新的提交任务
    """
    # 保存截图文件（如果有）
    screenshot_path = None
    if screenshot:
        # 确保目录存在
        os.makedirs("uploads", exist_ok=True)
        
        # 构建文件路径
        file_extension = os.path.splitext(screenshot.filename)[1]
        screenshot_path = f"uploads/{uuid.uuid4()}{file_extension}"
        
        # 保存文件
        with open(screenshot_path, "wb") as f:
            content = await screenshot.read()
            f.write(content)
    
    # 构造提交请求
    submission_request = SubmissionRequest(
        product_name=product_name,
        product_url=product_url,
        product_description=product_description,
        product_category=product_category,
        screenshot_path=screenshot_path,
        email=email,
        email_password=email_password,
        openai_api_key=openai_api_key,
        claude_api_key=claude_api_key,
        target_directories=target_directories
    )
    
    # 创建任务
    task_id = str(uuid.uuid4())
    now = datetime.now()
    task = SubmissionTask(
        id=task_id,
        user_id=current_user.id,
        status=SubmissionStatus.PENDING,
        request=submission_request,
        created_at=now,
        updated_at=now
    )
    
    # 存储任务
    submission_tasks[task_id] = task
    
    # 启动异步任务
    await create_submission_task(task)
    
    return task

@router.get("/list", response_model=List[SubmissionTask])
def list_submissions(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    列出当前用户的所有提交任务
    """
    user_tasks = [task for task in submission_tasks.values() if task.user_id == current_user.id]
    return user_tasks

@router.get("/{task_id}", response_model=SubmissionTask)
def get_submission(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    获取特定提交任务的详细信息
    """
    task = submission_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="没有权限访问该任务")
    
    return task 