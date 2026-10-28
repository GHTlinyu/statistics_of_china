"""聊天服务：编排一轮问答的流式响应。

SSE 事件统一为 ``{"type": ..., "data": {...}}``，由 controller 包成
``ServerSentEvent``，前端按 ``type`` 分发即可。
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from backend.agent.workflow.graph import graph
from backend.app.database.database import SessionLocal
from backend.app.mapper.conversationMapper import ConversationMapper
from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.conversation import Conversation
from backend.app.model.message import Message

logger = logging.getLogger(__name__)

# 短期上下文：最近 20 条消息（约 10 轮）
HISTORY_LIMIT = 20

# 首条消息自动生成会话标题的最大长度
TITLE_MAX_LENGTH = 20


@dataclass(frozen=True)
class ChatTurn:
    """一轮问答的入参，由依赖在流式开始前准备好。"""

    conversation_id: int
    question: str
    history: list[BaseMessage]


def build_event(event_type: str, **data: Any) -> dict[str, Any]:
    """通用 SSE 事件：{"type": ..., "data": {...}}。"""
    return {"type": event_type, "data": data}


def prepare_chat_turn(
    conversation_id: int,
    user_id: int,
    question: str,
) -> ChatTurn:
    """流式开始前的准备：校验归属、读历史、保存本轮用户消息。"""
    conversation = ChatService.get_conversation(
        conversation_id=conversation_id,
        user_id=user_id,
    )
    history = ChatService.load_history(conversation_id=conversation_id)

    ChatService.prepare_turn(conversation=conversation, question=question)

    return ChatTurn(
        conversation_id=conversation_id,
        question=question,
        history=history,
    )


class ChatService:
    @staticmethod
    def get_conversation(conversation_id: int, user_id: int) -> Conversation:
        """按归属读取会话，越权或已删除统一 404。"""
        with SessionLocal() as db:
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

        return conversation

    @staticmethod
    def load_history(
        conversation_id: int,
        limit: int = HISTORY_LIMIT,
    ) -> list[BaseMessage]:
        """最近 N 条消息转成 LangChain 消息（不含本轮问题）。"""
        with SessionLocal() as db:
            messages = MessageMapper.find_recent_by_conversation(
                db=db,
                conversation_id=conversation_id,
                limit=limit,
            )

        history: list[BaseMessage] = []

        for message in messages:
            if message.role == "user":
                history.append(HumanMessage(content=message.content))
            elif message.role == "assistant":
                history.append(AIMessage(content=message.content))

        return history

    @staticmethod
    def prepare_turn(conversation: Conversation, question: str) -> None:
        """保存本轮用户消息；首条消息顺便补会话标题。"""
        with SessionLocal() as db:
            if not conversation.title:
                ConversationMapper.update_title(
                    db=db,
                    conversation_id=conversation.id,
                    title=question[:TITLE_MAX_LENGTH],
                )

            MessageMapper.create(
                db=db,
                message=Message(
                    conversation_id=conversation.id,
                    role="user",
                    content=question,
                ),
            )
            ConversationMapper.touch(db=db, conversation_id=conversation.id)

    @staticmethod
    def save_assistant_message(conversation_id: int, content: str) -> int:
        with SessionLocal() as db:
            message = MessageMapper.create(
                db=db,
                message=Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=content,
                ),
            )
            ConversationMapper.touch(db=db, conversation_id=conversation_id)

            return message.id

    @staticmethod
    async def stream_answer(
        conversation_id: int,
        question: str,
        history: list[BaseMessage],
    ) -> AsyncIterator[dict[str, Any]]:
        """流式执行工作流，产出通用 SSE 事件。"""
        parts: list[str] = []
        saved = False

        try:
            yield build_event("start", conversation_id=conversation_id)

            inputs = {
                "question": question,
                "history": history,
                "memories": [],
            }

            async for chunk in graph.astream(inputs, stream_mode="custom"):
                content = chunk.get("content") if isinstance(chunk, dict) else None
                if not content:
                    continue

                parts.append(content)
                yield build_event("token", content=content)

            answer = "".join(parts)
            message_id: int | None = None

            if answer:
                message_id = await asyncio.to_thread(
                    ChatService.save_assistant_message,
                    conversation_id,
                    answer,
                )
                saved = True

            yield build_event(
                "done",
                conversation_id=conversation_id,
                message_id=message_id,
            )

        except Exception:
            logger.exception("聊天生成失败：conversation_id=%s", conversation_id)
            yield build_event(
                "error",
                code="AGENT_EXECUTION_ERROR",
                message="生成失败，请稍后重试",
            )

        finally:
            # 客户端断开或中途停止时，把已经生成的部分回答落库
            if not saved and parts:
                try:
                    await asyncio.shield(
                        asyncio.to_thread(
                            ChatService.save_assistant_message,
                            conversation_id,
                            "".join(parts),
                        )
                    )
                except Exception:
                    logger.exception(
                        "保存部分回答失败：conversation_id=%s",
                        conversation_id,
                    )
