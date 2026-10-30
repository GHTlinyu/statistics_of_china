"""检索配置：默认值、必填校验与数值类型校验。"""

import pytest

from backend.app.retrieval.config import load_retrieval_config
from backend.app.retrieval.exceptions import RagConfigurationError

ENV_KEYS = [
    "LLM_EMBEDDING_API_KEY",
    "LLM_EMBEDDING_BASE_URL",
    "LLM_EMBEDDING_MODEL",
    "LLM_EMBEDDING_DIMENSIONS",
    "LLM_EMBEDDING_TASK_QUERY",
    "LLM_EMBEDDING_TASK_DOCUMENT",
    "LLM_EMBEDDING_BATCH_SIZE",
    "LLM_RERANK_API_KEY",
    "LLM_RERANK_BASE_URL",
    "LLM_RERANK_MODEL",
    "RAG_TIMEOUT_SECONDS",
    "RAG_MAX_RETRIES",
]


def _clear(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_EMBEDDING_API_KEY", "key")
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "model")

    config = load_retrieval_config()

    assert config.embedding_api_key == "key"
    assert config.embedding_model == "model"
    assert config.embedding_base_url == "https://api.jina.ai/v1"
    assert config.embedding_dimensions == 1024
    assert config.embedding_task_query == "retrieval.query"
    assert config.embedding_task_document == "retrieval.passage"
    assert config.embedding_batch_size == 32
    assert config.rerank_api_key == "key"
    assert config.rerank_base_url == "https://api.jina.ai/v1"
    assert config.rerank_model == "jina-reranker-v3.5"
    assert config.timeout == 30.0
    assert config.max_retries == 2


def test_custom_values(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_EMBEDDING_API_KEY", "key")
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "model")
    monkeypatch.setenv("LLM_EMBEDDING_BASE_URL", "http://embed")
    monkeypatch.setenv("LLM_EMBEDDING_DIMENSIONS", "512")
    monkeypatch.setenv("LLM_EMBEDDING_TASK_QUERY", "q")
    monkeypatch.setenv("LLM_EMBEDDING_TASK_DOCUMENT", "d")
    monkeypatch.setenv("LLM_EMBEDDING_BATCH_SIZE", "8")
    monkeypatch.setenv("LLM_RERANK_API_KEY", "rerank-key")
    monkeypatch.setenv("LLM_RERANK_BASE_URL", "http://rerank")
    monkeypatch.setenv("LLM_RERANK_MODEL", "rerank-model")
    monkeypatch.setenv("RAG_TIMEOUT_SECONDS", "10.5")
    monkeypatch.setenv("RAG_MAX_RETRIES", "4")

    config = load_retrieval_config()

    assert config.embedding_base_url == "http://embed"
    assert config.embedding_dimensions == 512
    assert config.embedding_task_query == "q"
    assert config.embedding_task_document == "d"
    assert config.embedding_batch_size == 8
    assert config.rerank_api_key == "rerank-key"
    assert config.rerank_base_url == "http://rerank"
    assert config.rerank_model == "rerank-model"
    assert config.timeout == 10.5
    assert config.max_retries == 4


def test_missing_required(monkeypatch):
    _clear(monkeypatch)

    with pytest.raises(RagConfigurationError) as exc_info:
        load_retrieval_config()

    assert "LLM_EMBEDDING_API_KEY" in str(exc_info.value)
    assert "LLM_EMBEDDING_MODEL" in str(exc_info.value)


def test_invalid_numbers(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("LLM_EMBEDDING_API_KEY", "key")
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "model")

    monkeypatch.setenv("LLM_EMBEDDING_DIMENSIONS", "many")
    with pytest.raises(RagConfigurationError):
        load_retrieval_config()

    monkeypatch.delenv("LLM_EMBEDDING_DIMENSIONS")
    monkeypatch.setenv("RAG_TIMEOUT_SECONDS", "slow")
    with pytest.raises(RagConfigurationError):
        load_retrieval_config()
