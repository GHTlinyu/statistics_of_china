"""长期记忆读写编排。

读路径在聊天流开始前筛选相关记忆，写路径在回答落库后由后台任务提取。
两边的模型调用都视为 best-effort：失败只记日志，不影响聊天主链路。
"""

import logging

from sqlalchemy.orm import Session

from backend.agent.memory.memory_extractor import extract_memories
from backend.agent.memory.memory_finder import find_memories
from backend.agent.memory.memory_updater import decide_memory_update
from backend.agent.schema.memory_schema import MemoryOperation
from backend.app.database.database import SessionLocal
from backend.app.mapper.memoryMapper import MemoryMapper
from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.memory import Memory
from backend.app.model.message import Message

logger = logging.getLogger(__name__)

# 每个用户最多保存的长期记忆条数
MAX_MEMORIES = 10

# finder 输入：最近 2 条用户消息 + 本轮问题 ≈ 3 轮
FINDER_RECENT_USER_MESSAGES = 2

# extractor 输入：最近 10 轮对话（user / assistant 各一条算一轮）
EXTRACTOR_HISTORY_LIMIT = 20

# memory.title 对应 VARCHAR(255)
TITLE_MAX_LENGTH = 255


def _memory_to_dict(memory: Memory) -> dict:
    return {
        "id": memory.id,
        "memory_type": memory.memory_type,
        "title": memory.title,
        "description": memory.description or "",
        "content": memory.content,
    }


def _message_to_dict(message: Message) -> dict:
    return {
        "role": message.role,
        "content": message.content,
    }


