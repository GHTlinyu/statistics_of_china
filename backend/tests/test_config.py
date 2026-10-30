"""应用配置：数据库 URL、验证码默认值与必填项。"""

import pytest
from pydantic import ValidationError

from backend.app.core.config import Settings


def _settings(**overrides):
    values = {
        "db_host": "127.0.0.1",
        "db_name": "statistics_test",
        "db_user": "test",
        "db_password": "test",
        "jwt_secret": "secret",
    }
    values.update(overrides)

    return Settings(_env_file=None, **values)


def test_database_url_and_captcha_defaults():
    settings = _settings()

    assert settings.database_url.drivername == "postgresql+psycopg"
    assert settings.database_url.host == "127.0.0.1"
    assert settings.database_url.port == 5432
    assert settings.database_url.database == "statistics_test"
    assert settings.captcha_ttl_seconds == 300
    assert settings.captcha_length == 4


def test_captcha_overrides():
    settings = _settings(
        captcha_ttl_seconds=60,
        captcha_length=6,
    )

    assert settings.captcha_ttl_seconds == 60
    assert settings.captcha_length == 6


def test_missing_required_fields(monkeypatch):
    for key in (
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "JWT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
