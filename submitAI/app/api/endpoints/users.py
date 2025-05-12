from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Any, List
from datetime import datetime

from app.models.user import User, UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password, create_access_token
from app.api.deps import get_current_user, fake_users_db

router = APIRouter()

# 不再需要这里定义fake_users_db，使用从deps.py导入的变量
# fake_users_db = {}

@router.post("/register", response_model=User)
def create_user(user_in: UserCreate) -> Any:
    """
    创建新用户
    """
    user = fake_users_db.get(user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="该邮箱已被注册",
        )
    
    hashed_password = get_password_hash(user_in.password)
    user_data = user_in.dict()
    user_data.pop("password")
    user_data["hashed_password"] = hashed_password
    user_data["id"] = len(fake_users_db) + 1
    user_data["created_at"] = datetime.now()
    
    fake_users_db[user_in.email] = user_data
    return user_data

@router.post("/login/access-token")
def login_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    """
    获取OAuth2兼容的令牌
    """
    user = fake_users_db.get(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    
    if not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    
    return {
        "access_token": create_access_token(subject=user["email"]),
        "token_type": "bearer",
    }

@router.get("/me", response_model=User)
def read_users_me(current_user: User = Depends(get_current_user)) -> Any:
    """
    获取当前用户信息
    """
    return current_user 