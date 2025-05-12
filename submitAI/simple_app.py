from fastapi import FastAPI, Request, Form, File, UploadFile, Depends, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uvicorn
import os
import secrets
import uuid
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional, Union
from pydantic import BaseModel
import jwt
from passlib.context import CryptContext
import asyncio
from fastapi import BackgroundTasks

# 确保目录存在
os.makedirs("app/web/static", exist_ok=True)
os.makedirs("app/web/static/css", exist_ok=True)
os.makedirs("app/web/static/js", exist_ok=True)
os.makedirs("app/web/static/img", exist_ok=True)
os.makedirs("app/web/templates", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("submissions", exist_ok=True)
os.makedirs("users", exist_ok=True)  # 新增用户目录

# 创建应用
app = FastAPI(title="自动化产品提交工具 - 简化版")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 设置静态文件目录
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# 设置模板目录
templates = Jinja2Templates(directory="app/web/templates")

# 模拟存储
submissions = {}
users = {}  # 用户存储

# 安全相关配置
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 密码哈希工具
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login/access-token", auto_error=False)

# 模型定义
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str

class UserInDB(User):
    hashed_password: str

# 用户相关函数
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(email: str):
    # 从文件加载用户
    user_path = Path(f"users/{email}.json")
    if not user_path.exists():
        return None
    try:
        with open(user_path, "r") as f:
            user_data = json.load(f)
            return UserInDB(**user_data)
    except:
        return None

def authenticate_user(email: str, password: str):
    user = get_user(email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)):
    if token is None:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        token_data = TokenData(email=email)
    except jwt.PyJWTError:
        return None
        
    user = get_user(email=token_data.email)
    if user is None:
        return None
    return user

async def get_current_active_user(current_user: Optional[User] = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# API路由
@app.post("/api/users/login/access-token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/users/register", response_model=User)
async def register_user(user: UserCreate):
    if get_user(user.email):
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user.password)
    
    user_in_db = UserInDB(
        id=user_id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        hashed_password=hashed_password
    )
    
    # 保存用户到文件
    with open(f"users/{user.email}.json", "w") as f:
        json.dump(user_in_db.dict(), f, indent=2)
    
    return User(
        id=user_id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser
    )

@app.get("/api/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.get("/api/submissions/list")
async def list_submissions_api(current_user: User = Depends(get_current_active_user)):
    # 从文件加载所有提交
    all_submissions = []
    for file in Path("submissions").glob("*.json"):
        with open(file, "r") as f:
            submission = json.load(f)
            all_submissions.append(submission)
    
    return all_submissions

@app.get("/api/submissions/{submission_id}")
async def get_submission(submission_id: str, current_user: User = Depends(get_current_active_user)):
    # 从文件加载提交
    try:
        with open(f"submissions/{submission_id}.json", "r") as f:
            submission = json.load(f)
    except:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    return submission

# 保护路由，需要登录的页面
def login_required(page_name: str = ""):
    async def inner(request: Request, current_user: Optional[User] = Depends(get_current_user)):
        if not current_user:
            # 对于API路由返回401
            if request.url.path.startswith("/api/"):
                raise HTTPException(status_code=401, detail="Not authenticated")
            # 对于页面路由重定向到登录页
            return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)
        return templates.TemplateResponse(
            f"{page_name}.html",
            {"request": request, "title": page_name.replace("_", " ").title(), "user": current_user}
        )
    return inner

