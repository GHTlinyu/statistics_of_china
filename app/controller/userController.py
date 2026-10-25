from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schema.userDTO import UserDTO
from app.service.userService import UserService

router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@router.get(
    "/{user_id}",
    response_model=UserDTO,
)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    user = UserService.get_user(
        db=db,
        user_id=user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return user
