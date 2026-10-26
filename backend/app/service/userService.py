from sqlalchemy.orm import Session

from backend.app.mapper.userMapper import UserMapper
from backend.app.model.user import User


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
