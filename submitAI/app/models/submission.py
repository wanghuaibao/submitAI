from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class SubmissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class DirectoryWebsite(BaseModel):
    name: str
    url: HttpUrl
    category: Optional[str] = None
    description: Optional[str] = None

class SubmissionRequest(BaseModel):
    product_name: str = Field(..., description="产品名称")
    product_url: HttpUrl = Field(..., description="产品网址")
    product_description: str = Field(..., description="产品描述")
    product_category: Optional[str] = Field(None, description="产品分类")
    screenshot_path: Optional[str] = Field(None, description="产品截图路径")
    email: str = Field(..., description="用于注册和验证的邮箱")
    email_password: Optional[str] = Field(None, description="邮箱密码（用于验证）")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API密钥")
    claude_api_key: Optional[str] = Field(None, description="Claude API密钥")
    target_directories: List[str] = Field(..., description="目标目录网站列表")

class SubmissionResult(BaseModel):
    directory_url: str
    has_submission_form: bool
    is_success: bool
    short_reason_if_failed: Optional[str] = None
    submitted_at: datetime

class SubmissionTask(BaseModel):
    id: str
    user_id: int
    status: SubmissionStatus
    request: SubmissionRequest
    results: List[SubmissionResult] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True 