"""聊天接口：SSE 流式问答。"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent

from backend.app.schema.authDTO import TokenPayload
from backend.app.schema.chatDTO import ChatRequest
from backend.app.security.deps import get_current_user
from backend.app.service.chatService import ChatService, ChatTurn, prepare_chat_turn

router = APIRouter(
    prefix="/conversation",
    tags=["chat"],
)


def _prepare_turn(
    conversation_id: int,
    body: ChatRequest,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> ChatTurn:
    """依赖：在流式开始前完成 404 校验与历史读取。

    放在依赖里执行，404 能以普通 JSON 错误返回，而不是流里的半截异常。
    """
    return prepare_chat_turn(
        conversation_id=conversation_id,
        user_id=current_user.user_id,
        question=body.content,
    )


@router.post(
    "/{conversation_id}/chat",
    response_class=EventSourceResponse,
)
async def chat(
    turn: Annotated[ChatTurn, Depends(_prepare_turn)],
) -> AsyncIterator[ServerSentEvent]:
    async for event in ChatService.stream_answer(
        conversation_id=turn.conversation_id,
        question=turn.question,
        history=turn.history,
    ):
        yield ServerSentEvent(data=event)
