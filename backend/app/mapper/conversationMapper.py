from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.model.conversation import STATE_ACTIVE, Conversation


class ConversationMapper:
    @staticmethod
    def list_by_user(
        db: Session,
        user_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[Conversation], int]:
        conditions = (
            Conversation.user_id == user_id,
            Conversation.state == STATE_ACTIVE,
        )

        total = db.scalar(
            select(func.count()).select_from(Conversation).where(*conditions)
        ) or 0

        stmt = (
            select(Conversation)
            .where(*conditions)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        return list(db.scalars(stmt)), total

    @staticmethod
    def find_by_id(
        db: Session,
        conversation_id: int,
        user_id: int,
    ) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.state == STATE_ACTIVE,
        )

        return db.scalar(stmt)

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        title: str | None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            title=title,
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return conversation

    @staticmethod
    def update_title(
        db: Session,
        conversation_id: int,
        title: str,
    ) -> None:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(title=title)
        )

        db.execute(stmt)
        db.commit()

    @staticmethod
    def touch(
        db: Session,
        conversation_id: int,
    ) -> None:
        """刷新会话的 updated_at，让列表按最近活跃排序。"""
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now())
        )

        db.execute(stmt)
        db.commit()

    @staticmethod
    def soft_delete(
        db: Session,
        conversation_id: int,
        user_id: int,
        state: int,
    ) -> int:
        """软删除，返回受影响行数。"""
        stmt = (
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.state == STATE_ACTIVE,
            )
            .values(state=state)
        )

        result = db.execute(stmt)
        db.commit()

        return result.rowcount or 0
