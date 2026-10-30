"""年鉴知识库检索工具。"""

import json

from langchain_core.tools import tool

from backend.app.database.database import SessionLocal
from backend.app.retrieval.retriever import ChunkRetriever

# 召回数 = 最终条数 × 该系数，且不低于 20
RECALL_FACTOR = 4
MIN_RECALL = 20

MAX_TOP_K = 10


@tool
def search_yearbook(query: str, top_k: int = 5) -> str:
    """检索《中国统计年鉴 2025》知识库，返回与问题最相关的统计表格片段。

    Args:
        query: 检索语句，尽量带上统计主题、指标名或年份。
        top_k: 返回片段数量，默认 5，最多 10。
    """
    top_n = max(1, min(int(top_k), MAX_TOP_K))
    recall = max(top_n * RECALL_FACTOR, MIN_RECALL)

    db = SessionLocal()
    try:
        chunks = ChunkRetriever(db).search(query=query, top_k=recall, top_n=top_n)
    finally:
        db.close()

    payload = [
        {
            "chunk_id": chunk.chunk_id,
            "title": chunk.title,
            "content": chunk.content,
            "score": round(chunk.score, 6),
        }
        for chunk in chunks
    ]
    return json.dumps(payload, ensure_ascii=False)
