from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# 仓库根目录（backend/app/database/config.py -> backend/app/database -> backend -> 仓库根）。
# .env 固定在仓库根，避免工作目录不同导致找不到配置。
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    db_host: str
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str
    jwt_secret: str
    jwt_expire_minutes: int = 1440

    # 登录 / 注册验证码
    captcha_ttl_seconds: int = 300
    captcha_length: int = 4

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


settings = Settings()
