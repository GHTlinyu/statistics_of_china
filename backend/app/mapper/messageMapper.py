from sqlalchemy import func, select
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
