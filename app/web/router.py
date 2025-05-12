from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path

# 设置模板目录
base_dir = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """网站首页"""
    return templates.TemplateResponse("index.html", {"request": request, "user": None})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """控制面板"""
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": None})

@router.get("/new-submission", response_class=HTMLResponse)
async def new_submission(request: Request):
    """创建提交页面"""
    return templates.TemplateResponse("new_submission.html", {"request": request, "user": None})

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request, "user": None})

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """注册页面"""
    return templates.TemplateResponse("register.html", {"request": request, "user": None}) 