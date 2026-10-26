"""认证相关 FastAPI 依赖。"""

from typing import Annotated

import jwt
from fastapi import Header, HTTPException, Request, status

from backend.app.schema.authDTO import TokenPayload
from backend.app.security.security import decode_access_token

# 免鉴权的公开路径；其余所有接口默认要求携带 Bearer token
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/auth/register",
        "/auth/login",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
)


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> TokenPayload | None:
    """全局鉴权依赖：白名单路径放行，其余路径校验 Bearer token。"""
    path = request.url.path.rstrip("/") or "/"

    if path in PUBLIC_PATHS or path.startswith("/docs"):
        return None

    if authorization is None or not authorization.startswith("Bearer "):
        raise _unauthorized()

    token = authorization.removeprefix("Bearer ").strip()

    try:
        return decode_access_token(token)
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise _unauthorized() from None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
