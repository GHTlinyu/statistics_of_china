"""验证码数据访问。"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.model.captcha import Captcha


class CaptchaMapper:
    @staticmethod
    def create(db: Session, captcha: Captcha) -> Captcha:
        db.add(captcha)
        db.commit()

        return captcha

    @staticmethod
    def find_for_update(db: Session, captcha_id: str) -> Captcha | None:
        """加行锁读取，配合校验后的删除保证一次性。"""
        stmt = (
            select(Captcha)
            .where(Captcha.id == captcha_id)
            .with_for_update()
        )

        return db.scalar(stmt)

    @staticmethod
    def delete(db: Session, captcha: Captcha) -> None:
        db.delete(captcha)
        db.commit()

    @staticmethod
    def delete_expired(db: Session) -> int:
        """清理过期记录，返回删除行数。"""
        stmt = delete(Captcha).where(Captcha.expires_at < func.now())

        result = db.execute(stmt)
        db.commit()

        return result.rowcount or 0
