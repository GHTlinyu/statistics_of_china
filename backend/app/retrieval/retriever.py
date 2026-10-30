"""文档块检索：summary 向量召回 + 重排 + 回表取正文。"""

import logging
from dataclasses import dataclass, replace

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from backend.app.model.chunk_retrieval import ChunkRetrieval
from backend.app.retrieval.config import RetrievalConfig, load_retrieval_config
from backend.app.retrieval.embedding import EmbeddingClient
from backend.app.retrieval.exceptions import RagError
from backend.app.retrieval.ranker import Reranker

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 20
DEFAULT_TOP_N = 5

_CONTENT_SQL = text(
    "SELECT chunk_id, content FROM document_chunks WHERE chunk_id IN :chunk_ids"
).bindparams(bindparam("chunk_ids", expanding=True))


@dataclass(frozen=True)
class RetrievedChunk:
    """一条检索结果。"""

    chunk_id: str
    title: str | None
    summary: str | None
    content: str
    score: float


class ChunkRetriever:
    """检索入口：query → 向量 → 候选 → 重排 → 正文。"""

    def __init__(
        self,
        db: Session,
        embedding: EmbeddingClient | None = None,
        ranker: Reranker | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self._db = db
        config = config or load_retrieval_config()
        self._embedding = embedding or EmbeddingClient(config)
        self._ranker = ranker or Reranker(config)

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        top_n: int = DEFAULT_TOP_N,
    ) -> list[RetrievedChunk]:
        vector = self._embedding.embed_query(query)
        candidates = self._vector_search(vector, top_k)
        if not candidates:
            return []

        ranked = self._rerank(query, candidates, top_n)
        return self._attach_content(ranked)

    def _vector_search(
        self,
        vector: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """只按 summary 向量的余弦相似度取 top_k。

        summary 为空的分块（正文里的「备注」块）没有向量可比，直接排除。
        """
        score = 1 - ChunkRetrieval.summary_embedding.cosine_distance(vector)

        stmt = (
            select(
                ChunkRetrieval.chunk_id,
                ChunkRetrieval.title,
                ChunkRetrieval.summary,
                score.label("score"),
            )
            .where(ChunkRetrieval.summary_embedding.is_not(None))
            .order_by(score.desc())
            .limit(top_k)
        )

        rows = self._db.execute(stmt).all()
        return [
            RetrievedChunk(
                chunk_id=row.chunk_id,
                title=row.title,
                summary=row.summary,
                content="",
                score=float(row.score),
            )
            for row in rows
        ]

    def _rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_n: int,
    ) -> list[RetrievedChunk]:
        documents = [self._document_text(chunk) for chunk in candidates]

        try:
            ranking = self._ranker.rerank(query, documents, top_n=top_n)
        except RagError as exc:
            # 重排失败不影响主流程，退回向量排序
            logger.warning("rerank 失败，回退向量排序：%s", exc)
            return candidates[:top_n]

        return [replace(candidates[index], score=score) for index, score in ranking]

    def _attach_content(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return []

        rows = self._db.execute(
            _CONTENT_SQL,
            {"chunk_ids": [chunk.chunk_id for chunk in chunks]},
        ).all()
        contents = {row.chunk_id: row.content for row in rows}

        result: list[RetrievedChunk] = []
        for chunk in chunks:
            content = contents.get(chunk.chunk_id)
            if not content:
                continue
            result.append(replace(chunk, content=content))
        return result

    @staticmethod
    def _document_text(chunk: RetrievedChunk) -> str:
        """重排输入：只用 summary，与向量召回口径保持一致。"""
        return chunk.summary or ""
