"""记忆更新器：prompt、MERGE / REPLACE 解析与非法输出。"""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.agent.memory import memory_updater
from backend.agent.schema.memory_schema import MemoryOperation


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return SimpleNamespace(content=self.content)


def _new_memory():
    return MemoryOperation(
        action="CREATE",
        memory_type="feedback",
        title="新标题",
        description="新描述",
        content="新内容",
    )


def test_returns_merge_decision(monkeypatch):
    llm = FakeLLM(
        json.dumps(
            {
                "action": "MERGE",
                "memory_id": 3,
                "title": "合并标题",
                "description": "合并描述",
                "content": "合并内容",
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr(memory_updater, "get_llm", lambda: llm)

    decision = memory_updater.decide_memory_update(
        new_memory=_new_memory(),
        existing_memories=[
            {
                "id": 3,
                "title": "旧标题",
                "description": "旧描述",
                "content": "旧内容",
            }
        ],
        oldest_memory_id=3,
    )

    assert decision.action == "MERGE"
    assert decision.memory_id == 3
    assert decision.title == "合并标题"
    assert "新标题" in llm.prompt
    assert "旧标题" in llm.prompt
    assert "最旧记忆ID" in llm.prompt


def test_returns_replace_decision(monkeypatch):
    monkeypatch.setattr(
        memory_updater,
        "get_llm",
        lambda: FakeLLM(
            '{"action": "REPLACE", "memory_id": 1, '
            '"title": "t", "description": "d", "content": "c"}'
        ),
    )

    decision = memory_updater.decide_memory_update(
        new_memory=_new_memory(),
        existing_memories=[],
        oldest_memory_id=1,
    )

    assert decision.action == "REPLACE"
    assert decision.memory_id == 1


def test_invalid_json_raises(monkeypatch):
    monkeypatch.setattr(
        memory_updater,
        "get_llm",
        lambda: FakeLLM("not json"),
    )

    with pytest.raises(json.JSONDecodeError):
        memory_updater.decide_memory_update(_new_memory(), [], 1)


def test_invalid_schema_raises(monkeypatch):
    monkeypatch.setattr(
        memory_updater,
        "get_llm",
        lambda: FakeLLM(
            '{"action": "KEEP", "memory_id": 1, '
            '"title": "t", "description": "d", "content": "c"}'
        ),
    )

    with pytest.raises(ValidationError):
        memory_updater.decide_memory_update(_new_memory(), [], 1)


def test_non_text_content_raises(monkeypatch):
    monkeypatch.setattr(
        memory_updater,
        "get_llm",
        lambda: FakeLLM([{"text": "hello"}]),
    )

    with pytest.raises(ValueError):
        memory_updater.decide_memory_update(_new_memory(), [], 1)
