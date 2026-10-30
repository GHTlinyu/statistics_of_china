"""检索编排：向量召回、重排、回表与重排失败回退。"""

from types import SimpleNamespace

from backend.app.retrieval.config import RetrievalConfig
from backend.app.retrieval.exceptions import RagError
from backend.app.retrieval.retriever import ChunkRetriever, RetrievedChunk


def _config():
    return RetrievalConfig(
        embedding_api_key="key",
        embedding_base_url="http://embedding",
        embedding_model="embed-model",
        embedding_dimensions=3,
        embedding_task_query="retrieval.query",
        embedding_task_document="retrieval.passage",
        embedding_batch_size=2,
        rerank_api_key="key",
        rerank_base_url="http://rerank",
        rerank_model="rerank-model",
        timeout=5.0,
        max_retries=1,
    )


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, vector_rows, content_rows):
        self.vector_rows = vector_rows
        self.content_rows = content_rows
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append(params)
        if len(self.calls) == 1:
            return FakeResult(self.vector_rows)
        return FakeResult(self.content_rows)


class FakeEmbedding:
    def __init__(self):
        self.queries = []

    def embed_query(self, text):
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


class FakeRanker:
    def __init__(self, ranking=None, error=None):
        self.ranking = ranking or []
        self.error = error
        self.calls = []

    def rerank(self, query, documents, top_n=None):
        self.calls.append((query, documents, top_n))
        if self.error is not None:
            raise self.error
        return self.ranking


def _vector_rows():
    return [
        SimpleNamespace(
            chunk_id="c1",
            title="t1",
            summary="s1",
            score=0.9,
        ),
        SimpleNamespace(
            chunk_id="c2",
            title="t2",
            summary="s2",
            score=0.8,
        ),
    ]


def _content_rows():
    return [
        SimpleNamespace(chunk_id="c1", content="content1"),
        SimpleNamespace(chunk_id="c2", content="content2"),
    ]


def test_search_runs_full_pipeline():
    embedding = FakeEmbedding()
    ranker = FakeRanker(ranking=[(1, 0.95), (0, 0.85)])
    db = FakeDB(_vector_rows(), _content_rows())
    retriever = ChunkRetriever(
        db=db,
        embedding=embedding,
        ranker=ranker,
        config=_config(),
    )

    result = retriever.search("query", top_k=2, top_n=2)

    assert [chunk.chunk_id for chunk in result] == ["c2", "c1"]
    assert [chunk.score for chunk in result] == [0.95, 0.85]
    assert [chunk.content for chunk in result] == [
        "content2",
        "content1",
    ]
    assert embedding.queries == ["query"]
    assert ranker.calls == [("query", ["s1", "s2"], 2)]
    assert len(db.calls) == 2


def test_search_empty_candidates_returns_empty():
    ranker = FakeRanker(error=RagError("should not be called"))
    db = FakeDB([], [])
    retriever = ChunkRetriever(
        db=db,
        embedding=FakeEmbedding(),
        ranker=ranker,
        config=_config(),
    )

    assert retriever.search("query") == []
    assert ranker.calls == []
    assert len(db.calls) == 1


def test_rerank_failure_falls_back_to_vector_order():
    ranker = FakeRanker(error=RagError("rerank down"))
    retriever = ChunkRetriever(
        db=FakeDB(_vector_rows(), _content_rows()),
        embedding=FakeEmbedding(),
        ranker=ranker,
        config=_config(),
    )

    result = retriever.search("query", top_n=2)

    assert [chunk.chunk_id for chunk in result] == ["c1", "c2"]
    assert [chunk.score for chunk in result] == [0.9, 0.8]
    assert [chunk.content for chunk in result] == [
        "content1",
        "content2",
    ]


def test_missing_content_is_filtered():
    retriever = ChunkRetriever(
        db=FakeDB(
            _vector_rows(),
            [SimpleNamespace(chunk_id="c1", content="content1")],
        ),
        embedding=FakeEmbedding(),
        ranker=FakeRanker(ranking=[(0, 0.95), (1, 0.85)]),
        config=_config(),
    )

    result = retriever.search("query", top_n=2)

    assert [chunk.chunk_id for chunk in result] == ["c1"]


def test_document_text_uses_summary():
    chunk = RetrievedChunk(
        chunk_id="c1",
        title="t1",
        summary="summary",
        content="content",
        score=0.5,
    )

    assert ChunkRetriever._document_text(chunk) == "summary"
    assert (
        ChunkRetriever._document_text(
            RetrievedChunk(
                chunk_id="c2",
                title=None,
                summary=None,
                content="content",
                score=0.5,
            )
        )
        == ""
    )
