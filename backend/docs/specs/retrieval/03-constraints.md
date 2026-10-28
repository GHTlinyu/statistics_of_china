# 03 开发约束：文档块向量检索与重排

- 功能 slug：`retrieval`
- 日期：2026-10-28

## 代码位置

- 实现只放 `backend/app/`（`app/model`、`app/retrieval`）与 `backend/agent/tools/`；`backend/rag/` 只保留数据与文档，不新增 Python 代码。
- `ChunkRetriever` 只依赖 `Session`、`EmbeddingClient`、`Reranker`，不感知 FastAPI；HTTP 层、鉴权、DTO 不进入检索模块。

## 配置约束

- 用 `load_dotenv` + `os.getenv` 读取仓库根目录 `.env`，不引入 pydantic-settings，不修改 `backend/app/database/config.py`。
- `LLM_EMBEDDING_API_KEY` 与 `LLM_EMBEDDING_MODEL` 必填；embedding 模型须与入库向量一致，换模型必须重新入库；其余配置有默认值。
- 密钥只经环境变量传递，不写入代码、日志与文档。

## 依赖约束

- `httpx` 已在 `backend/pyproject.toml` 显式声明（`uv.lock` 同步），不再引入 `requests` 等重复 HTTP 依赖。
- 不引入本地推理依赖（`sentence-transformers` 等），向量与重排一律走外部 API。
- 使用 `pgvector.sqlalchemy.Vector`，维度固定 `1024`。

## 数据约束

- `chunk_retrieval` 结构以用户提供的 DDL 为准，不改表、不加索引。
- `chunk_id` 与 `document_chunks.chunk_id` 一一对应；正文只从 `document_chunks.content` 取，不冗余存储。
- 检索只使用 `summary_embedding`；`summary_embedding IS NULL` 的分块不参与召回。
- 向量维度运行时校验，与表定义不一致时立即报错。

## 行为约束

- 检索链路同步实现；异步场景由调用方放入线程池或包装，不在模块内起线程。
- embedding 请求固定 `normalized=true`、`input` 用 `{text}` 对象数组；rerank 请求带 `return_documents=false`。
- 重排失败必须降级为向量排序并记录 warning；embedding 失败才允许向上抛错。
- tool 返回完整正文，不做截断；上下文长度由调用方按模型窗口控制。
- 召回数与最终条数使用命名常量，便于后续评测调整。
- 重试仅针对 429 / 5xx / 网络错误，4xx 直接失败。

## 兼容性

- 本轮不改 `workflow/` 的业务逻辑；接线时把 `rag.embedding` / `rag.retriever` 改为 `backend.app.retrieval.*`。
- 不改现有 API、数据库表结构与前端。
