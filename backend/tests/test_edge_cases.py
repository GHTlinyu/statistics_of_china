"""边界用例：后台任务、异常分支、LLM 可选参数与检索空输入。"""

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import backend.agent.client.llm as llm_module
import backend.agent.memory.memory_finder as memory_finder
import backend.app.service.chatService as chat_service
import backend.app.service.memoryService as memory_service
from backend.agent.client.config import LLMConfig
from backend.agent.client.llm import LLMClient
from backend.agent.schema.memory_finder_schema import MemoryFinderResult
from backend.agent.schema.memory_schema import MemoryOperation
from backend.agent.schema.memory_updater_schema import MemoryUpdateDecision
from backend.agent.workflow import nodes
from backend.app.mapper.memoryMapper import MemoryMapper
from backend.app.model.memory import Memory
from backend.app.retrieval.config import RetrievalConfig
from backend.app.retrieval.embedding import EmbeddingClient
from backend.app.retrieval.ranker import Reranker
from backend.app.retrieval.retriever import ChunkRetriever
from backend.app.service.memoryService import MemoryService


@pytest.fixture(autouse=True)
def patch_sessions(monkeypatch, session_factory):
    monkeypatch.setattr(memory_service, "SessionLocal", session_factory)
    monkeypatch.setattr(chat_service, "SessionLocal", session_factory)


class Sample(BaseModel):
    answer: str


class DictRunner:
    def invoke(self, messages, **kwargs):
        return {"answer": "ok"}

    async def ainvoke(self, messages, **kwargs):
        return {"answer": "ok"}


class DictModel:
    def with_structured_output(self, schema, **kwargs):
        return DictRunner()


class FakeGraph:
    def __init__(self, chunks, error=None):
        self.chunks = chunks
        self.error = error

    async def astream(self, inputs, stream_mode):
        for chunk in self.chunks:
            yield chunk
        if self.error is not None:
            raise self.error


class FakeLLM:
    def __init__(self, pieces):
        self.pieces = pieces

    async def astream(self, messages):
        for piece in self.pieces:
            yield piece


class FakeWriter:
    def __init__(self):
        self.writes = []

    def __call__(self, value):
        self.writes.append(value)


def _memory(db, user_id, content="old"):
    return MemoryMapper.create(
        db=db,
        memory=Memory(
            user_id=user_id,
            memory_type="user",
            title="title",
            description="desc",
            content=content,
        ),
    )


def test_create_model_passes_optional_params(monkeypatch):
    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_module, "ChatOpenAI", FakeChat)
    config = LLMConfig(
        model="m",
        api_key="k",
        base_url="http://base",
        temperature=0.2,
        timeout=10.0,
        max_retries=3,
    )

    llm_module._create_model(config)

    assert captured == {
        "model": "m",
        "api_key": "k",
        "temperature": 0.2,
        "base_url": "http://base",
        "timeout": 10.0,
        "max_retries": 3,
    }


def test_llm_client_from_config(monkeypatch):
    config = LLMConfig(
        model="m",
        api_key="k",
        base_url=None,
        temperature=0.0,
        timeout=None,
        max_retries=2,
    )
    sentinel = object()
    monkeypatch.setattr(llm_module, "load_llm_config", lambda: config)
    monkeypatch.setattr(llm_module, "_create_model", lambda _: sentinel)

    client = LLMClient()

    assert client.config is config
    assert client.model is sentinel


def test_structured_output_dict_result():
    llm = LLMClient(model=DictModel())

    assert llm.chat_json("hello", schema=Sample) == {"answer": "ok"}


async def test_async_structured_output_dict_result():
    llm = LLMClient(model=DictModel())

    assert await llm.achat_json("hello", schema=Sample) == {"answer": "ok"}


def test_memory_finder_rejects_non_text_content(monkeypatch):
    class FakeLLM:
        def invoke(self, prompt):
            return SimpleNamespace(content=[{"text": "hello"}])

    monkeypatch.setattr(memory_finder, "get_llm", lambda: FakeLLM())

    with pytest.raises(ValueError):
        memory_finder.find_memories(
            [{"id": 1, "title": "t", "description": "d"}],
            [],
        )


def test_embedding_and_ranker_config_properties():
    config = RetrievalConfig(
        embedding_api_key="key",
        embedding_base_url="http://embedding",
        embedding_model="model",
        embedding_dimensions=3,
        embedding_task_query="query",
        embedding_task_document="document",
        embedding_batch_size=2,
        rerank_api_key="key",
        rerank_base_url="http://rerank",
        rerank_model="model",
        timeout=5.0,
        max_retries=1,
    )

    assert EmbeddingClient(config).config is config
    assert Reranker(config).config is config


def test_attach_content_empty_chunks():
    config = RetrievalConfig(
        embedding_api_key="key",
        embedding_base_url="http://embedding",
        embedding_model="model",
        embedding_dimensions=3,
        embedding_task_query="query",
        embedding_task_document="document",
        embedding_batch_size=2,
        rerank_api_key="key",
        rerank_base_url="http://rerank",
        rerank_model="model",
        timeout=5.0,
        max_retries=1,
    )
    retriever = ChunkRetriever(
        db=object(),
        embedding=object(),
        ranker=object(),
        config=config,
    )

    assert retriever._attach_content([]) == []


