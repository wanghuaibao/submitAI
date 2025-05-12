from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, List
from app.models.user import User
from app.api.deps import get_current_active_user
from app.models.submission import SubmissionTask

# 导入submissions.py中定义的模拟数据库
from app.api.endpoints.submissions import submission_tasks

router = APIRouter()

@router.get("/status/{task_id}")
def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    获取任务状态
    """
    task = submission_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="没有权限访问该任务")
    
    return {
        "task_id": task.id,
        "status": task.status,
        "completed_directories": len(task.results),
        "total_directories": len(task.request.target_directories),
        "success_count": sum(1 for result in task.results if result.is_success),
        "failed_count": sum(1 for result in task.results if not result.is_success),
    }

@router.delete("/{task_id}")
def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    取消任务
    """
    task = submission_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务未找到")
    
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="没有权限访问该任务")
    
    # 在真实实现中，这里应该发送取消信号给任务处理器
    
    return {"status": "success", "message": "任务已取消"} 