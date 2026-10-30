"""聊天服务：历史、标题、记忆注入、SSE 事件与部分保存。"""

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage

import backend.app.service.chatService as chat_service
from backend.app.mapper.conversationMapper import ConversationMapper
from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.conversation import Conversation
from backend.app.model.message import Message
from backend.app.service.chatService import ChatService, prepare_chat_turn


@pytest.fixture(autouse=True)
def patch_session_local(monkeypatch, session_factory):
    monkeypatch.setattr(chat_service, "SessionLocal", session_factory)


class FakeGraph:
    def __init__(self, chunks, error=None):
        self.chunks = chunks
        self.error = error
        self.inputs = None

    async def astream(self, inputs, stream_mode):
        self.inputs = inputs
        assert stream_mode == "custom"
        for chunk in self.chunks:
            yield chunk
        if self.error is not None:
            raise self.error


def _messages(db, conversation_id):
    return MessageMapper.list_by_conversation(
        db=db,
        conversation_id=conversation_id,
        page=1,
        page_size=100,
    )[0]


def test_get_conversation_own_foreign_missing(db, user, other_user, conversation):
    fetched = ChatService.get_conversation(
        conversation_id=conversation.id,
        user_id=user.id,
    )
    assert fetched.id == conversation.id

    with pytest.raises(HTTPException):
        ChatService.get_conversation(
            conversation_id=conversation.id,
            user_id=other_user.id,
        )

    with pytest.raises(HTTPException):
        ChatService.get_conversation(
            conversation_id=999_999,
            user_id=user.id,
        )


def test_load_history_maps_roles_and_skips_system(db, conversation):
    MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="user",
            content="u1",
        ),
    )
    MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="assistant",
            content="a1",
        ),
    )
    MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="system",
            content="s1",
        ),
    )

    history = ChatService.load_history(conversation_id=conversation.id)

    assert len(history) == 2
    assert isinstance(history[0], HumanMessage)
    assert history[0].content == "u1"
    assert isinstance(history[1], AIMessage)
    assert history[1].content == "a1"


def test_load_history_limit_keeps_latest(db, conversation):
    for index in range(5):
        MessageMapper.create(
            db=db,
            message=Message(
                conversation_id=conversation.id,
                role="user",
                content=f"m{index}",
            ),
        )

    history = ChatService.load_history(
        conversation_id=conversation.id,
        limit=3,
    )

    assert [message.content for message in history] == ["m2", "m3", "m4"]


def test_prepare_turn_sets_title_and_saves_message(db, user):
    conversation = ConversationMapper.create(
        db=db,
        user_id=user.id,
        title=None,
    )
    question = "这是一个超过二十个字符的很长的问题用于测试标题截断"

    ChatService.prepare_turn(
        conversation=conversation,
        question=question,
    )

    db.expire_all()
    saved = db.get(Conversation, conversation.id)
    messages = _messages(db, conversation.id)

    assert saved.title == question[:20]
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == question


def test_prepare_chat_turn_includes_memories(
    db,
    user,
    conversation,
    monkeypatch,
):
    memory = {
        "id": 1,
        "memory_type": "user",
        "title": "偏好",
        "description": "",
        "content": "喜欢表格",
    }
    monkeypatch.setattr(
        chat_service.MemoryService,
        "find_long_term_memories",
        staticmethod(lambda **kwargs: [memory]),
    )

    turn = prepare_chat_turn(
        conversation_id=conversation.id,
        user_id=user.id,
        question="2024 年人口",
    )

    assert turn.conversation_id == conversation.id
    assert turn.user_id == user.id
    assert turn.question == "2024 年人口"
    assert turn.memories == [memory]
    assert len(_messages(db, conversation.id)) == 1


def test_save_assistant_message(db, conversation):
    message_id = ChatService.save_assistant_message(
        conversation_id=conversation.id,
        content="回答",
    )

    message = MessageMapper.find_by_id(db=db, message_id=message_id)

    assert message is not None
    assert message.role == "assistant"
    assert message.content == "回答"


async def test_stream_answer_success(
    db,
    user,
    conversation,
    monkeypatch,
):
    graph = FakeGraph([{"content": "你"}, {"content": "好"}])
    spawned = []
    monkeypatch.setattr(chat_service, "graph", graph)
    monkeypatch.setattr(
        chat_service,
        "_spawn_memory_extraction",
        lambda **kwargs: spawned.append(kwargs),
    )

    events = [
        event
        async for event in ChatService.stream_answer(
            conversation_id=conversation.id,
            user_id=user.id,
            question="人口",
            history=[],
            memories=[{"id": 1}],
        )
    ]

    assert [event["type"] for event in events] == [
        "start",
        "token",
        "token",
        "done",
    ]
    assert events[0]["data"]["conversation_id"] == conversation.id
    assert events[1]["data"]["content"] == "你"
    assert events[-1]["data"]["message_id"] is not None
    assert graph.inputs == {
        "question": "人口",
        "history": [],
        "memories": [{"id": 1}],
    }
    assert spawned == [
        {
            "user_id": user.id,
            "conversation_id": conversation.id,
        }
    ]

    messages = _messages(db, conversation.id)
    assert len(messages) == 1
    assert messages[0].content == "你好"


async def test_stream_answer_saves_partial_on_error(
    db,
    user,
    conversation,
    monkeypatch,
):
    graph = FakeGraph([{"content": "部分"}], error=RuntimeError("boom"))
    spawned = []
    monkeypatch.setattr(chat_service, "graph", graph)
    monkeypatch.setattr(
        chat_service,
        "_spawn_memory_extraction",
        lambda **kwargs: spawned.append(kwargs),
    )

    events = [
        event
        async for event in ChatService.stream_answer(
            conversation_id=conversation.id,
            user_id=user.id,
            question="人口",
            history=[],
            memories=[],
        )
    ]

    assert [event["type"] for event in events] == [
        "start",
        "token",
        "error",
    ]
    assert events[-1]["data"]["code"] == "AGENT_EXECUTION_ERROR"
    assert spawned == []

    messages = _messages(db, conversation.id)
    assert len(messages) == 1
    assert messages[0].content == "部分"


async def test_stream_answer_empty_answer(
    user,
    conversation,
    db,
    monkeypatch,
):
    graph = FakeGraph([])
    spawned = []
    monkeypatch.setattr(chat_service, "graph", graph)
    monkeypatch.setattr(
        chat_service,
        "_spawn_memory_extraction",
        lambda **kwargs: spawned.append(kwargs),
    )

    events = [
        event
        async for event in ChatService.stream_answer(
            conversation_id=conversation.id,
            user_id=user.id,
            question="人口",
            history=[],
            memories=[],
        )
    ]

    assert [event["type"] for event in events] == ["start", "done"]
    assert events[-1]["data"]["message_id"] is None
    assert spawned == []
    assert _messages(db, conversation.id) == []
