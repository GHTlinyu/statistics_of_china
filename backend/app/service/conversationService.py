from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.mapper.conversationMapper import ConversationMapper
from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.conversation import STATE_DELETED, Conversation
from backend.app.model.message import Message


class ConversationService:
    @staticmethod
    def list_conversations(
        db: Session,
        user_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[Conversation], int]:
        return ConversationMapper.list_by_user(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def get_conversation(
        db: Session,
        conversation_id: int,
        user_id: int,
    ) -> Conversation:
        conversation = ConversationMapper.find_by_id(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if conversation is None:
            raise _not_found()

        return conversation

    @staticmethod
    def list_messages(
        db: Session,
        conversation_id: int,
        user_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[Message], int]:
        # 先校验会话归属与状态，越权/已删除统一 404
        ConversationService.get_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return MessageMapper.list_by_conversation(
            db=db,
            conversation_id=conversation_id,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def create_conversation(
        db: Session,
        user_id: int,
        title: str | None,
    ) -> Conversation:
        return ConversationMapper.create(
            db=db,
            user_id=user_id,
            title=title,
        )

    @staticmethod
    def delete_conversation(
        db: Session,
        conversation_id: int,
        user_id: int,
    ) -> None:
        affected = ConversationMapper.soft_delete(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
            state=STATE_DELETED,
        )

        if affected == 0:
            raise _not_found()


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Conversation not found",
    )
