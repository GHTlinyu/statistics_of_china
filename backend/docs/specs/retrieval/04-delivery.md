# 04 交付：文档块向量检索与重排

- 功能 slug：`retrieval`
- 日期：2026-10-28
- 状态：已实现；数据库链路已实测（含 summary-only 复核），真实模型调用待凭据

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/model/chunk_retrieval.py` | 新增 `ChunkRetrieval` ORM，两列 `Vector(1024)` |
| `backend/app/retrieval/__init__.py` | 模块出口 |
| `backend/app/retrieval/config.py` | `RetrievalConfig`、`load_retrieval_config()` |
| `backend/app/retrieval/exceptions.py` | `RagError` / `RagConfigurationError` / `EmbeddingError` / `RerankError` |
| `backend/app/retrieval/http.py` | JSON POST、超时、429/5xx/网络错误重试 |
| `backend/app/retrieval/embedding.py` | `EmbeddingClient`，query / document 任务、分批、维度校验 |
| `backend/app/retrieval/ranker.py` | `Reranker`，解析 `/rerank` 结果 |
| `backend/app/retrieval/retriever.py` | `ChunkRetriever`：双列召回 → 重排 → 回表 |
| `backend/agent/tools/retrieval.py` | `@tool search_yearbook` |
| `backend/agent/tools/__init__.py` | `TOOLS` 列表 |
| `backend/app/database/init_db.py` | 注册 `ChunkRetrieval` |
| `backend/pyproject.toml`、`uv.lock` | 新增 `httpx>=0.28.1` 直接依赖 |

## 验证结果（离线：假 embedding / 假 rerank / 假 DB）

| 场景 | 结果 |
| --- | --- |
| ORM 编译 DDL | `VECTOR(1024)` ×2、`GENERATED ALWAYS AS IDENTITY`、时间戳默认值正确 |
| 缺配置 | 一次性列出 `LLM_EMBEDDING_*` 三项 |
| query / document 任务 | 分别发送 `retrieval.query`、`retrieval.passage` |
| 分批 | batch=2 时 5 条按 2 / 2 / 1 拆分 |
| 维度校验 | 返回 768 维时报错 |
| rerank 解析 | `index` + `relevance_score` 正确排序 |
| 检索主流程 | 重排顺序、分数、正文回填正确；无正文片段被丢弃 |
| 重排失败 | 回退向量排序，返回 top_n |
| tool | 返回 JSON；正文完整返回，不截断 |
| 检索列 | SQL 只引用 `summary_embedding`，`title_embedding` 不参与；NULL summary 被过滤 |

## 数据库实测（2026-10-28）

| 项 | 结果 |
| --- | --- |
| 连接 | PostgreSQL 16.15，已装 pgvector |
| 表规模 | `chunk_retrieval` 1229 行，`document_chunks` 1229 行 |
| 数据完整性 | 两表 `chunk_id` 均无重复；联表 1229/1229 命中，无缺失正文 |
| 向量维度 | `vector_dims` 全部为 1024 |
| 真实 SQL | summary 余弦召回 + 回表在真实库执行成功（全表扫描，数十毫秒） |
| 召回范围 | `summary_embedding` 非空 947/1229；实测召回恰为 947 条，全部带 summary |
| 正文完整性 | 最长分块 16717 字，回表返回完整内容，未截断 |

## 待办与已知偏差

1. `.env` 的 embedding 三项为空，真实模型调用未验证。
2. `chunk_retrieval` 有 282 条「备注」块没有 `summary_embedding`（正文约 30 字），按当前设计不参与召回；若需覆盖表注，需补 summary 向量。
3. `workflow/nodes.py` 仍引用 `rag.embedding` / `rag.retriever`，未接线（本轮约定不改业务逻辑）。
4. rerank 默认模型名 `jina-reranker-v2-base-multilingual` 需按账号实际可用模型确认。
5. 召回 `20`、最终 `5` 为默认值，待真实向量联调后复核。
6. 两表 `chunk_id` 与向量列均无索引（本期约定不建）；1229 行下全表扫描耗时可接受。

## 配置示例

```ini
LLM_EMBEDDING_API_KEY=...
LLM_EMBEDDING_BASE_URL=https://api.jina.ai/v1
LLM_EMBEDDING_MODEL=jina-embeddings-v5-text-small
LLM_RERANK_MODEL=...
```

## 联调步骤（数据库与凭据就绪后）

1. 用 `ChunkRetriever(db).search("2024 年人口")` 直接调用，确认返回 5 条带正文的结果。
2. 核对 `chunk_retrieval` 行数与 `summary_embedding` 非空比例（决定可召回范围）。
3. 抽查 top5 是否命中预期表格；必要时调整 `top_k` / `top_n` 与重排模型。
