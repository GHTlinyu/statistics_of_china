"""记忆查找器：prompt、空目录、ID 过滤与解析失败。"""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.agent.memory import memory_finder
from backend.agent.schema.memory_finder_schema import MemoryFinderResult


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return SimpleNamespace(content=self.content)


def test_empty_catalog_skips_llm(monkeypatch):
    def explode():
        raise AssertionError("LLM 不应被调用")

    monkeypatch.setattr(memory_finder, "get_llm", explode)

    result = memory_finder.find_memories([], [{"role": "user", "content": "hi"}])

    assert result == MemoryFinderResult()


def test_prompt_and_result(monkeypatch):
    llm = FakeLLM('{"memory_ids": [1, 2]}')
    monkeypatch.setattr(memory_finder, "get_llm", lambda: llm)

    result = memory_finder.find_memories(
        memory_catalog=[
            {"id": 1, "title": "偏好", "description": "喜欢表格"},
            {"id": 2, "title": "指导", "description": "注明来源"},
        ],
        recent_user_messages=[
            {"role": "user", "content": "hello"},
        ],
    )

    assert result.memory_ids == [1, 2]
    assert "ID: 1" in llm.prompt
    assert "标题: 偏好" in llm.prompt
    assert "1. hello" in llm.prompt
    assert "{'role'" not in llm.prompt


def test_filters_unknown_ids_and_dedupes(monkeypatch):
    llm = FakeLLM('{"memory_ids": [2, 2, 99]}')
    monkeypatch.setattr(memory_finder, "get_llm", lambda: llm)

    result = memory_finder.find_memories(
        memory_catalog=[
            {"id": 1, "title": "a", "description": "a"},
            {"id": 2, "title": "b", "description": "b"},
        ],
        recent_user_messages=[],
    )

    assert result.memory_ids == [2]


def test_invalid_json_raises(monkeypatch):
    monkeypatch.setattr(
        memory_finder,
        "get_llm",
        lambda: FakeLLM("not json"),
    )

    with pytest.raises(json.JSONDecodeError):
        memory_finder.find_memories(
            [{"id": 1, "title": "a", "description": "a"}],
            [],
        )


def test_invalid_schema_raises(monkeypatch):
    monkeypatch.setattr(
        memory_finder,
        "get_llm",
        lambda: FakeLLM('{"memory_ids": "x"}'),
    )

    with pytest.raises(ValidationError):
        memory_finder.find_memories(
            [{"id": 1, "title": "a", "description": "a"}],
            [],
        )
