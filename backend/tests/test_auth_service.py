"""认证服务：注册、重复用户名、凭据校验。"""

import pytest
from fastapi import HTTPException

from backend.app.security.security import verify_password
from backend.app.service.authService import AuthService


def test_register_hashes_password_and_defaults(db):
    user = AuthService.register(
        db=db,
        username="alice",
        password="secret123",
    )

    assert user.id is not None
    assert user.username == "alice"
    assert user.role == "user"
    assert user.is_active is True
    assert user.password_hash != "secret123"
    assert verify_password("secret123", user.password_hash) is True


def test_register_rejects_duplicate_username(db):
    AuthService.register(db=db, username="alice", password="secret123")

    with pytest.raises(HTTPException) as exc_info:
        AuthService.register(db=db, username="alice", password="secret456")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "用户名已存在"


def test_authenticate_success(db):
    created = AuthService.register(
        db=db,
        username="alice",
        password="secret123",
    )

    user = AuthService.authenticate(
        db=db,
        username="alice",
        password="secret123",
    )

    assert user.id == created.id


def test_authenticate_unknown_user_returns_401(db):
    with pytest.raises(HTTPException) as exc_info:
        AuthService.authenticate(
            db=db,
            username="nobody",
            password="secret123",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "用户名或密码错误"
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_authenticate_wrong_password_returns_401(db):
    AuthService.register(db=db, username="alice", password="secret123")

    with pytest.raises(HTTPException) as exc_info:
        AuthService.authenticate(
            db=db,
            username="alice",
            password="wrong-password",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "用户名或密码错误"
