from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model.user import User


class UserMapper:
    @staticmethod
    def find_by_id(
        db: Session,
        user_id: int,
    ) -> User | None:

        stmt = select(User).where(User.id == user_id)

        return db.scalar(stmt)
