"""年鉴检索工具：召回放大、top_k 截断、JSON 输出与会话关闭。"""

import json

import pytest

import backend.agent.tools.retrieval as tool_module
from backend.app.retrieval.retriever import RetrievedChunk


class FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeRetriever:
    instances = []

    def __init__(self, db):
        self.db = db
        self.args = None
        FakeRetriever.instances.append(self)

    def search(self, query, top_k, top_n):
        self.args = (query, top_k, top_n)
        return [
            RetrievedChunk(
                chunk_id="c1",
                title="表 1",
                summary="summary",
                content="content",
                score=0.123456789,
            )
        ]


@pytest.fixture(autouse=True)
def patch_tool(monkeypatch):
    FakeRetriever.instances = []
    session = FakeSession()
    monkeypatch.setattr(tool_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(tool_module, "ChunkRetriever", FakeRetriever)

    return session


def _invoke(top_k):
    raw = tool_module.search_yearbook.invoke(
        {"query": "人口", "top_k": top_k}
    )
    return json.loads(raw)


def test_search_yearbook_defaults(patch_tool):
    payload = _invoke(5)
    retriever = FakeRetriever.instances[0]

    assert retriever.args == ("人口", 20, 5)
    assert payload == [
        {
            "chunk_id": "c1",
            "title": "表 1",
            "content": "content",
            "score": 0.123457,
        }
    ]
    assert patch_tool.closed is True


def test_search_yearbook_recall_factor(patch_tool):
    payload = _invoke(7)

    assert FakeRetriever.instances[0].args == ("人口", 28, 7)
    assert len(payload) == 1


def test_search_yearbook_clamps_top_k(patch_tool):
    assert FakeRetriever.instances == []

    payload = _invoke(0)

    assert FakeRetriever.instances[0].args == ("人口", 20, 1)
    assert len(payload) == 1


def test_search_yearbook_caps_top_k(patch_tool):
    _invoke(99)

    assert FakeRetriever.instances[0].args == ("人口", 40, 10)


def test_search_yearbook_handles_negative_top_k(patch_tool):
    _invoke(-5)

    assert FakeRetriever.instances[0].args == ("人口", 20, 1)
