"""消息接口：会话内消息的增删。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.database import get_db
from backend.app.schema.authDTO import TokenPayload
from backend.app.schema.conversationDTO import MessageDTO
from backend.app.schema.messageDTO import CreateMessageRequest
from backend.app.schema.responseDTO import ApiResponse
from backend.app.security.deps import get_current_user
from backend.app.service.messageService import MessageService

router = APIRouter(
    prefix="/conversation",
    tags=["message"],
)


@router.post(
    "/{conversation_id}/messages",
    response_model=ApiResponse[MessageDTO],
    status_code=201,
)
def create_message(
    conversation_id: int,
    body: CreateMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    message = MessageService.create_message(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.user_id,
        role=body.role,
        content=body.content,
    )

    return ApiResponse.ok(MessageDTO.model_validate(message))


@router.delete(
    "/{conversation_id}/messages/{message_id}",
    response_model=ApiResponse[None],
)
def delete_message(
    conversation_id: int,
    message_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    MessageService.delete_message(
        db=db,
        conversation_id=conversation_id,
        message_id=message_id,
        user_id=current_user.user_id,
    )

    return ApiResponse.ok(message="Message deleted")
