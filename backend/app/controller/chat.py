from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService


router = APIRouter(
    prefix="/conversations",
    tags=["chat"],
)


@router.post(
    "/{conversation_id}/chat",
    response_class=EventSourceResponse,
)
async def chat(
    conversation_id: int,
    data: ChatRequest,
) -> AsyncGenerator[ServerSentEvent, None]:

    try:
        conversation = ChatService.get_conversation(
            conversation_id=conversation_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # 2. 读取短期记忆
    # 注意：这里要在保存本轮 user message 之前读取，
    # 否则当前问题会同时存在于 history 和 question 中
    history = ChatService.load_history(
        conversation_id=conversation_id,
        limit=20,
    )

    # 3. 读取长期记忆
    long_term_memories = ChatService.find_long_term_memories(
        user_id=conversation.user_id,
        conversation_id=conversation_id,
        current_question=data.content,
    )

    ChatService.save_user_message(
        conversation_id=conversation_id,
        content=data.content,
    )

    async for event in ChatService.stream_chat(
        user_id=conversation.user_id,
        conversation_id=conversation_id,
        question=data.content,
        history=history,
        long_term_memories=long_term_memories,
    ):
        yield event
