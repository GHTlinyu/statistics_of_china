from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.mapper.userMapper import UserMapper
from backend.app.model.user import User
from backend.app.security.security import hash_password, verify_password


class AuthService:
    @staticmethod
    def register(
        db: Session,
        username: str,
        password: str,
    ) -> User:
        if UserMapper.find_by_username(db=db, username=username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在",
            )

        return UserMapper.create(
            db=db,
            username=username,
            password_hash=hash_password(password),
        )

    @staticmethod
    def authenticate(
        db: Session,
        username: str,
        password: str,
    ) -> User:
        user = UserMapper.find_by_username(db=db, username=username)

        if user is None or not verify_password(password, user.password_hash):
            # 不区分"用户名不存在"与"密码错误"，避免用户枚举
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user
