"""Rerank 客户端：结果解析、top_n 与非法响应。"""

import pytest

from backend.app.retrieval.config import RetrievalConfig
from backend.app.retrieval.exceptions import RerankError
from backend.app.retrieval.ranker import Reranker


def _config(**overrides):
    values = {
        "embedding_api_key": "key",
        "embedding_base_url": "http://embedding",
        "embedding_model": "embed-model",
        "embedding_dimensions": 3,
        "embedding_task_query": "retrieval.query",
        "embedding_task_document": "retrieval.passage",
        "embedding_batch_size": 2,
        "rerank_api_key": "rerank-key",
        "rerank_base_url": "http://rerank",
        "rerank_model": "rerank-model",
        "timeout": 5.0,
        "max_retries": 1,
    }
    values.update(overrides)

    return RetrievalConfig(**values)


def _fake_post(response):
    calls = []

    def post_json(
        url,
        payload,
        *,
        api_key,
        timeout,
        max_retries,
        error_type,
    ):
        calls.append(
            {
                "url": url,
                "payload": payload,
                "api_key": api_key,
            }
        )
        if isinstance(response, Exception):
            raise response
        return response

    return post_json, calls


def test_rerank_returns_ranked_pairs(monkeypatch):
    post, calls = _fake_post(
        {
            "results": [
                {"index": 1, "relevance_score": 0.9},
                {"index": 0, "relevance_score": 0.5},
            ]
        }
    )
    monkeypatch.setattr("backend.app.retrieval.ranker.post_json", post)
    ranker = Reranker(_config())

    ranked = ranker.rerank("query", ["a", "b"], top_n=2)

    assert ranked == [(1, 0.9), (0, 0.5)]
    assert ranker._url == "http://rerank/rerank"
    assert calls[0]["url"] == "http://rerank/rerank"
    assert calls[0]["api_key"] == "rerank-key"
    assert calls[0]["payload"] == {
        "model": "rerank-model",
        "query": "query",
        "documents": ["a", "b"],
        "top_n": 2,
        "return_documents": False,
    }


def test_rerank_empty_documents_skips_call(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("空文档不应调用接口")

    monkeypatch.setattr("backend.app.retrieval.ranker.post_json", explode)

    assert Reranker(_config()).rerank("query", []) == []


def test_rerank_data_fallback(monkeypatch):
    post, _ = _fake_post(
        {"data": [{"index": 0, "score": 0.7}]}
    )
    monkeypatch.setattr("backend.app.retrieval.ranker.post_json", post)

    assert Reranker(_config()).rerank("query", ["a"]) == [(0, 0.7)]


def test_rerank_skips_invalid_items(monkeypatch):
    post, _ = _fake_post(
        {
            "results": [
                {"index": 5, "relevance_score": 0.9},
                {"index": 0},
                {"foo": "bar"},
            ]
        }
    )
    monkeypatch.setattr("backend.app.retrieval.ranker.post_json", post)

    with pytest.raises(RerankError):
        Reranker(_config()).rerank("query", ["a"])


def test_rerank_top_n_is_clamped(monkeypatch):
    post, calls = _fake_post(
        {"results": [{"index": 0, "relevance_score": 0.9}]}
    )
    monkeypatch.setattr("backend.app.retrieval.ranker.post_json", post)

    ranked = Reranker(_config()).rerank(
        "query",
        ["a", "b"],
        top_n=5,
    )

    assert calls[0]["payload"]["top_n"] == 2
    assert len(ranked) == 1


def test_rerank_none_top_n_uses_document_count(monkeypatch):
    post, calls = _fake_post(
        {"results": [{"index": 0, "relevance_score": 0.9}]}
    )
    monkeypatch.setattr("backend.app.retrieval.ranker.post_json", post)

    Reranker(_config()).rerank(
        "query",
        ["a", "b", "c"],
        top_n=None,
    )

    assert calls[0]["payload"]["top_n"] == 3
