from fastapi import APIRouter
from app.api.endpoints import submissions, users, tasks

router = APIRouter()

router.include_router(users.router, prefix="/users", tags=["用户"])
router.include_router(submissions.router, prefix="/submissions", tags=["提交"])
router.include_router(tasks.router, prefix="/tasks", tags=["任务"]) 