"""验证码生成与校验：图片自托管，摘要入库，一次性使用。"""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from captcha.image import ImageCaptcha
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.mapper.captchaMapper import CaptchaMapper
from backend.app.model.captcha import Captcha

# 去掉 0/O/1/I 等易混淆字符
CAPTCHA_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

IMAGE_WIDTH = 160
IMAGE_HEIGHT = 60

MIN_LENGTH = 4
MAX_LENGTH = 8


@dataclass(frozen=True)
class IssuedCaptcha:
    """签发结果；`code` 仅供服务端内部使用，禁止放进 API 响应。"""

    captcha_id: str
    code: str
    image: str
    expires_in: int


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def _hash_code(code: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        _normalize_code(code).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _render_image(code: str) -> str:
    buffer = ImageCaptcha(width=IMAGE_WIDTH, height=IMAGE_HEIGHT).generate(code)
    payload = base64.b64encode(buffer.read()).decode("ascii")

    return f"data:image/png;base64,{payload}"


def _is_expired(expires_at: datetime) -> bool:
    # 兼容不使用 timezone-aware timestamp 的测试数据库
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return expires_at <= datetime.now(timezone.utc)


class CaptchaService:
    @staticmethod
    def generate(db: Session) -> IssuedCaptcha:
        length = max(MIN_LENGTH, min(settings.captcha_length, MAX_LENGTH))
        expires_in = max(1, settings.captcha_ttl_seconds)

        code = "".join(
            secrets.choice(CAPTCHA_ALPHABET) for _ in range(length)
        )
        image = _render_image(code)
        captcha_id = secrets.token_hex(16)

        # 先清理过期记录，避免表无限增长
        CaptchaMapper.delete_expired(db)
        CaptchaMapper.create(
            db,
            Captcha(
                id=captcha_id,
                code_hash=_hash_code(code),
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=expires_in),
            ),
        )

        return IssuedCaptcha(
            captcha_id=captcha_id,
            code=code,
            image=image,
            expires_in=expires_in,
        )

    @staticmethod
    def verify(db: Session, captcha_id: str, code: str) -> bool:
        """校验并销毁验证码；成功或失败都只能使用一次。"""
        if not captcha_id or not code:
            return False

        captcha = CaptchaMapper.find_for_update(db, captcha_id)
        if captcha is None:
            return False

        valid = not _is_expired(captcha.expires_at) and hmac.compare_digest(
            captcha.code_hash,
            _hash_code(code),
        )

        CaptchaMapper.delete(db, captcha)

        return valid
