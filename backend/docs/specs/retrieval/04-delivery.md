# 04 交付：文档块向量检索与重排

- 功能 slug：`retrieval`
- 日期：2026-10-28
- 状态：已实现；向量、重排、数据库、LLM 问答链路均已真实联调

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
| 缺 key | 报错 `缺少向量检索配置：LLM_EMBEDDING_API_KEY` |
| Jina 请求体 | embedding：`input` 为 `[{text}]`、`normalized=true`；rerank：`return_documents=false` |
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

## 真实接口联调（2026-10-28）

| 项 | 结果 |
| --- | --- |
| embedding（query） | 1024 维，模长 1.0（`normalized` 生效），单次约 0.5s |
| embedding（document） | 3 条批量约 0.67s，1024 维 |
| 模型一致性 | 库里 summary 用 document 任务重算，与存储向量余弦 0.999928（模型、task 完全一致） |
| rerank | 约 0.64s，`jina-reranker-v3.5`；分数为原始 logit（可能为负），仅用于排序 |
| tool 端到端 | 「2024 年全国人口」1.59s、「分地区固定资产投资」1.31s，top5 命中对应统计表 |
| 工作流接入 | `graph.invoke` 真实检索 1.53s，5 条文档进入 prompt |
| 问答链路 | 「近几年的人口结构变化是如何的」：检索 1.54s + 生成 10.19s，回答 1203 字，18 个关键数字均可在召回原文中找到 |

## 待办与已知偏差

1. 回答生成约 10s（非流式），后续接前端时建议改流式输出。
2. `chunk_retrieval` 有 282 条「备注」块没有 `summary_embedding`（正文约 30 字），按当前设计不参与召回；若需覆盖表注，需补 summary 向量。
3. 检索已通过 `search_yearbook` tool 接入工作流（`workflow/nodes.py`）。
4. 默认 rerank 模型 `jina-reranker-v3.5` 需与账号可用模型一致；embedding 模型必须与入库一致（按入库说明记为 `jina-embeddings-v5-text-small`，若实际为 omni-small 需改配置）。
5. 召回 `20`、最终 `5` 为默认值，待真实向量联调后复核。
6. 两表 `chunk_id` 与向量列均无索引（本期约定不建）；1229 行下全表扫描耗时可接受。

## 配置示例

```ini
LLM_EMBEDDING_API_KEY=...
LLM_EMBEDDING_MODEL=jina-embeddings-v5-text-small   # 必须与入库向量一致
# 以下有默认值，可按需覆盖
# LLM_EMBEDDING_BASE_URL=https://api.jina.ai/v1
# LLM_RERANK_MODEL=jina-reranker-v3.5
```

## 联调步骤（数据库与凭据就绪后）

1. 用 `ChunkRetriever(db).search("2024 年人口")` 直接调用，确认返回 5 条带正文的结果。
2. 核对 `chunk_retrieval` 行数与 `summary_embedding` 非空比例（决定可召回范围）。
3. 抽查 top5 是否命中预期表格；必要时调整 `top_k` / `top_n` 与重排模型。
