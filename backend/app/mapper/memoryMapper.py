"""用户长期记忆数据访问。"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.model.memory import Memory


class MemoryMapper:
    @staticmethod
    def list_by_user(
        db: Session,
        user_id: int,
        limit: int | None = None,
    ) -> list[Memory]:
        """按最近更新时间倒序取用户记忆；limit 为空时不限量。"""
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.updated_at.desc(), Memory.id.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        return list(db.scalars(stmt))

    @staticmethod
    def list_by_user_and_type(
        db: Session,
        user_id: int,
        memory_type: str,
    ) -> list[Memory]:
        """按创建时间正序取同类型记忆，第一条即最旧。"""
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.memory_type == memory_type,
            )
            .order_by(Memory.created_at.asc(), Memory.id.asc())
        )

        return list(db.scalars(stmt))

    @staticmethod
    def find_by_ids(
        db: Session,
        user_id: int,
        memory_ids: list[int],
    ) -> list[Memory]:
        """按 ID 批量读取，同时限定归属。"""
        if not memory_ids:
            return []

        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.id.in_(memory_ids),
        )

        return list(db.scalars(stmt))

    @staticmethod
    def find_by_id(
        db: Session,
        user_id: int,
        memory_id: int,
    ) -> Memory | None:
        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.id == memory_id,
        )

        return db.scalar(stmt)

    @staticmethod
    def count_by_user(db: Session, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Memory)
            .where(Memory.user_id == user_id)
        )

        return db.scalar(stmt) or 0

    @staticmethod
    def find_oldest(
        db: Session,
        user_id: int,
        memory_type: str | None = None,
    ) -> Memory | None:
        """取最旧一条记忆；指定类型时只在该类型内查找。"""
        stmt = select(Memory).where(Memory.user_id == user_id)
        if memory_type is not None:
            stmt = stmt.where(Memory.memory_type == memory_type)

        stmt = stmt.order_by(Memory.created_at.asc(), Memory.id.asc()).limit(1)

        return db.scalar(stmt)

    @staticmethod
    def create(db: Session, memory: Memory) -> Memory:
        db.add(memory)
        db.commit()
        db.refresh(memory)

        return memory

    @staticmethod
    def update_fields(
        db: Session,
        user_id: int,
        memory_id: int,
        *,
        memory_type: str,
        title: str,
        description: str | None,
        content: str,
    ) -> None:
        stmt = (
            update(Memory)
            .where(
                Memory.id == memory_id,
                Memory.user_id == user_id,
            )
            .values(
                memory_type=memory_type,
                title=title,
                description=description,
                content=content,
                updated_at=func.now(),
            )
        )

        db.execute(stmt)
        db.commit()
