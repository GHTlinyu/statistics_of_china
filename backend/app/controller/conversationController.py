from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.database import get_db
from backend.app.schema.authDTO import TokenPayload
from backend.app.schema.conversationDTO import (
    ConversationDTO,
    CreateConversationRequest,
    MessageDTO,
)
from backend.app.schema.pageDTO import PageResult
from backend.app.schema.responseDTO import ApiResponse
from backend.app.security.deps import get_current_user
from backend.app.service.conversationService import ConversationService

router = APIRouter(
    prefix="/conversation",
    tags=["conversation"],
)


@router.get(
    "",
    response_model=ApiResponse[PageResult[ConversationDTO]],
)
def list_conversations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    items, total = ConversationService.list_conversations(
        db=db,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )

    return ApiResponse.ok(
        PageResult[ConversationDTO](
            items=[ConversationDTO.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "",
    response_model=ApiResponse[ConversationDTO],
    status_code=201,
)
def create_conversation(
    body: CreateConversationRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    conversation = ConversationService.create_conversation(
        db=db,
        user_id=current_user.user_id,
        title=body.title,
    )

    return ApiResponse.ok(
        ConversationDTO.model_validate(conversation),
    )


@router.get(
    "/{conversation_id}",
    response_model=ApiResponse[ConversationDTO],
)
def get_conversation(
    conversation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    conversation = ConversationService.get_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.user_id,
    )

    return ApiResponse.ok(
        ConversationDTO.model_validate(conversation),
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=ApiResponse[PageResult[MessageDTO]],
)
def list_messages(
    conversation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    items, total = ConversationService.list_messages(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )

    return ApiResponse.ok(
        PageResult[MessageDTO](
            items=[MessageDTO.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.delete(
    "/{conversation_id}",
    response_model=ApiResponse[None],
)
def delete_conversation(
    conversation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    ConversationService.delete_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.user_id,
    )

    return ApiResponse.ok(message="Conversation deleted")
