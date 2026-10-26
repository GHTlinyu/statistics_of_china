from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.config import settings
from backend.app.database.database import get_db
from backend.app.schema.authDTO import (
    LoginRequest,
    RegisterRequest,
    TokenPayload,
    TokenResponse,
)
from backend.app.schema.responseDTO import ApiResponse
from backend.app.schema.userDTO import UserDTO
from backend.app.security.deps import get_current_user
from backend.app.security.security import create_access_token
from backend.app.service.authService import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
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
