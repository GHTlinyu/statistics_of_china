# 02 设计：文档块向量检索与重排

- 功能 slug：`retrieval`
- 日期：2026-10-28

## 数据模型

### chunk_retrieval

| 列 | 类型 | 约束 |
| --- | --- | --- |
| id | BIGINT GENERATED ALWAYS AS IDENTITY | PRIMARY KEY |
| chunk_id | VARCHAR(100) | NOT NULL，对应 `document_chunks.chunk_id` |
| title | VARCHAR(500) | NULL |
| title_embedding | VECTOR(1024) | NULL |
| summary | TEXT | NULL |
| summary_embedding | VECTOR(1024) | NULL |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

正文不在本表，检索后按 `chunk_id` 回 `document_chunks.content` 取。

数据现状（2026-10-28）：1229 行；`title_embedding` 全量有值，`summary_embedding` 947 行有值——其余 282 条是「备注」块，无 summary 向量，按设计不参与召回。

## 模块结构

按需求，实现放在 `backend/app/` 下，`backend/rag/` 只保留数据与文档：

```
backend/app/
├── model/chunk_retrieval.py     # ChunkRetrieval ORM（pgvector Vector(1024)）
└── retrieval/
    ├── config.py                # load_dotenv + os.getenv，读仓库根 .env
    ├── exceptions.py            # RagError / RagConfigurationError / EmbeddingError / RerankError
    ├── http.py                  # JSON POST、超时、有限重试
    ├── embedding.py             # EmbeddingClient（query / document 两种任务）
    ├── ranker.py                # Reranker（Jina /rerank）
    ├── retriever.py             # ChunkRetriever：召回 → 重排 → 回表
    └── __init__.py

backend/agent/tools/
├── retrieval.py                 # @tool search_yearbook
└── __init__.py                  # TOOLS 列表
```

## 检索流程

1. `EmbeddingClient.embed_query(question)` → 1024 维向量（task=`retrieval.query`）。
2. `ChunkRetriever._vector_search` 按 summary 余弦相似度取 top_k，summary 为空的分块被过滤。
3. `Reranker.rerank(question, [summary…])` → 按分数降序的 `(下标, 分数)`。
4. `_attach_content` 按 `chunk_id` 回 `document_chunks` 取正文，取不到的片段丢弃。
5. tool 序列化为 JSON 字符串返回。

## 打分公式

```sql
score = 1 - (summary_embedding <=> :vector)
```

- `<=>` 为 pgvector 余弦距离，分数越高越相关。
- 只使用 `summary_embedding`；`title_embedding` 不参与检索打分，`title` 只用于展示。
- 重排输入同样只用 `summary`，与召回口径一致。
- `summary_embedding IS NULL` 的分块（「备注」块）没有可比较的向量，直接过滤，不参与召回。
- `DEFAULT_TOP_K = 20`（召回）、`DEFAULT_TOP_N = 5`（最终）。

## 外部接口契约

### embedding

```
POST {LLM_EMBEDDING_BASE_URL}/embeddings
Authorization: Bearer <key>
{
  "model": "jina-embeddings-v5-text-small",
  "task": "retrieval.query" | "retrieval.passage",
  "normalized": true,
  "input": [{"text": "..."}]
}
→ {"data": [{"index": 0, "embedding": [0.1, ...]}, ...]}
```

- `input` 是对象数组（支持 `{text}` / `{image}`），当前只用文本。
- 固定 `normalized=true`，与入库向量口径一致。
- 模型必须与入库向量一致（当前库按 `jina-embeddings-v5-text-small` 生成）；换模型必须重新入库。
- 按 `LLM_EMBEDDING_BATCH_SIZE`（默认 32）分批请求。
- 返回条数或单条维度不符，抛 `EmbeddingError`。

### rerank

```
POST {LLM_RERANK_BASE_URL}/rerank
{
  "model": "jina-reranker-v3.5",
  "query": "...",
  "documents": ["..."],
  "top_n": 5,
  "return_documents": false
}
→ {"results": [{"index": 2, "relevance_score": 0.93}, ...]}
```

- 兼容 `results` / `data` 两种字段名，`relevance_score` / `score` 两种分数字段。
- `relevance_score` 是原始分数（可能为负），只用于排序，不作为概率展示。
- 越界下标与缺字段的条目被忽略；无有效结果抛 `RerankError`。

## 配置项

| 变量 | 必填 | 默认 |
| --- | --- | --- |
| LLM_EMBEDDING_API_KEY | 是 | — |
| LLM_EMBEDDING_BASE_URL | 否 | https://api.jina.ai/v1 |
| LLM_EMBEDDING_MODEL | 是 | —（须与入库向量一致） |
| LLM_EMBEDDING_DIMENSIONS | 否 | 1024 |
| LLM_EMBEDDING_TASK_QUERY | 否 | retrieval.query |
| LLM_EMBEDDING_TASK_DOCUMENT | 否 | retrieval.passage |
| LLM_EMBEDDING_BATCH_SIZE | 否 | 32 |
| LLM_RERANK_API_KEY | 否 | 复用 embedding key |
| LLM_RERANK_BASE_URL | 否 | 复用 embedding base_url |
| LLM_RERANK_MODEL | 否 | jina-reranker-v3.5 |
| RAG_TIMEOUT_SECONDS | 否 | 30 |
| RAG_MAX_RETRIES | 否 | 2 |

配置在模块导入时通过 `load_dotenv(仓库根/.env)` 加载；`LLM_EMBEDDING_API_KEY` 与 `LLM_EMBEDDING_MODEL` 必填，其余有默认值或被复用。

## 接口定义

```python
class EmbeddingClient:
    def embed_query(self, text: str) -> list[float]: ...
    def embed_queries(self, texts: list[str]) -> list[list[float]]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

class Reranker:
    def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[tuple[int, float]]: ...

class ChunkRetriever:
    def __init__(self, db: Session, embedding=None, ranker=None, config=None): ...
    def search(
        self, query: str, top_k: int = 20, top_n: int = 5
    ) -> list[RetrievedChunk]: ...
```

`RetrievedChunk` 字段：`chunk_id`、`title`、`summary`、`content`、`score`。

## Tool 契约

| 项 | 值 |
| --- | --- |
| 名称 | `search_yearbook` |
| 参数 | `query: str`、`top_k: int = 5`（限制 1~10） |
| 召回 | `max(top_k * 4, 20)` |
| 返回 | JSON 数组字符串：`chunk_id`、`title`、`content`（完整正文，不截断）、`score` |

工具内部自建 `SessionLocal` 会话并关闭，不要求调用方传入数据库会话。

## 错误与降级

| 场景 | 处理 |
| --- | --- |
| 配置缺失 | `RagConfigurationError`，列出缺失项 |
| embedding 请求失败 / 维度不符 | `EmbeddingError`，向上抛出 |
| rerank 失败 | 记录 warning，退回向量排序取 top_n |
| 回表无正文 | 丢弃该片段 |
| 无召回结果 | 返回空列表 |

## 关键决策

1. 实现放 `app/` 下（`app/retrieval`），`backend/rag/` 只放数据与文档，避免与数据目录混淆。
2. 只使用 summary：summary 是整块语义的一句话总结，比标题更贴近用户问题；title 只用于展示。
3. 重排失败不阻塞主流程：检索是回答的前置步骤，降级比失败更可用。
4. HTTP 使用轻量封装（`httpx`）+ 显式有限重试，不引入额外 SDK。
5. 不做查询改写与缓存，保持链路可解释、便于后续评测。
