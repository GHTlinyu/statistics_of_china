"""记忆服务：读路径、写路径、容量淘汰与失败降级。"""

import pytest

import backend.app.service.memoryService as memory_service
from backend.agent.schema.memory_finder_schema import MemoryFinderResult
from backend.agent.schema.memory_schema import (
    MemoryExtractionResult,
    MemoryOperation,
)
from backend.agent.schema.memory_updater_schema import MemoryUpdateDecision
from backend.app.mapper.memoryMapper import MemoryMapper
from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.memory import Memory
from backend.app.model.message import Message
from backend.app.service.memoryService import MemoryService


@pytest.fixture(autouse=True)
def patch_session_local(monkeypatch, session_factory):
    monkeypatch.setattr(memory_service, "SessionLocal", session_factory)


def _create_memory(
    db,
    user_id,
    memory_type="user",
    title="标题",
    description="描述",
    content="内容",
):
    return MemoryMapper.create(
        db=db,
        memory=Memory(
            user_id=user_id,
            memory_type=memory_type,
            title=title,
            description=description,
            content=content,
        ),
    )


def _create_message(db, conversation_id, role="user", content="hello"):
    return MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        ),
    )


def _memories(session_factory, user_id):
    with session_factory() as db:
        return MemoryMapper.list_by_user(db=db, user_id=user_id)


def _seed_full_memories(db, user_id):
    memories = []
    for index in range(5):
        memories.append(
            _create_memory(
                db,
                user_id,
                memory_type="user",
                title=f"u{index}",
                content=f"u-content-{index}",
            )
        )
        memories.append(
            _create_memory(
                db,
                user_id,
                memory_type="feedback",
                title=f"f{index}",
                content=f"f-content-{index}",
            )
        )
    return memories


def test_read_without_catalog_skips_finder(
    db,
    user,
    conversation,
    monkeypatch,
):
    def explode(**kwargs):
        raise AssertionError("目录为空时不应调用 finder")

    monkeypatch.setattr(memory_service, "find_memories", explode)

    result = MemoryService.find_long_term_memories(
        user_id=user.id,
        conversation_id=conversation.id,
        current_question="问题",
    )

    assert result == []


def test_read_uses_recent_user_messages_and_filters_ownership(
    db,
    user,
    other_user,
    conversation,
    monkeypatch,
):
    own = _create_memory(db, user.id, title="偏好")
    foreign = _create_memory(db, other_user.id, title="别人的")
    for content in ["q1", "q2", "q3", "q4"]:
        _create_message(db, conversation.id, content=content)
    _create_message(db, conversation.id, role="assistant", content="a4")

    captured = {}

    def fake_find(memory_catalog, recent_user_messages):
        captured["catalog"] = memory_catalog
        captured["messages"] = recent_user_messages
        return MemoryFinderResult(memory_ids=[own.id, foreign.id])

    monkeypatch.setattr(memory_service, "find_memories", fake_find)

    result = MemoryService.find_long_term_memories(
        user_id=user.id,
        conversation_id=conversation.id,
        current_question="现在的问题",
    )

    assert [message["content"] for message in captured["messages"]] == [
        "q3",
        "q4",
        "现在的问题",
    ]
    assert [memory["id"] for memory in captured["catalog"]] == [own.id]
    assert [memory["id"] for memory in result] == [own.id]


def test_read_swallows_finder_error(db, user, conversation, monkeypatch):
    _create_memory(db, user.id)

    def explode(**kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(memory_service, "find_memories", explode)

    result = MemoryService.find_long_term_memories(
        user_id=user.id,
        conversation_id=conversation.id,
        current_question="问题",
    )

    assert result == []


def test_extract_creates_memory(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    _create_message(db, conversation.id, content="以后用表格")
    _create_message(db, conversation.id, role="assistant", content="好的")

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="CREATE",
                    memory_type="feedback",
                    title="表格偏好",
                    description="用户要求表格",
                    content="回答统计数据时使用表格",
                )
            ]
        ),
    )

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    memories = _memories(session_factory, user.id)

    assert len(memories) == 1
    assert memories[0].memory_type == "feedback"
    assert memories[0].title == "表格偏好"
    assert memories[0].source_conversation_id == conversation.id


def test_extract_updates_own_memory(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    memory = _create_memory(db, user.id, content="old")
    _create_message(db, conversation.id)

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="UPDATE",
                    memory_id=memory.id,
                    memory_type="user",
                    title="new",
                    description="new desc",
                    content="new content",
                )
            ]
        ),
    )

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    memories = _memories(session_factory, user.id)

    assert memories[0].title == "new"
    assert memories[0].content == "new content"