class MemoryService:
    @staticmethod
    def find_long_term_memories(
        user_id: int,
        conversation_id: int,
        current_question: str,
    ) -> list[dict]:
        """读路径：返回与当前问题相关的记忆；异常时降级为空。"""
        try:
            with SessionLocal() as db:
                catalog = MemoryMapper.list_by_user(
                    db=db,
                    user_id=user_id,
                    limit=MAX_MEMORIES,
                )
                if not catalog:
                    return []

                recent_messages = MessageMapper.find_recent_user_messages(
                    db=db,
                    conversation_id=conversation_id,
                    limit=FINDER_RECENT_USER_MESSAGES,
                )

            messages = [
                _message_to_dict(message) for message in recent_messages
            ]
            messages.append({"role": "user", "content": current_question})

            result = find_memories(
                memory_catalog=[_memory_to_dict(memory) for memory in catalog],
                recent_user_messages=messages,
            )

            if not result.memory_ids:
                return []

            with SessionLocal() as db:
                memories = MemoryMapper.find_by_ids(
                    db=db,
                    user_id=user_id,
                    memory_ids=result.memory_ids,
                )

            return [_memory_to_dict(memory) for memory in memories]
        except Exception:
            logger.warning(
                "长期记忆查找失败，按无记忆继续：user_id=%s conversation_id=%s",
                user_id,
                conversation_id,
                exc_info=True,
            )
            return []

    @staticmethod
    def extract_and_save(user_id: int, conversation_id: int) -> None:
        """写路径：从最近对话提取记忆；异常只记日志。"""
        try:
            with SessionLocal() as db:
                messages = MessageMapper.find_recent_by_conversation(
                    db=db,
                    conversation_id=conversation_id,
                    limit=EXTRACTOR_HISTORY_LIMIT,
                )
                existing_memories = MemoryMapper.list_by_user(
                    db=db,
                    user_id=user_id,
                    limit=MAX_MEMORIES,
                )

            if not messages:
                return

            result = extract_memories(
                existing_memories=[
                    _memory_to_dict(memory) for memory in existing_memories
                ],
                recent_messages=[
                    _message_to_dict(message) for message in messages
                ],
            )

            for operation in result.operations:
                MemoryService._apply_operation(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    operation=operation,
                )

            logger.info(
                "长期记忆提取完成：user_id=%s conversation_id=%s operations=%d",
                user_id,
                conversation_id,
                len(result.operations),
            )
        except Exception:
            logger.warning(
                "长期记忆提取失败：user_id=%s conversation_id=%s",
                user_id,
                conversation_id,
                exc_info=True,
            )

    @staticmethod
    def _apply_operation(
        user_id: int,
        conversation_id: int,
        operation: MemoryOperation,
    ) -> None:
        if operation.action == "UPDATE":
            MemoryService._apply_update(
                user_id=user_id,
                operation=operation,
            )
            return

        MemoryService._apply_create(
            user_id=user_id,
            conversation_id=conversation_id,
            operation=operation,
        )

    @staticmethod
    def _apply_update(
        user_id: int,
        operation: MemoryOperation,
    ) -> None:
        if operation.memory_id is None:
            logger.warning(
                "记忆 UPDATE 缺少 memory_id，已忽略：user_id=%s",
                user_id,
            )
            return

        with SessionLocal() as db:
            memory = MemoryMapper.find_by_id(
                db=db,
                user_id=user_id,
                memory_id=operation.memory_id,
            )

            if memory is None:
                logger.warning(
                    "记忆 UPDATE 目标不存在或不属于当前用户，已忽略："
                    "user_id=%s memory_id=%s",
                    user_id,
                    operation.memory_id,
                )
                return

            MemoryMapper.update_fields(
                db=db,
                user_id=user_id,
                memory_id=memory.id,
                memory_type=operation.memory_type,
                title=operation.title[:TITLE_MAX_LENGTH],
                description=operation.description,
                content=operation.content,
            )

    @staticmethod
    def _apply_create(
        user_id: int,
        conversation_id: int,
        operation: MemoryOperation,
    ) -> None:
        with SessionLocal() as db:
            count = MemoryMapper.count_by_user(
                db=db,
                user_id=user_id,
            )

            if count < MAX_MEMORIES:
                MemoryService._create(
                    db=db,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    operation=operation,
                )
                return

            same_type = MemoryMapper.list_by_user_and_type(
                db=db,
                user_id=user_id,
                memory_type=operation.memory_type,
            )

        if same_type:
            MemoryService._merge_or_replace(
                user_id=user_id,
                operation=operation,
                candidates=same_type,
            )
            return

        MemoryService._replace_oldest(
            user_id=user_id,
            operation=operation,
        )

    @staticmethod
    def _create(
        db: Session,
        user_id: int,
        conversation_id: int,
        operation: MemoryOperation,
    ) -> Memory:
        return MemoryMapper.create(
            db=db,
            memory=Memory(
                user_id=user_id,
                memory_type=operation.memory_type,
                title=operation.title[:TITLE_MAX_LENGTH],
                description=operation.description,
                content=operation.content,
                source_conversation_id=conversation_id,
            ),
        )

    @staticmethod
    def _merge_or_replace(
        user_id: int,
        operation: MemoryOperation,
        candidates: list[Memory],
    ) -> None:
        """同类型记忆已存在：由 updater 决定合并目标或替换最旧一条。"""
        oldest = candidates[0]

        try:
            decision = decide_memory_update(
                new_memory=operation,
                existing_memories=[
                    _memory_to_dict(memory) for memory in candidates
                ],
                oldest_memory_id=oldest.id,
            )
        except Exception:
            logger.warning(
                "记忆更新决策失败，跳过本条：user_id=%s",
                user_id,
                exc_info=True,
            )
            return

        if decision.action == "MERGE":
            target_id = decision.memory_id
            if target_id not in {memory.id for memory in candidates}:
                logger.warning(
                    "记忆 MERGE 返回非法 memory_id，已忽略："
                    "user_id=%s memory_id=%s",
                    user_id,
                    target_id,
                )
                return
        else:
            # REPLACE 必须覆盖系统指定的最旧记忆，不采信模型返回的其他 ID
            target_id = oldest.id

        with SessionLocal() as db:
            memory = MemoryMapper.find_by_id(
                db=db,
                user_id=user_id,
                memory_id=target_id,
            )

            if memory is None:
                logger.warning(
                    "记忆更新目标不存在或不属于当前用户，已忽略："
                    "user_id=%s memory_id=%s",
                    user_id,
                    target_id,
                )
                return

            MemoryMapper.update_fields(
                db=db,
                user_id=user_id,
                memory_id=memory.id,
                memory_type=operation.memory_type,
                title=decision.title[:TITLE_MAX_LENGTH],
                description=decision.description,
                content=decision.content,
            )

    @staticmethod
    def _replace_oldest(
        user_id: int,
        operation: MemoryOperation,
    ) -> None:
        """没有同类型记忆时，直接替换全局最旧一条。"""
        with SessionLocal() as db:
            oldest = MemoryMapper.find_oldest(
                db=db,
                user_id=user_id,
            )

            if oldest is None:
                logger.warning(
                    "记忆数量已满但未找到可替换记录：user_id=%s",
                    user_id,
                )
                return

            MemoryMapper.update_fields(
                db=db,
                user_id=user_id,
                memory_id=oldest.id,
                memory_type=operation.memory_type,
                title=operation.title[:TITLE_MAX_LENGTH],
                description=operation.description,
                content=operation.content,
            )
