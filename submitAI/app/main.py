import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# 创建API和Web路由
from app.api.router import router as api_router
from app.web.router import router as web_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保静态目录存在
os.makedirs("app/web/static", exist_ok=True)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# 包含API路由
app.include_router(api_router, prefix="/api")

# 包含Web路由
app.include_router(web_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 