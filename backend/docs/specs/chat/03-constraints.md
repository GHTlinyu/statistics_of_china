# 03 开发约束：聊天（SSE 流式问答）

- 功能 slug：`chat`
- 日期：2026-10-29

## 分层与命名

- 沿用 controller → service → mapper → model 分层；service 不感知 HTTP 之外的东西（`ChatService` 只产出事件字典）。
- service 文件用 `xxxService.py` 放 `app/service`，数据访问用 `xxxMapper.py` 放 `app/mapper`；controller / schema 用 `chatController.py`、`chatDTO.py`。
- 参数校验放在 Pydantic DTO，业务错误由 service 抛 `HTTPException`。

## SSE 端点约束

- 聊天端点必须是 **async 生成器函数**（`async def` + `yield`），不能写成 `return EventSourceResponse(...)` 的普通协程：FastAPI 会直接迭代返回值，不会 await 返回对象。
- 预校验（会话归属、历史读取、保存 user 消息）放在依赖 `_prepare_turn` 中执行，保证 404 以普通 JSON 返回；生成器里只做流式输出。
- 事件结构固定为 `{"type": ..., "data": {...}}`，通过 `ServerSentEvent(data=...)` 输出；新增事件类型只能追加，不能改变已有字段语义。
- 不允许把异常原文塞进 `error.message`，对外统一固定文案，细节写日志。

## 数据库约束

- 流式路径（`chatService`）禁止持有请求级 Session；每个操作使用短会话 `SessionLocal()`，用完即关。
- 普通 CRUD（消息增删）使用 `get_db` 依赖注入，遵循项目约定。
- 消息写入必须校验 `conversation.user_id == current_user.user_id`；删除消息还要校验 `message.conversation_id` 与路径一致。
- 保存 assistant 消息放在线程池里执行，禁止在事件循环中做同步 DB I/O。

## 工作流约束

- `retrieve_node` / `generate_node` 是 async 节点，`graph.invoke` 不可用；调用方必须用 `ainvoke` / `astream`。
- token 事件通过 `get_stream_writer()` 写入，service 只消费 `stream_mode="custom"` 的 `{"content": ...}`。
- 检索 tool 为同步实现，节点内必须用 `asyncio.to_thread` 包裹，避免阻塞事件循环。

## 行为约束

- 短期上下文固定最近 **20 条消息**；本轮问题在读取 history 之后才落库，避免重复。
- 会话标题取首条问题的前 **20 个字**，仅当标题为空时写入。
- `content` 长度 1~4000；消息 `role` 仅允许 `user` / `assistant` / `system`。
- 每轮对话刷新 `conversation.updated_at`；列表排序依赖该字段。
- 客户端断开时保留部分回答；完整结束后不得重复保存。

## 本期范围

- 不接入长期记忆：`memories` 固定传空列表，禁止在 chat 链路里调用 memory finder / extractor。
- 不做 query 改写、工具事件、引用来源、用量统计。
- 不新增前端代码。

## 兼容性

- 路由沿用现有单数前缀 `/conversation`，不新增 `/conversations`。
- `GET /conversation/{id}/messages` 保持在 `conversationController`，消息增删放在 `messageController`，避免同路径重复注册。
- 现有会话列表、详情、删除接口的行为不变。
