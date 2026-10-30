"""密码哈希与 JWT 签发/校验。"""

import jwt
import pytest

from backend.app.core.config import settings
from backend.app.schema.authDTO import TokenPayload
from backend.app.security.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")

    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_with_invalid_hash_returns_false():
    assert verify_password("secret123", "not-a-valid-hash") is False


def test_access_token_roundtrip():
    payload = TokenPayload(user_id=7, username="alice", role="user")

    token = create_access_token(payload)

    assert decode_access_token(token) == payload


def test_access_token_rejects_wrong_signature():
    token = jwt.encode(
        {"sub": "7", "username": "alice", "role": "user"},
        "wrong-secret-0123456789abcdef0123456789abcdef",
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_access_token_rejects_expired(monkeypatch):
    monkeypatch.setattr(settings, "jwt_expire_minutes", -1)
    token = create_access_token(
        TokenPayload(user_id=7, username="alice", role="user")
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_access_token_requires_all_claims():
    token = jwt.encode(
        {"sub": "7"},
        settings.jwt_secret,
        algorithm="HS256",
    )

    with pytest.raises(KeyError):
        decode_access_token(token)
