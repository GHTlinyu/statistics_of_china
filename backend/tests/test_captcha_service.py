"""验证码服务：图片、摘要、过期、一次性与容量清理。"""

import base64
import io
from datetime import datetime, timedelta, timezone

from PIL import Image

from backend.app.core.config import settings
from backend.app.model.captcha import Captcha
from backend.app.service.captchaService import (
    CAPTCHA_ALPHABET,
    CaptchaService,
)


def test_generate_returns_valid_png(db):
    issued = CaptchaService.generate(db=db)

    assert len(issued.captcha_id) == 32
    assert set(issued.code) <= set(CAPTCHA_ALPHABET)
    assert issued.expires_in == settings.captcha_ttl_seconds
    assert issued.image.startswith("data:image/png;base64,")

    raw = base64.b64decode(issued.image.split(",", 1)[1])
    image = Image.open(io.BytesIO(raw))
    assert image.size == (160, 60)
    assert image.format == "PNG"

    row = db.get(Captcha, issued.captcha_id)
    assert row is not None
    assert row.code_hash != issued.code
    assert issued.code not in row.code_hash
    assert len(row.code_hash) == 64


def test_verify_success_is_one_time(db):
    issued = CaptchaService.generate(db=db)

    assert CaptchaService.verify(db, issued.captcha_id, issued.code) is True
    assert CaptchaService.verify(db, issued.captcha_id, issued.code) is False
    assert db.get(Captcha, issued.captcha_id) is None


def test_verify_wrong_code_consumes_captcha(db):
    issued = CaptchaService.generate(db=db)

    assert CaptchaService.verify(db, issued.captcha_id, "XXXX") is False
    assert db.get(Captcha, issued.captcha_id) is None


def test_verify_is_case_insensitive(db):
    issued = CaptchaService.generate(db=db)

    assert CaptchaService.verify(db, issued.captcha_id, issued.code.lower()) is True


def test_verify_rejects_unknown_or_empty(db):
    assert CaptchaService.verify(db, "missing-id", "ABCD") is False
    assert CaptchaService.verify(db, "", "") is False


def test_verify_expired_captcha(db):
    issued = CaptchaService.generate(db=db)
    row = db.get(Captcha, issued.captcha_id)
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert CaptchaService.verify(db, issued.captcha_id, issued.code) is False
    assert db.get(Captcha, issued.captcha_id) is None


def test_generate_cleans_expired_records(db):
    expired = Captcha(
        id="expired-row",
        code_hash="0" * 64,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db.add(expired)
    db.commit()

    CaptchaService.generate(db=db)

    assert db.get(Captcha, "expired-row") is None


def test_generate_clamps_length(db, monkeypatch):
    monkeypatch.setattr(settings, "captcha_length", 2)
    assert len(CaptchaService.generate(db=db).code) == 4

    monkeypatch.setattr(settings, "captcha_length", 20)
    assert len(CaptchaService.generate(db=db).code) == 8
