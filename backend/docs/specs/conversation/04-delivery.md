# 04 交付：会话记录

- 功能 slug：`conversation`
- 日期：2026-10-26
- 状态：已交付并验证（数据库恢复后完成全链路实测）

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/model/conversation.py` | 新增 `Conversation` 模型、`STATE_ACTIVE`/`STATE_DELETED` 常量 |
| `backend/app/model/message.py` | 新增 `Message` 模型（含 role CHECK 约束） |
| `backend/app/schema/pageDTO.py` | 新增通用分页结构 `PageResult[T]` |
| `backend/app/schema/conversationDTO.py` | 新增 `ConversationDTO`、`MessageDTO`、`CreateConversationRequest` |
| `backend/app/mapper/conversationMapper.py` | 新增：分页列表、按 id+user 查询、创建、软删除 |
| `backend/app/mapper/messageMapper.py` | 新增：按会话分页查询消息 |
| `backend/app/service/conversationService.py` | 新增：业务逻辑与归属/状态校验（越权统一 404） |
| `backend/app/controller/conversationController.py` | 新增 5 个接口 |
| `backend/app/main.py` | 注册 conversation 路由 |
| `backend/app/database/init_db.py` | 导入新模型，保证 `create_all` 建表 |

## 接口清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/conversation?page=1&page_size=20` | 当前用户会话分页（state=1，updated_at 倒序） |
| POST | `/conversation` | 创建会话（201） |
| GET | `/conversation/{conversation_id}` | 会话详情 |
| GET | `/conversation/{conversation_id}/messages?page=1&page_size=20` | 消息分页（created_at 正序） |
| DELETE | `/conversation/{conversation_id}` | 软删除（state=2） |

## 验证结果（实测）

| 场景 | 结果 |
| --- | --- |
| `init_db` 建表 | conversation/message 表、外键、CHECK、BIGSERIAL 均正确 ✅ |
| `POST /conversation`（含 title / 不含 title） | 201，state 默认 1，title 可为 null ✅ |
| `GET /conversation` 列表 | 分页正确，total 准确，updated_at 倒序 ✅ |
| `GET /conversation/{id}` 详情 | 200 ✅ |
| `GET /conversation/{id}/messages` | created_at 正序，分页 total 准确 ✅ |
| 跨用户访问（详情/消息/删除） | 均返回 404 `Conversation not found`，数据隔离 ✅ |
| `DELETE /conversation/{id}` | 200，state=2，updated_at 刷新，消息保留 ✅ |
| 删除后列表/详情/消息/重复删除 | 列表不可见，详情与消息 404，重复删除 404 ✅ |
| `page=0` / `page_size=101` | 422 参数校验 ✅ |
| 无 token 访问 | 401 ✅ |

测试数据（会话 1~3 及其消息）已清理，测试账号 `testuser`/`testuser2` 保留。

## 已知偏差（已确认保留）

`backend/app/main.py` 中的统一异常处理器（`@app.exception_handler(HTTPException)`）被注释，业务异常（如 401/404/409）返回 FastAPI 默认格式 `{"detail": ...}`。用户已确认保留现状：不影响业务，暂不恢复。前端 `src/app.tsx` 的错误处理已兼容该格式（优先读取 `data.message`，回退 `error.message`）。