def test_build_memory_context_all_unknown():
    assert (
        nodes.build_memory_context(
            [{"memory_type": "other", "title": "t", "content": "c"}]
        )
        == "无相关长期记忆。"
    )


async def test_generate_node_skips_empty_piece(monkeypatch):
    writer = FakeWriter()
    monkeypatch.setattr(nodes, "get_llm", lambda: FakeLLM(["", "ok"]))
    monkeypatch.setattr(nodes, "get_stream_writer", lambda: writer)

    result = await nodes.generate_node(
        {
            "question": "q",
            "documents": [],
            "history": [],
            "memories": [],
        }
    )

    assert result == {"answer": "ok"}
    assert writer.writes == [{"content": "ok"}]


async def test_stream_answer_skips_empty_chunks(
    user,
    conversation,
    monkeypatch,
):
    monkeypatch.setattr(
        chat_service,
        "graph",
        FakeGraph([{"foo": "bar"}, {"content": "ok"}]),
    )
    monkeypatch.setattr(
        chat_service,
        "_spawn_memory_extraction",
        lambda **kwargs: None,
    )

    events = [
        event
        async for event in chat_service.ChatService.stream_answer(
            conversation_id=conversation.id,
            user_id=user.id,
            question="q",
            history=[],
            memories=[],
        )
    ]

    assert [event["type"] for event in events] == [
        "start",
        "token",
        "done",
    ]
    assert events[1]["data"]["content"] == "ok"


async def test_stream_answer_handles_partial_save_failure(
    user,
    conversation,
    monkeypatch,
):
    def explode(*args, **kwargs):
        raise RuntimeError("save failed")

    monkeypatch.setattr(
        chat_service,
        "graph",
        FakeGraph([{"content": "partial"}], error=RuntimeError("boom")),
    )
    monkeypatch.setattr(
        chat_service.ChatService,
        "save_assistant_message",
        staticmethod(explode),
    )

    events = [
        event
        async for event in chat_service.ChatService.stream_answer(
            conversation_id=conversation.id,
            user_id=user.id,
            question="q",
            history=[],
            memories=[],
        )
    ]

    assert [event["type"] for event in events] == [
        "start",
        "token",
        "error",
    ]


async def test_spawn_memory_extraction_success(monkeypatch):
    called = []

    def fake_extract(**kwargs):
        called.append(kwargs)

    monkeypatch.setattr(
        chat_service.MemoryService,
        "extract_and_save",
        staticmethod(fake_extract),
    )
    chat_service._extraction_tasks.clear()

    chat_service._spawn_memory_extraction(user_id=1, conversation_id=2)
    while chat_service._extraction_tasks:
        await asyncio.gather(*list(chat_service._extraction_tasks))

    assert called == [{"user_id": 1, "conversation_id": 2}]
    assert chat_service._extraction_tasks == set()


async def test_on_extraction_done_ignores_cancelled_task():
    async def never_finishes():
        await asyncio.sleep(10)

    task = asyncio.create_task(never_finishes())
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    chat_service._extraction_tasks.add(task)
    chat_service._on_extraction_done(task)

    assert task not in chat_service._extraction_tasks


async def test_spawn_memory_extraction_error_is_logged(monkeypatch):
    def explode(**kwargs):
        raise RuntimeError("extract failed")

    monkeypatch.setattr(
        chat_service.MemoryService,
        "extract_and_save",
        staticmethod(explode),
    )
    chat_service._extraction_tasks.clear()

    chat_service._spawn_memory_extraction(user_id=1, conversation_id=2)
    while chat_service._extraction_tasks:
        await asyncio.gather(
            *list(chat_service._extraction_tasks),
            return_exceptions=True,
        )

    assert chat_service._extraction_tasks == set()


def test_memory_read_returns_empty_for_empty_finder_result(
    db,
    user,
    conversation,
    monkeypatch,
):
    _memory(db, user.id)
    monkeypatch.setattr(
        memory_service,
        "find_memories",
        lambda **kwargs: MemoryFinderResult(),
    )

    result = MemoryService.find_long_term_memories(
        user_id=user.id,
        conversation_id=conversation.id,
        current_question="q",
    )

    assert result == []


def test_memory_update_without_id_is_ignored(user):
    MemoryService._apply_update(
        user_id=user.id,
        operation=MemoryOperation(
            action="UPDATE",
            memory_id=None,
            memory_type="user",
            title="t",
            description="d",
            content="c",
        ),
    )


def test_memory_merge_target_missing_is_ignored(
    db,
    user,
    monkeypatch,
):
    candidate = _memory(db, user.id)
    monkeypatch.setattr(
        memory_service,
        "decide_memory_update",
        lambda **kwargs: MemoryUpdateDecision(
            action="MERGE",
            memory_id=candidate.id,
            title="t",
            description="d",
            content="c",
        ),
    )
    monkeypatch.setattr(
        memory_service.MemoryMapper,
        "find_by_id",
        staticmethod(lambda **kwargs: None),
    )

    MemoryService._merge_or_replace(
        user_id=user.id,
        operation=MemoryOperation(
            action="CREATE",
            memory_type="user",
            title="t",
            description="d",
            content="c",
        ),
        candidates=[candidate],
    )


def test_memory_replace_oldest_when_none(user):
    MemoryService._replace_oldest(
        user_id=user.id,
        operation=MemoryOperation(
            action="CREATE",
            memory_type="user",
            title="t",
            description="d",
            content="c",
        ),
    )
