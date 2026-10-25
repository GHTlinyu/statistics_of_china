from sqlalchemy.orm import Session

from app.mapper.userMapper import UserMapper
from app.model.user import User


class UserService:
    @staticmethod
    def get_user(
        db: Session,
        user_id: int,
    ) -> User | None:

        return UserMapper.find_by_id(
            db=db,
            user_id=user_id,
        )
