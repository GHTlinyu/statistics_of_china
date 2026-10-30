"""记忆提取器：prompt、操作解析与非法输出。"""

import json
from types import SimpleNamespace

import pytest

from backend.agent.memory import memory_extractor


class FakeLLM:
    def __init__(self, content):
        self.content = content
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return SimpleNamespace(content=self.content)


def test_extract_parses_operations(monkeypatch):
    llm = FakeLLM(
        json.dumps(
            {
                "operations": [
                    {
                        "action": "CREATE",
                        "memory_id": None,
                        "memory_type": "feedback",
                        "title": "表格偏好",
                        "description": "用户要求表格",
                        "content": "回答统计数据时使用表格",
                    }
                ]
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr(memory_extractor, "get_llm", lambda: llm)

    result = memory_extractor.extract_memories(
        existing_memories=[
            {
                "id": 1,
                "memory_type": "user",
                "title": "旧标题",
                "description": "旧描述",
                "content": "旧内容",
            }
        ],
        recent_messages=[
            {"role": "user", "content": "以后用表格"},
            {"role": "assistant", "content": "好的"},
        ],
    )

    assert len(result.operations) == 1
    operation = result.operations[0]
    assert operation.action == "CREATE"
    assert operation.memory_type == "feedback"
    assert operation.title == "表格偏好"
    assert "ID: 1" in llm.prompt
    assert "旧标题" in llm.prompt
    assert "user: 以后用表格" in llm.prompt
    assert "assistant: 好的" in llm.prompt


def test_extract_allows_empty_operations(monkeypatch):
    monkeypatch.setattr(
        memory_extractor,
        "get_llm",
        lambda: FakeLLM('{"operations": []}'),
    )

    result = memory_extractor.extract_memories([], [])

    assert result.operations == []


def test_invalid_json_raises(monkeypatch):
    monkeypatch.setattr(
        memory_extractor,
        "get_llm",
        lambda: FakeLLM("not json"),
    )

    with pytest.raises(ValueError):
        memory_extractor.extract_memories([], [])


def test_invalid_schema_raises(monkeypatch):
    monkeypatch.setattr(
        memory_extractor,
        "get_llm",
        lambda: FakeLLM('{"operations": [{"action": "DELETE"}]}'),
    )

    with pytest.raises(ValueError):
        memory_extractor.extract_memories([], [])


def test_non_text_content_raises(monkeypatch):
    monkeypatch.setattr(
        memory_extractor,
        "get_llm",
        lambda: FakeLLM([{"text": "hello"}]),
    )

    with pytest.raises(ValueError):
        memory_extractor.extract_memories([], [])
