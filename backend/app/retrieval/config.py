"""检索与重排配置：从仓库根目录的 `.env` 读取。

只读 embedding / rerank 相关的 `LLM_*` 与 `RAG_*`，不碰数据库与 LLM 聊天配置。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

from backend.app.retrieval.exceptions import RagConfigurationError

# 本文件在 backend/app/retrieval/config.py，向上三层是仓库根
REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"

load_dotenv(ENV_FILE)

DEFAULT_BASE_URL = "https://api.jina.ai/v1"
DEFAULT_RERANK_MODEL = "jina-reranker-v3.5"

DEFAULT_DIMENSIONS = 1024
DEFAULT_BATCH_SIZE = 32
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_TASK_QUERY = "retrieval.query"
DEFAULT_TASK_DOCUMENT = "retrieval.passage"


@dataclass(frozen=True)
class RetrievalConfig:
    """embedding / rerank 的连接与行为参数。"""

    embedding_api_key: str
    embedding_base_url: str
    embedding_model: str
    embedding_dimensions: int
    embedding_task_query: str
    embedding_task_document: str
    embedding_batch_size: int
    rerank_api_key: str
    rerank_base_url: str
    rerank_model: str
    timeout: float
    max_retries: int


def _read_text(key: str) -> str | None:
    value = os.getenv(key)
    value = value.strip() if value else ""
    return value or None


def _read_int(key: str, default: int) -> int:
    value = _read_text(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RagConfigurationError(f"{key} 必须是整数，当前值：{value}") from exc


def _read_float(key: str, default: float) -> float:
    value = _read_text(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise RagConfigurationError(f"{key} 必须是数字，当前值：{value}") from exc


def load_retrieval_config() -> RetrievalConfig:
    """读取并校验检索配置。

    embedding 模型必须显式配置，且要与入库向量的模型一致，否则相似度没有意义。
    """
    api_key = _read_text("LLM_EMBEDDING_API_KEY")
    model = _read_text("LLM_EMBEDDING_MODEL")

    missing = [
        name
        for name, value in (
            ("LLM_EMBEDDING_API_KEY", api_key),
            ("LLM_EMBEDDING_MODEL", model),
        )
        if value is None
    ]
    if missing:
        raise RagConfigurationError(
            "缺少向量检索配置：" + "、".join(missing) + "，请在仓库根目录的 .env 中填写"
        )

    base_url = _read_text("LLM_EMBEDDING_BASE_URL") or DEFAULT_BASE_URL

    return RetrievalConfig(
        embedding_api_key=cast(str, api_key),
        embedding_base_url=base_url,
        embedding_model=cast(str, model),
        embedding_dimensions=_read_int("LLM_EMBEDDING_DIMENSIONS", DEFAULT_DIMENSIONS),
        embedding_task_query=_read_text("LLM_EMBEDDING_TASK_QUERY")
        or DEFAULT_TASK_QUERY,
        embedding_task_document=_read_text("LLM_EMBEDDING_TASK_DOCUMENT")
        or DEFAULT_TASK_DOCUMENT,
        embedding_batch_size=_read_int("LLM_EMBEDDING_BATCH_SIZE", DEFAULT_BATCH_SIZE),
        rerank_api_key=_read_text("LLM_RERANK_API_KEY") or cast(str, api_key),
        rerank_base_url=_read_text("LLM_RERANK_BASE_URL") or base_url,
        rerank_model=_read_text("LLM_RERANK_MODEL") or DEFAULT_RERANK_MODEL,
        timeout=_read_float("RAG_TIMEOUT_SECONDS", DEFAULT_TIMEOUT),
        max_retries=_read_int("RAG_MAX_RETRIES", DEFAULT_MAX_RETRIES),
    )
