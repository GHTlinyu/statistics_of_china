"""消息服务：会话内消息的增删。"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.mapper.conversationMapper import ConversationMapper
from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.message import Message


class MessageService:
    @staticmethod
    def create_message(
        db: Session,
        conversation_id: int,
        user_id: int,
        role: str,
        content: str,
    ) -> Message:
        _ensure_conversation(db=db, conversation_id=conversation_id, user_id=user_id)

        return MessageMapper.create(
            db=db,
            message=Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
            ),
        )

    @staticmethod
    def delete_message(
        db: Session,
        conversation_id: int,
        message_id: int,
        user_id: int,
    ) -> None:
        _ensure_conversation(db=db, conversation_id=conversation_id, user_id=user_id)

        message = MessageMapper.find_by_id(db=db, message_id=message_id)

        if message is None or message.conversation_id != conversation_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        MessageMapper.delete_by_id(db=db, message_id=message_id)


def _ensure_conversation(db: Session, conversation_id: int, user_id: int) -> None:
    conversation = ConversationMapper.find_by_id(
        db=db,
        conversation_id=conversation_id,
        user_id=user_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
