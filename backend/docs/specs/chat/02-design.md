# 02 设计：聊天（SSE 流式问答）

- 功能 slug：`chat`
- 日期：2026-10-29

## 总体流程

```
Client
  │ POST /conversation/{id}/chat {"content": "..."}
  ▼
Controller（依赖 _prepare_turn 先执行）
  ├─ ChatService.get_conversation(id, user_id)   → 不存在/越权：404
  ├─ ChatService.load_history(id, limit=20)      → list[BaseMessage]
  └─ ChatService.prepare_turn(conversation, q)   → 保存 user 消息、补标题、touch
  ▼
异步生成器（SSE）
  ├─ yield {"type": "start", "data": {...}}
  ├─ graph.astream({"question", "history", "memories": []}, stream_mode="custom")
  │    ├─ retrieve_node（async，工具放线程池）
  │    └─ generate_node（async，token 写入 custom 流）
  ├─ 累积回答 → 保存 assistant 消息（线程池）
  └─ yield {"type": "done", "data": {...}}
```

异常时 yield `error` 事件；客户端断开时在 `finally` 中保存部分回答。

## 模块结构

```
backend/app/
├── controller/chatController.py    聊天 SSE 接口 + 预校验依赖
├── controller/messageController.py 消息增删接口
├── service/chatService.py          聊天编排（权限、历史、标题、落库、流式）
├── service/messageService.py       消息增删业务
├── mapper/messageMapper.py         消息数据访问（扩展原有分页查询）
├── mapper/conversationMapper.py    新增 update_title / touch
├── schema/chatDTO.py               ChatRequest、ChatEvent
└── schema/messageDTO.py            CreateMessageRequest

backend/agent/workflow/nodes.py
├── retrieve_node  async，asyncio.to_thread 调检索 tool
└── generate_node  async，get_llm().astream + get_stream_writer
```

命名约定：service 用 `xxxService.py` 放 `app/service`，数据访问用 `xxxMapper.py` 放 `app/mapper`，controller / schema 用 `xxxController.py`、`xxxDTO.py`。

## 接口定义

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/conversation/{id}/chat` | SSE 流式问答，返回 `text/event-stream` |
| POST | `/conversation/{id}/messages` | 手工新增消息，201，`ApiResponse[MessageDTO]` |
| DELETE | `/conversation/{id}/messages/{message_id}` | 删除消息，200 |
| GET | `/conversation/{id}/messages` | 既有分页查询，保持不变 |

聊天与消息写接口都需要登录，并校验会话归属。

## SSE 事件契约

统一使用单个 `data:` 事件（不依赖命名事件），前端按 `type` 分发：

```
data: {"type":"start","data":{"conversation_id":5}}
data: {"type":"token","data":{"content":"202"}}
data: {"type":"token","data":{"content":"4 年末"}}
data: {"type":"done","data":{"conversation_id":5,"message_id":11}}
data: {"type":"error","data":{"code":"AGENT_EXECUTION_ERROR","message":"生成失败，请稍后重试"}}
```

| type | data 字段 |
| --- | --- |
| start | `conversation_id` |
| token | `content` |
| done | `conversation_id`、`message_id`（无回答时为 null） |
| error | `code`、`message` |

新增事件类型（如 `tool_call`、`citation`）只需扩展 `type`，前端未知类型可忽略。

## 数据库会话策略

聊天流可能持续数十秒，**不持有请求级 `Session`**。`chatService` 每个操作内部用 `SessionLocal()` 短会话：

- `get_conversation` / `load_history` / `prepare_turn` 各开一次，随用随关；
- `save_assistant_message` 在线程池里执行，避免阻塞事件循环；
- 普通 CRUD 接口（消息增删）仍按项目约定用 `get_db` 依赖。

## 短期上下文

`MessageRepository.find_recent_by_conversation` 按 `created_at desc, id desc` 取最近 20 条再反转成正序；`user → HumanMessage`、`assistant → AIMessage`，`system` 不进入 history（避免注入）。

## 标题与活跃时间

- `prepare_turn` 中若 `conversation.title` 为空，取 `question[:20]` 写入；
- 每保存一条消息调用 `ConversationMapper.touch`，刷新 `updated_at`。

## 停止生成与部分回答

- 客户端断开 → 响应生成器被关闭 → `stream_answer` 的 `finally` 执行；
- `finally` 中用 `asyncio.shield(asyncio.to_thread(save_assistant_message, ...))` 保存已累积内容，防止取消把写入一同打断；
- 已经完整走完 `done` 的轮次不会重复保存（`saved` 标记）。

## 错误处理

| 场景 | 处理 |
| --- | --- |
| 会话不存在 / 越权 | 依赖中抛 404，返回普通 JSON |
| 参数非法 | FastAPI 422 |
| 检索或生成异常 | 记录 `conversation_id` 与堆栈，返回固定 `error` 事件 |
| 客户端断开 | 不返回 `error`，保存部分回答后结束 |
| 空回答 | 不保存 assistant 消息，`done.message_id` 为 null |

## 工作流改造

- `retrieve_node`、`generate_node` 改为 `async`，`graph.invoke` 不再可用，统一用 `ainvoke` / `astream`；
- `generate_node` 用 `get_llm().astream(messages)` 逐块产出，`get_stream_writer()` 写 `{"content": piece}`；
- 检索 tool 是同步实现（DB + 外部接口），用 `asyncio.to_thread` 包一层避免阻塞事件循环。

## 关键决策

1. **单事件信封**：所有事件走一个 `data:` JSON，`type` 内部分发，后续加事件类型不需要改前端解析器。
2. **预校验放依赖**：FastAPI 的 SSE 路由直接迭代 async 生成器、不 await 返回对象，404 若写在生成器里会变成半截流；放进依赖即可正常返回 JSON 404。
3. **短会话**：流式期间不占用连接池连接，避免长事务。
4. **部分保存**：用户主动停止也应当留下他看过的内容，避免下一轮历史缺失。
5. **本期不接记忆**：`memories` 固定空列表，记忆节点后续以独立节点接入，不改动本轮链路。
