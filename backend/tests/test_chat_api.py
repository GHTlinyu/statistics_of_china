"""聊天接口：SSE 事件序列、404、参数校验、记忆注入与后台提取。"""

import json

import backend.app.service.chatService as chat_service
from backend.app.mapper.conversationMapper import ConversationMapper
from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.conversation import Conversation
from backend.app.service.conversationService import ConversationService


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


def _parse_events(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: ") :])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def _post_chat(client, conversation_id, headers, content="2024 年人口"):
    return client.post(
        f"/conversation/{conversation_id}/chat",
        json={"content": content},
        headers=headers,
    )


def test_chat_stream_success(
    client,
    auth_headers,
    conversation,
    session_factory,
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

    response = _post_chat(
        client,
        conversation.id,
        auth_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_events(response.text)
    assert [event["type"] for event in events] == [
        "start",
        "token",
        "token",
        "done",
    ]
    assert events[0]["data"]["conversation_id"] == conversation.id
    assert events[-1]["data"]["message_id"] is not None
    assert spawned == [
        {
            "user_id": conversation.user_id,
            "conversation_id": conversation.id,
        }
    ]

    with session_factory() as db:
        messages, total = MessageMapper.list_by_conversation(
            db=db,
            conversation_id=conversation.id,
            page=1,
            page_size=20,
        )

    assert total == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert messages[1].content == "你好"


def test_chat_returns_404_for_foreign_conversation(
    client,
    db,
    auth_headers,
    other_user,
):
    foreign = ConversationService.create_conversation(
        db=db,
        user_id=other_user.id,
        title="other",
    )

    response = _post_chat(client, foreign.id, auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


def test_chat_validates_content(client, auth_headers, conversation):
    response = _post_chat(
        client,
        conversation.id,
        auth_headers,
        content="",
    )

    assert response.status_code == 422


def test_chat_auto_fills_title(
    client,
    db,
    user,
    auth_headers,
    monkeypatch,
):
    conversation = ConversationMapper.create(
        db=db,
        user_id=user.id,
        title=None,
    )
    monkeypatch.setattr(
        chat_service,
        "graph",
        FakeGraph([{"content": "ok"}]),
    )
    monkeypatch.setattr(
        chat_service,
        "_spawn_memory_extraction",
        lambda **kwargs: None,
    )

    response = _post_chat(
        client,
        conversation.id,
        auth_headers,
        content="2024年全国人口是多少",
    )

    assert response.status_code == 200

    db.expire_all()
    saved = db.get(Conversation, conversation.id)
    assert saved.title == "2024年全国人口是多少"


def test_chat_injects_memories(
    client,
    auth_headers,
    conversation,
    monkeypatch,
):
    memory = {
        "id": 1,
        "memory_type": "feedback",
        "title": "格式",
        "description": "",
        "content": "用表格",
    }
    graph = FakeGraph([{"content": "ok"}])
    monkeypatch.setattr(chat_service, "graph", graph)
    monkeypatch.setattr(
        chat_service,
        "_spawn_memory_extraction",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        chat_service.MemoryService,
        "find_long_term_memories",
        staticmethod(lambda **kwargs: [memory]),
    )

    response = _post_chat(client, conversation.id, auth_headers)

    assert response.status_code == 200
    assert graph.inputs["memories"] == [memory]


def test_chat_returns_error_event_on_graph_failure(
    client,
    auth_headers,
    conversation,
    monkeypatch,
):
    graph = FakeGraph([{"content": "部分"}], error=RuntimeError("boom"))
    monkeypatch.setattr(chat_service, "graph", graph)
    monkeypatch.setattr(
        chat_service,
        "_spawn_memory_extraction",
        lambda **kwargs: None,
    )

    response = _post_chat(client, conversation.id, auth_headers)

    events = _parse_events(response.text)

    assert [event["type"] for event in events] == [
        "start",
        "token",
        "error",
    ]
    assert events[-1]["data"]["code"] == "AGENT_EXECUTION_ERROR"
