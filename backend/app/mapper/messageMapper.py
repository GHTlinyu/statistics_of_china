"""消息数据访问。"""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.model.message import Message


class MessageMapper:
    @staticmethod
    def list_by_conversation(
        db: Session,
        conversation_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[Message], int]:
        total = db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        ) or 0

        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(db.scalars(stmt)), total

    @staticmethod
    def create(
        db: Session,
        message: Message,
    ) -> Message:
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def find_by_id(
        db: Session,
        message_id: int,
    ) -> Message | None:
        stmt = select(Message).where(Message.id == message_id)

        return db.scalar(stmt)

    @staticmethod
    def delete_by_id(
        db: Session,
        message_id: int,
    ) -> None:
        stmt = delete(Message).where(Message.id == message_id)

        db.execute(stmt)
        db.commit()

    @staticmethod
    def find_recent_by_conversation(
        db: Session,
        conversation_id: int,
        limit: int = 20,
    ) -> list[Message]:
        """取最近 N 条消息，返回时恢复为正序。"""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )

        messages = list(db.scalars(stmt).all())
        messages.reverse()

        return messages

    @staticmethod
    def find_recent_user_messages(
        db: Session,
        conversation_id: int,
        limit: int = 2,
    ) -> list[Message]:
        """取最近 N 条用户消息，返回时恢复为正序。"""
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )

        messages = list(db.scalars(stmt).all())
        messages.reverse()

        return messages
