from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.database import Base


class Captcha(Base):
    """一次性图片验证码记录。

    只保存验证码摘要，明文只在生成时短暂存在于内存中。
    """

    __tablename__ = "captcha"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    code_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
