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

    @staticmethod
    def find_by_username(
        db: Session,
        username: str,
    ) -> User | None:

        stmt = select(User).where(User.username == username)

        return db.scalar(stmt)

    @staticmethod
    def create(
        db: Session,
        username: str,
        password_hash: str,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user
