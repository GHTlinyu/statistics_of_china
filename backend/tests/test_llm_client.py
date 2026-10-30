"""大模型客户端：文本提取、JSON 解析、流式、中断与配置。"""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from backend.agent.client import get_llm, reset_llm
from backend.agent.client.config import load_llm_config
from backend.agent.client.exceptions import (
    LLMConfigurationError,
    LLMResponseError,
)
from backend.agent.client.llm import (
    InterruptToken,
    LLMClient,
    _extract_text,
    _parse_json,
)


class SampleModel(BaseModel):
    answer: str


class FakeStructuredRunner:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, messages, **kwargs):
        return SampleModel(answer="ok")

    async def ainvoke(self, messages, **kwargs):
        return SampleModel(answer="ok")


class FakeModel:
    def __init__(self, content="hello", pieces=("a", "b")):
        self.content = content
        self.pieces = list(pieces)
        self.last_kwargs = {}
        self.bound_tools = None

    def invoke(self, messages, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=self.content)

    async def ainvoke(self, messages, **kwargs):
        return self.invoke(messages, **kwargs)

    def stream(self, messages, **kwargs):
        for piece in self.pieces:
            yield SimpleNamespace(content=piece)

    async def astream(self, messages, **kwargs):
        for piece in self.pieces:
            yield SimpleNamespace(content=piece)

    def with_structured_output(self, schema, **kwargs):
        return FakeStructuredRunner(schema)

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = tools
        return self


def test_extract_text_variants():
    assert _extract_text(SimpleNamespace(content="abc")) == "abc"
    assert (
        _extract_text(
            SimpleNamespace(
                content=[
                    {"text": "a"},
                    "b",
                    SimpleNamespace(text="c"),
                ]
            )
        )
        == "abc"
    )
    assert _extract_text(SimpleNamespace(content=None)) == ""
    assert _extract_text(SimpleNamespace(content=123)) == "123"


def test_parse_json_plain_and_code_fence():
    assert _parse_json('{"a": 1}') == {"a": 1}
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('```\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_rejects_invalid():
    with pytest.raises(LLMResponseError):
        _parse_json("not json")

    with pytest.raises(LLMResponseError):
        _parse_json("[1, 2]")


def test_chat_and_invoke():
    llm = LLMClient(model=FakeModel())

    assert llm.chat("hello") == "hello"
    assert llm.invoke("hello").content == "hello"
    assert llm.config is None


def test_chat_json_and_structured_output():
    model = FakeModel(content='{"a": 1}')
    llm = LLMClient(model=model)

    assert llm.chat_json("hello") == {"a": 1}
    assert model.last_kwargs["response_format"] == {"type": "json_object"}
    assert llm.chat_json("hello", schema=SampleModel) == {"answer": "ok"}


def test_stream_stops_on_interrupt_token():
    llm = LLMClient(model=FakeModel())
    token = InterruptToken()
    token.stop()

    assert list(llm.stream("hello", interrupt=token)) == []

    token.reset()
    pieces = []
    for piece in llm.stream("hello", interrupt=token):
        pieces.append(piece)
        token.stop()

    assert pieces == ["a"]


def test_interrupt_token_properties():
    token = InterruptToken()

    assert token.is_set() is False
    assert token.stopped is False
    token.stop()
    assert token.is_set() is True
    assert token.stopped is True
    token.reset()
    assert token.is_set() is False


def test_bind_tools_and_with_structured_output():
    model = FakeModel()
    llm = LLMClient(model=model)

    assert llm.bind_tools([1, 2]) is model
    assert model.bound_tools == [1, 2]
    runner = llm.with_structured_output(SampleModel)
    assert runner.schema is SampleModel


async def test_async_methods_and_interrupt():
    llm = LLMClient(model=FakeModel(pieces=("x", "y")))

    assert await llm.achat("hello") == "hello"
    pieces = [piece async for piece in llm.astream("hello")]
    assert pieces == ["x", "y"]

    token = InterruptToken()
    token.stop()
    assert [piece async for piece in llm.astream("hello", interrupt=token)] == []

    token.reset()
    pieces = []
    async for piece in llm.astream("hello", interrupt=token):
        pieces.append(piece)
        token.stop()
    assert pieces == ["x"]


async def test_async_json():
    model = FakeModel(content='{"a": 1}')
    llm = LLMClient(model=model)

    assert await llm.achat_json("hello") == {"a": 1}
    assert await llm.achat_json("hello", schema=SampleModel) == {"answer": "ok"}


def test_load_llm_config_defaults(monkeypatch):
    for key in (
        "LLM_BASE_URL",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_RETRIES",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    config = load_llm_config()

    assert config.model == "test-model"
    assert config.api_key == "test-key"
    assert config.base_url is None
    assert config.temperature == 0.0
    assert config.timeout is None
    assert config.max_retries == 2


def test_load_llm_config_missing_required(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(LLMConfigurationError) as exc_info:
        load_llm_config()

    assert "LLM_MODEL" in str(exc_info.value)
    assert "LLM_API_KEY" in str(exc_info.value)


def test_load_llm_config_rejects_invalid_numbers(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_TEMPERATURE", "hot")

    with pytest.raises(LLMConfigurationError):
        load_llm_config()

    monkeypatch.delenv("LLM_TEMPERATURE")
    monkeypatch.setenv("LLM_MAX_RETRIES", "many")

    with pytest.raises(LLMConfigurationError):
        load_llm_config()


def test_get_llm_is_cached(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    reset_llm()

    try:
        first = get_llm()
        second = get_llm()

        assert first is second
        assert first.config is not None
        assert first.config.model == "test-model"
    finally:
        reset_llm()
