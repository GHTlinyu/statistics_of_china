"""Embedding 客户端：任务参数、分批、排序与维度校验。"""

import pytest

from backend.app.retrieval.config import RetrievalConfig
from backend.app.retrieval.embedding import EmbeddingClient
from backend.app.retrieval.exceptions import EmbeddingError


def _config(**overrides):
    values = {
        "embedding_api_key": "key",
        "embedding_base_url": "http://embedding",
        "embedding_model": "embed-model",
        "embedding_dimensions": 3,
        "embedding_task_query": "retrieval.query",
        "embedding_task_document": "retrieval.passage",
        "embedding_batch_size": 2,
        "rerank_api_key": "key",
        "rerank_base_url": "http://rerank",
        "rerank_model": "rerank-model",
        "timeout": 5.0,
        "max_retries": 1,
    }
    values.update(overrides)

    return RetrievalConfig(**values)


def _fake_post(dimensions=3, count_mismatch=False):
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
                "timeout": timeout,
                "max_retries": max_retries,
            }
        )
        inputs = payload["input"]
        data = [
            {
                "index": index,
                "embedding": [float(index)] * dimensions,
            }
            for index in range(len(inputs))
        ]
        if count_mismatch:
            data = data[:-1]
        data.reverse()

        return {"data": data}

    return post_json, calls


def test_embed_query(monkeypatch):
    post, calls = _fake_post()
    monkeypatch.setattr("backend.app.retrieval.embedding.post_json", post)
    client = EmbeddingClient(_config())

    vector = client.embed_query("hello")

    assert vector == [0.0, 0.0, 0.0]
    assert client.dimensions == 3
    assert calls[0]["url"] == "http://embedding/embeddings"
    assert calls[0]["payload"]["task"] == "retrieval.query"
    assert calls[0]["payload"]["model"] == "embed-model"
    assert calls[0]["payload"]["normalized"] is True
    assert calls[0]["payload"]["input"] == [{"text": "hello"}]
    assert calls[0]["api_key"] == "key"


def test_embed_documents_uses_document_task(monkeypatch):
    post, calls = _fake_post()
    monkeypatch.setattr("backend.app.retrieval.embedding.post_json", post)
    client = EmbeddingClient(_config())

    vectors = client.embed_documents(["a", "b"])

    assert [vector[0] for vector in vectors] == [0.0, 1.0]
    assert calls[0]["payload"]["task"] == "retrieval.passage"


def test_embed_queries_batches_and_preserves_order(monkeypatch):
    post, calls = _fake_post()
    monkeypatch.setattr("backend.app.retrieval.embedding.post_json", post)
    client = EmbeddingClient(_config(embedding_batch_size=2))

    vectors = client.embed_queries(["a", "b", "c"])

    assert len(calls) == 2
    assert [len(call["payload"]["input"]) for call in calls] == [2, 1]
    assert [vector[0] for vector in vectors] == [0.0, 1.0, 0.0]


def test_embed_queries_empty_skips_request(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("空输入不应调用接口")

    monkeypatch.setattr(
        "backend.app.retrieval.embedding.post_json",
        explode,
    )
    client = EmbeddingClient(_config())

    assert client.embed_queries([]) == []


def test_dimension_mismatch_raises(monkeypatch):
    post, _ = _fake_post(dimensions=2)
    monkeypatch.setattr("backend.app.retrieval.embedding.post_json", post)
    client = EmbeddingClient(_config(embedding_dimensions=3))

    with pytest.raises(EmbeddingError):
        client.embed_query("hello")


def test_count_mismatch_raises(monkeypatch):
    post, _ = _fake_post(count_mismatch=True)
    monkeypatch.setattr("backend.app.retrieval.embedding.post_json", post)
    client = EmbeddingClient(_config())

    with pytest.raises(EmbeddingError):
        client.embed_queries(["a", "b"])
