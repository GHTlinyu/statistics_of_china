"""向量接口客户端：OpenAI 兼容的 `/embeddings`。

数据库里的向量是 document 任务生成的，所以查询必须用 query 任务，
两边的 task 参数通过配置区分（Jina 用 retrieval.query / retrieval.passage）。
"""

from collections.abc import Iterator

from backend.app.retrieval.config import RetrievalConfig, load_retrieval_config
from backend.app.retrieval.exceptions import EmbeddingError
from backend.app.retrieval.http import post_json


def _batches(items: list[str], size: int) -> Iterator[list[str]]:
    step = max(1, size)
    for start in range(0, len(items), step):
        yield items[start : start + step]


class EmbeddingClient:
    """把文本转成向量，维度必须与库里的 `VECTOR(1024)` 一致。"""

    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self._config = config or load_retrieval_config()

    @property
    def config(self) -> RetrievalConfig:
        return self._config

    @property
    def dimensions(self) -> int:
        return self._config.embedding_dimensions

    def embed_query(self, text: str) -> list[float]:
        """把用户问题转成向量（query 任务）。"""
        return self._embed([text], self._config.embedding_task_query)[0]

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, self._config.embedding_task_query)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """把文档块转成向量（document 任务，入库时用）。"""
        return self._embed(texts, self._config.embedding_task_document)

    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for batch in _batches(texts, self._config.embedding_batch_size):
            data = post_json(
                self._url,
                {
                    "model": self._config.embedding_model,
                    "input": batch,
                    "task": task,
                },
                api_key=self._config.embedding_api_key,
                timeout=self._config.timeout,
                max_retries=self._config.max_retries,
                error_type=EmbeddingError,
            )

            items = list(data.get("data") or [])
            if len(items) != len(batch):
                raise EmbeddingError(
                    f"embedding 返回数量不符：请求 {len(batch)} 条，返回 {len(items)} 条"
                )

            items.sort(key=lambda item: item.get("index", 0))
            for item in items:
                vector = [float(value) for value in item.get("embedding") or []]
                if len(vector) != self.dimensions:
                    raise EmbeddingError(
                        f"embedding 维度不符：期望 {self.dimensions}，实际 {len(vector)}"
                    )
                vectors.append(vector)

        return vectors

    @property
    def _url(self) -> str:
        return f"{self._config.embedding_base_url.rstrip('/')}/embeddings"
