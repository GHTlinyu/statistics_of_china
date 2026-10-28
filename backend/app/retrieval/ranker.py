"""重排接口客户端：Jina Rerank 兼容的 `/rerank`。"""

from backend.app.retrieval.config import RetrievalConfig, load_retrieval_config
from backend.app.retrieval.exceptions import RerankError
from backend.app.retrieval.http import post_json


class Reranker:
    """对召回的候选文本重新打分，返回 (候选下标, 分数)。"""

    def __init__(self, config: RetrievalConfig | None = None) -> None:
        self._config = config or load_retrieval_config()

    @property
    def config(self) -> RetrievalConfig:
        return self._config

    @property
    def _url(self) -> str:
        return f"{self._config.rerank_base_url.rstrip('/')}/rerank"

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[tuple[int, float]]:
        """返回按相关度降序排列的 (下标, 分数)。"""
        if not documents:
            return []

        limit = len(documents) if top_n is None else min(top_n, len(documents))
        data = post_json(
            self._url,
            {
                "model": self._config.rerank_model,
                "query": query,
                "documents": documents,
                "top_n": limit,
            },
            api_key=self._config.rerank_api_key,
            timeout=self._config.timeout,
            max_retries=self._config.max_retries,
            error_type=RerankError,
        )

        results = data.get("results")
        if results is None:
            results = data.get("data") or []

        ranked: list[tuple[int, float]] = []
        for item in results:
            index = item.get("index")
            score = item.get("relevance_score", item.get("score"))
            if index is None or score is None:
                continue
            index = int(index)
            if not 0 <= index < len(documents):
                continue
            ranked.append((index, float(score)))

        if not ranked:
            raise RerankError("rerank 返回结果为空或格式不正确")

        return ranked[:limit]
