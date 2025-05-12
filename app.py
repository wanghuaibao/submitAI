import uvicorn
from fastapi import FastAPI
from app.web.router import router
from app.web.api import api_router

app = FastAPI(title="AI产品自动提交工具")
app.include_router(router)
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True) 