"""密码哈希与 JWT 签发/解析。"""

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from backend.app.core.config import settings
from backend.app.schema.authDTO import TokenPayload

password_hasher = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(payload: TokenPayload) -> str:
    now = datetime.now(timezone.utc)
    to_encode = {
        "sub": str(payload.user_id),
        "username": payload.username,
        "role": payload.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }

    return jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> TokenPayload:
    """解析并校验 token。

    签名无效/过期/缺少声明时抛出 jwt.InvalidTokenError 或 KeyError，
    由调用方统一转为 401。
    """
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[JWT_ALGORITHM],
    )

    return TokenPayload(
        user_id=int(claims["sub"]),
        username=claims["username"],
        role=claims["role"],
    )