def test_extract_ignores_foreign_update(
    db,
    user,
    other_user,
    conversation,
    session_factory,
    monkeypatch,
):
    own = _create_memory(db, user.id, content="own")
    foreign = _create_memory(db, other_user.id, content="foreign")
    _create_message(db, conversation.id)

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="UPDATE",
                    memory_id=foreign.id,
                    memory_type="user",
                    title="hijack",
                    description="hijack",
                    content="hijack",
                )
            ]
        ),
    )

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    assert _memories(session_factory, user.id)[0].content == "own"
    assert _memories(session_factory, other_user.id)[0].content == "foreign"


def test_extract_failure_is_swallowed(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    _create_message(db, conversation.id)

    def explode(**kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(memory_service, "extract_memories", explode)

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    assert _memories(session_factory, user.id) == []


def test_extract_without_messages_skips(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    def explode(**kwargs):
        raise AssertionError("没有消息时不应调用 extractor")

    monkeypatch.setattr(memory_service, "extract_memories", explode)

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    assert _memories(session_factory, user.id) == []


def test_capacity_merges_same_type(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    memories = _seed_full_memories(db, user.id)
    user_memories = [
        memory for memory in memories if memory.memory_type == "user"
    ]
    target = user_memories[1]
    _create_message(db, conversation.id)

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="CREATE",
                    memory_type="user",
                    title="merged",
                    description="merged",
                    content="merged-content",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        memory_service,
        "decide_memory_update",
        lambda **kwargs: MemoryUpdateDecision(
            action="MERGE",
            memory_id=target.id,
            title="merged",
            description="merged",
            content="merged-content",
        ),
    )

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    result = _memories(session_factory, user.id)
    by_id = {memory.id: memory for memory in result}

    assert len(result) == 10
    assert by_id[target.id].content == "merged-content"


def test_capacity_replace_forces_oldest_same_type(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    memories = _seed_full_memories(db, user.id)
    user_memories = [
        memory for memory in memories if memory.memory_type == "user"
    ]
    oldest = user_memories[0]
    another = user_memories[-1]
    _create_message(db, conversation.id)

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="CREATE",
                    memory_type="user",
                    title="replaced",
                    description="replaced",
                    content="replaced-content",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        memory_service,
        "decide_memory_update",
        lambda **kwargs: MemoryUpdateDecision(
            action="REPLACE",
            memory_id=another.id,
            title="replaced",
            description="replaced",
            content="replaced-content",
        ),
    )

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    result = _memories(session_factory, user.id)
    by_id = {memory.id: memory for memory in result}

    assert len(result) == 10
    assert by_id[oldest.id].content == "replaced-content"
    assert by_id[another.id].content != "replaced-content"


def test_capacity_without_same_type_replaces_global_oldest(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    memories = [
        _create_memory(
            db,
            user.id,
            memory_type="feedback",
            title=f"f{index}",
            content=f"f-content-{index}",
        )
        for index in range(10)
    ]
    oldest = memories[0]
    _create_message(db, conversation.id)

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="CREATE",
                    memory_type="user",
                    title="new",
                    description="new",
                    content="new-content",
                )
            ]
        ),
    )

    def explode(**kwargs):
        raise AssertionError("没有同类型记忆时不应调用 updater")

    monkeypatch.setattr(memory_service, "decide_memory_update", explode)

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    result = _memories(session_factory, user.id)
    by_id = {memory.id: memory for memory in result}

    assert len(result) == 10
    assert by_id[oldest.id].memory_type == "user"
    assert by_id[oldest.id].content == "new-content"


def test_capacity_ignores_invalid_merge_id(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    _seed_full_memories(db, user.id)
    _create_message(db, conversation.id)
    before = {
        memory.id: memory.content
        for memory in _memories(session_factory, user.id)
    }

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="CREATE",
                    memory_type="user",
                    title="x",
                    description="x",
                    content="x",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        memory_service,
        "decide_memory_update",
        lambda **kwargs: MemoryUpdateDecision(
            action="MERGE",
            memory_id=999_999,
            title="x",
            description="x",
            content="x",
        ),
    )

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    after = {
        memory.id: memory.content
        for memory in _memories(session_factory, user.id)
    }

    assert after == before


def test_capacity_updater_failure_skips_create(
    db,
    user,
    conversation,
    session_factory,
    monkeypatch,
):
    _seed_full_memories(db, user.id)
    _create_message(db, conversation.id)
    before = {
        memory.id: memory.content
        for memory in _memories(session_factory, user.id)
    }

    monkeypatch.setattr(
        memory_service,
        "extract_memories",
        lambda **kwargs: MemoryExtractionResult(
            operations=[
                MemoryOperation(
                    action="CREATE",
                    memory_type="user",
                    title="x",
                    description="x",
                    content="x",
                )
            ]
        ),
    )

    def explode(**kwargs):
        raise RuntimeError("updater down")

    monkeypatch.setattr(memory_service, "decide_memory_update", explode)

    MemoryService.extract_and_save(
        user_id=user.id,
        conversation_id=conversation.id,
    )

    after = {
        memory.id: memory.content
        for memory in _memories(session_factory, user.id)
    }

    assert after == before
