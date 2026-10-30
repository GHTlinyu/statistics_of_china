from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.database.database import get_db
from backend.app.schema.authDTO import (
    LoginRequest,
    RegisterRequest,
    TokenPayload,
    TokenResponse,
)
from backend.app.schema.captchaDTO import CaptchaDTO
from backend.app.schema.responseDTO import ApiResponse
from backend.app.schema.userDTO import UserDTO
from backend.app.security.deps import get_current_user
from backend.app.security.security import create_access_token
from backend.app.service.authService import AuthService
from backend.app.service.captchaService import CaptchaService

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


def _ensure_captcha(
    db: Session,
    captcha_id: str,
    captcha_code: str,
) -> None:
    """验证码是登录 / 注册的第一道校验，失败时不触碰账号数据。"""
    if not CaptchaService.verify(
        db=db,
        captcha_id=captcha_id,
        code=captcha_code,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误或已过期",
        )


@router.get(
    "/captcha",
    response_model=ApiResponse[CaptchaDTO],
)
def get_captcha(
    db: Annotated[Session, Depends(get_db)],
):
    issued = CaptchaService.generate(db=db)

    return ApiResponse.ok(
        CaptchaDTO(
            captcha_id=issued.captcha_id,
            image=issued.image,
            expires_in=issued.expires_in,
        )
    )


@router.post(
    "/register",
    response_model=ApiResponse[UserDTO],
    status_code=201,
)
def register(
    body: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
):
    _ensure_captcha(db, body.captcha_id, body.captcha_code)

    user = AuthService.register(
        db=db,
        username=body.username,
        password=body.password,
    )

    return ApiResponse.ok(user)


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
)
def login(
    body: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    _ensure_captcha(db, body.captcha_id, body.captcha_code)

    user = AuthService.authenticate(
        db=db,
        username=body.username,
        password=body.password,
    )

    payload = TokenPayload(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    return ApiResponse.ok(
        TokenResponse(
            access_token=create_access_token(payload),
            expires_in=settings.jwt_expire_minutes * 60,
        )
    )


@router.get(
    "/me",
    response_model=ApiResponse[TokenPayload],
)
def me(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    return ApiResponse.ok(current_user)
