from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from typing import Generator, Optional

from app.core.config import settings
from app.models.user import User

# 直接在这里定义模拟数据库，而不是从users.py导入
fake_users_db = {}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login/access-token")

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    验证当前用户
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = fake_users_db.get(email)
    if user is None:
        raise HTTPException(status_code=404, detail="用户未找到")
    
    return User(**user)

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    验证当前用户是否活跃
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="非活跃用户")
    return current_user 