# 页面路由
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    """首页"""
    return templates.TemplateResponse("index.html", {"request": request, "title": "首页", "user": current_user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: Optional[str] = None, current_user: Optional[User] = Depends(get_current_user)):
    """登录页面"""
    # 如果用户已登录，重定向到首页或指定的页面
    if current_user:
        return RedirectResponse(url=next or "/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "title": "登录", "next": next})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    """注册页面"""
    # 如果用户已登录，重定向到首页
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "title": "注册"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    """控制面板页面 - 需要登录"""
    if not current_user:
        return RedirectResponse(url="/login?next=/dashboard", status_code=303)
    return templates.TemplateResponse("dashboard.html", {"request": request, "title": "控制面板", "user": current_user})

@app.get("/new-submission", response_class=HTMLResponse)
async def new_submission_form(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    """提交表单页面 - 需要登录"""
    if not current_user:
        return RedirectResponse(url="/login?next=/new-submission", status_code=303)
    return templates.TemplateResponse("new_submission.html", {"request": request, "title": "新建提交", "user": current_user})

@app.post("/submit")
async def submit(
    request: Request,
    product_name: str = Form(...),
    product_url: str = Form(...),
    product_description: str = Form(...),
    product_category: str = Form(None),
    target_directories: str = Form(...),
    email: str = Form(...),
    current_user: User = Depends(get_current_active_user)
):
    """处理提交 - 需要登录"""
    # 创建提交ID
    submission_id = str(uuid.uuid4())
    
    # 解析目标目录列表
    directories = [d.strip() for d in target_directories.split(',') if d.strip()]
    
    # 创建提交对象
    submission = {
        "id": submission_id,
        "user_id": current_user.id,
        "user_email": current_user.email,
        "product_name": product_name,
        "product_url": product_url,
        "product_description": product_description,
        "product_category": product_category,
        "target_directories": directories,
        "email": email,
        "created_at": datetime.now().isoformat(),
        "status": "pending",  # 初始状态为待处理
        "results": []
    }
    
    # 为每个目标目录创建一个模拟结果
    for directory in directories:
        result = {
            "directory_url": directory,
            "has_submission_form": True,
            "is_success": None,  # 尚未提交
            "short_reason_if_failed": "",
            "submitted_at": None  # 尚未提交时间
        }
        submission["results"].append(result)
    
    # 存储提交
    submissions[submission_id] = submission
    
    # 保存到文件
    with open(f"submissions/{submission_id}.json", "w") as f:
        json.dump(submission, f, indent=2)
    
    # API请求返回JSON，Web表单提交重定向到仪表盘
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JSONResponse(status_code=201, content={"id": submission_id})
    else:
        return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/submissions", response_class=HTMLResponse)
async def list_submissions(request: Request, current_user: Optional[User] = Depends(get_current_user)):
    """提交列表页面 - 需要登录"""
    if not current_user:
        return RedirectResponse(url="/login?next=/submissions", status_code=303)
    
    # 从文件加载所有提交
    all_submissions = []
    for file in Path("submissions").glob("*.json"):
        with open(file, "r") as f:
            submission = json.load(f)
            all_submissions.append(submission)
    
    return templates.TemplateResponse(
        "submissions.html", 
        {"request": request, "title": "我的提交", "submissions": all_submissions, "user": current_user}
    )

@app.get("/submission/{submission_id}", response_class=HTMLResponse)
async def view_submission(request: Request, submission_id: str, current_user: Optional[User] = Depends(get_current_user)):
    """查看提交详情 - 需要登录"""
    if not current_user:
        return RedirectResponse(url=f"/login?next=/submission/{submission_id}", status_code=303)
    
    # 从文件加载提交
    try:
        with open(f"submissions/{submission_id}.json", "r") as f:
            submission = json.load(f)
    except:
        submission = None
    
    if not submission:
        return RedirectResponse(url="/submissions")
    
    return templates.TemplateResponse(
        "submission_detail.html", 
        {"request": request, "title": "提交详情", "submission": submission, "user": current_user}
    )

@app.get("/logout")
async def logout():
    """登出 - 清除会话"""
    response = RedirectResponse(url="/", status_code=303)
    return response

# 处理404错误
@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return templates.TemplateResponse(
        "404.html", 
        {"request": request, "title": "页面未找到"}
    )

# 创建 404 页面
if not os.path.exists("app/web/templates/404.html"):
    with open("app/web/templates/404.html", "w") as f:
        f.write("""{% extends "base.html" %}

{% block content %}
<div class="flex flex-col items-center justify-center py-12">
    <div class="text-9xl font-bold text-indigo-600">404</div>
    <h1 class="mt-4 text-3xl font-bold text-gray-900">页面未找到</h1>
    <p class="mt-2 text-lg text-gray-600">您访问的页面不存在或已被移除。</p>
    <a href="/" class="mt-8 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
        返回首页
    </a>
</div>
{% endblock %}
""")

# 创建静态资源目录和CSS文件
if not os.path.exists("app/web/static/css/main.css"):
    with open("app/web/static/css/main.css", "w") as f:
        f.write("""
/* 全局样式 */
:root {
    --primary-color: #4f46e5;
    --primary-hover: #4338ca;
    --secondary-color: #f3f4f6;
    --text-color: #111827;
    --text-muted: #6b7280;
    --success-color: #10b981;
    --warning-color: #f59e0b;
    --danger-color: #ef4444;
    --border-color: #e5e7eb;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: var(--text-color);
    line-height: 1.5;
}

/* 导航栏激活状态 */
.nav-active {
    color: var(--primary-color) !important;
    border-bottom-color: var(--primary-color) !important;
}

/* 自定义表单样式 */
.form-input {
    @apply mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring focus:ring-indigo-500 focus:ring-opacity-50;
}

.btn {
    @apply inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2;
}

.btn-primary {
    @apply text-white bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500;
}

.btn-secondary {
    @apply text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:ring-indigo-500;
}

/* 卡片、标题和其他UI元素的增强样式 */
.card {
    @apply bg-white rounded-lg shadow-md overflow-hidden;
}

.card-header {
    @apply px-4 py-5 sm:px-6 bg-gray-50 border-b border-gray-200;
}

.card-body {
    @apply px-4 py-5 sm:p-6;
}

/* 动画 */
.fade-in {
    animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* 响应式调整 */
@media (max-width: 640px) {
    .card {
        @apply rounded-none shadow-sm;
    }
}
        """)

# 定义后台处理函数
async def process_submission_background(submission_id: str):
    """在后台处理提交请求"""
    try:
        # 读取提交信息
        with open(f"submissions/{submission_id}.json", "r", encoding="utf-8") as f:
            submission = json.load(f)
            
        # 模拟处理过程
        await asyncio.sleep(5)  # 等待5秒
        
        # 更新所有结果为成功
        for result in submission["results"]:
            result["is_success"] = True
            result["submitted_at"] = datetime.now().isoformat()
        
        # 更新状态为已完成
        submission["status"] = "completed"
        
        # 保存更新后的提交
        with open(f"submissions/{submission_id}.json", "w", encoding="utf-8") as f:
            json.dump(submission, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"处理提交 {submission_id} 失败: {str(e)}")
        
        # 尝试更新状态为失败
        try:
            with open(f"submissions/{submission_id}.json", "r", encoding="utf-8") as f:
                submission = json.load(f)
            
            submission["status"] = "failed"
            
            for result in submission["results"]:
                if result["is_success"] is None:
                    result["is_success"] = False
                    result["submitted_at"] = datetime.now().isoformat()
                    result["short_reason_if_failed"] = "处理过程中出现错误"
            
            with open(f"submissions/{submission_id}.json", "w", encoding="utf-8") as f:
                json.dump(submission, f, indent=2, ensure_ascii=False)
        except Exception as save_ex:
            print(f"更新提交状态失败: {str(save_ex)}")

@app.post("/start-submission/{submission_id}")
async def start_submission(submission_id: str, background_tasks: BackgroundTasks):
    """开始处理提交"""
    try:
        # 读取提交
        with open(f"submissions/{submission_id}.json", "r", encoding="utf-8") as f:
            submission = json.load(f)
        
        # 更新状态为处理中
        submission["status"] = "running"
        with open(f"submissions/{submission_id}.json", "w", encoding="utf-8") as f:
            json.dump(submission, f, indent=2, ensure_ascii=False)
        
        # 在后台任务中处理提交
        background_tasks.add_task(process_submission_background, submission_id)
        
        return RedirectResponse(url=f"/submission/{submission_id}", status_code=303)
    except Exception as e:
        print(f"开始提交失败: {str(e)}")
        return RedirectResponse(url="/submissions", status_code=303)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 