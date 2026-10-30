# 后端单元测试

## 运行

在仓库根目录执行：

```bash
uv run --package statistics-of-china-backend pytest backend/tests
```

带覆盖率：

```bash
uv run --package statistics-of-china-backend pytest backend/tests \
  --cov=backend/app --cov=backend/agent --cov-report=term-missing
```

也可以在 `backend/` 目录执行 `uv run pytest`。

## 当前状态

- 205 个测试全部通过。
- `backend/app` + `backend/agent` 行覆盖率 100%。
- 测试不连接真实 PostgreSQL、真实 LLM、embedding / rerank 服务，也不会写入 `.env` 中的数据库。

## 测试策略

- **SQLite 临时库**：每个测试一个独立的 SQLite 文件库（`tmp_path`），见 `conftest.py` 的 `engine` / `session_factory` / `db`。
- **自定义 DDL**：SQLite 下 `BIGINT PRIMARY KEY` 不会自增，`TEST_DDL` 把测试表的主键改成 `INTEGER PRIMARY KEY AUTOINCREMENT`；新增表时需要同步补 DDL。
- **FastAPI 测试**：`client` 使用 `TestClient`，`app` 夹具覆盖 `get_db`，并把 `chatService` / `memoryService` / 检索工具里的 `SessionLocal` 指向测试库。
- **外部依赖全部 mock**：LLM 用 fake model，embedding / rerank HTTP 用 fake `post_json`，检索库用 fake session / execute 结果。
- **鉴权**：`user` 夹具创建测试用户，`auth_headers` 用真实 JWT 签发；登录 / 注册 / 验证码走真实接口。
- **聊天 SSE**：`TestClient` 会缓冲完整 SSE 响应，测试断言完整事件序列；真流式行为仍以 uvicorn + curl 联调为准。

## 覆盖范围

| 测试文件 | 覆盖内容 |
| --- | --- |
| `test_security.py` | argon2 密码哈希、JWT 签发/解析、过期/伪造/缺声明 |
| `test_auth_service.py` | 注册、重复用户名、凭据校验 |
| `test_auth_api.py` | 验证码、登录、注册、token 流转、401/409/422 |
| `test_captcha_service.py` | 图片、摘要、一次性、过期、清理、长度截断 |
| `test_schemas.py` | ApiResponse、分页、登录/注册/聊天/消息 DTO 校验 |
| `test_conversation_service.py` / `_mapper.py` / `_api.py` | 会话创建、归属、分页、标题、活跃时间、软删除 |
| `test_message_service.py` / `_mapper.py` / `_api.py` | 消息增删、归属、分页、最近消息、最近用户消息 |
| `test_workflow_nodes.py` | 检索节点、生成节点、prompt 片段、记忆上下文 |
| `test_chat_service.py` | 历史、标题、记忆注入、SSE 事件、部分保存 |
| `test_chat_api.py` | SSE 事件序列、404、422、记忆注入、后台提取 |
| `test_memory_finder.py` / `_extractor.py` / `_updater.py` | prompt、JSON 解析、非法输出、ID 过滤 |
| `test_memory_mapper.py` / `test_memory_service.py` | 排序、归属、读路径、写路径、容量 MERGE/REPLACE、降级 |
| `test_llm_client.py` | 文本提取、JSON、流式、中断、配置、单例 |
| `test_retrieval_config.py` / `test_config.py` | 检索配置与 Settings 默认值/必填校验 |
| `test_retrieval_http.py` | 重试、退避、非 JSON、网络错误 |
| `test_embedding.py` / `test_ranker.py` / `test_retriever.py` / `test_retrieval_tool.py` | 分批、排序、维度、重排、回表、召回放大 |
| `test_user_api.py` / `test_database.py` / `test_smoke.py` | 用户接口、鉴权依赖、`get_db` 生命周期、公开路径 |
| `test_edge_cases.py` | 后台任务取消/异常、保存失败、LLM 可选参数、空输入边界 |

## 已知边界

1. SQLite 不执行 PostgreSQL 的 `SELECT ... FOR UPDATE`、pgvector 相似度查询和 `Identity` 生成逻辑；这些由真实 PostgreSQL 联调覆盖。
2. 没有真实 LLM / embedding / rerank 调用，模型返回的内容与网络异常均通过 fake 模拟。
3. 测试使用占位 `JWT_SECRET` 和 SQLite，不读取真实业务数据；如需验证真实链路，仍按各功能 `04-delivery.md` 的手工步骤执行。
