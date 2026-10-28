# 04 交付：聊天（SSE 流式问答）

- 功能 slug：`chat`
- 日期：2026-10-29
- 状态：已实现并完成真实联调（真实数据库、真实 embedding / rerank / LLM）

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/controller/chatController.py` | 新增 SSE 聊天接口，预校验依赖 `_prepare_turn` |
| `backend/app/service/chatService.py` | 新增 `ChatTurn`、`prepare_chat_turn`、`ChatService`（权限、历史、标题、落库、流式） |
| `backend/app/schema/chatDTO.py` | 新增 `ChatRequest`、`ChatEvent` |
| `backend/app/controller/messageController.py` | 新增消息增删接口 |
| `backend/app/service/messageService.py` | 新增消息增删业务与归属校验 |
| `backend/app/mapper/messageMapper.py` | 扩展：新增消息建/查/删、最近 N 条、最近 N 条用户消息 |
| `backend/app/schema/messageDTO.py` | 新增 `CreateMessageRequest` |
| `backend/app/mapper/conversationMapper.py` | 新增 `update_title`、`touch` |
| `backend/agent/workflow/nodes.py` | 检索/生成节点改 async；生成节点流式写 token |
| `backend/app/main.py` | 注册 chat / message 路由 |

## 验证结果（真实联调，会话 5 / 用户 1）

| 场景 | 结果 |
| --- | --- |
| 第一轮「2024 年全国人口是多少」 | 2.78s；start 1 / token 26 / done 1；回答「140828 万人」 |
| 第二轮「那 2023 年呢？」 | 2.70s；start 1 / token 27 / done 1；回答资料不含 2023 年数据 |
| SSE 响应头 | `text/event-stream; charset=utf-8` |
| 事件结构 | `{"type": ..., "data": {...}}` 全部符合契约 |
| 消息落库 | 4 条（user / assistant 各 2），内容与流一致 |
| 会话标题 | 自动写成「2024 年全国人口是多少」 |
| 活跃时间 | `updated_at` 刷新，列表按最近活跃排序 |
| 停止生成 | 取 3 个 token 后 `aclose`，落库部分回答「2024年末」（6 字） |
| 消息增删 | POST 201、DELETE 200，列表数量正确变化 |
| 越权聊天 / 建消息 | 均 404 |
| 参数校验 | 空内容、超 4000 字、非法 role 均 422 |

## 手工联调

```bash
curl -N -X POST http://127.0.0.1:8000/conversation/5/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"2024 年全国人口是多少"}'
```

## 已知限制

1. 追问依赖上下文（如「那 2023 年呢」），检索只用原始问题、未做 query 改写，召回可能不准。
2. `TestClient` 会缓冲整个 SSE 响应，本地用它测「中途停止」不能反映真实逐 token 行为；真流式需用 uvicorn + curl / 浏览器验证。
3. 数据库在联调期间多次掉线（`server closed the connection unexpectedly`），建议配置自动重启。
4. 长期记忆未接入，`memories` 固定为空。
5. 前端尚未接入 SSE，需按 `{"type","data"}` 结构自行解析。

## 后续建议

1. 追问场景加 query 改写（用最近两三轮拼检索语句）后再检索。
2. 接入记忆：finder 作为 `retrieve` 前的节点，extractor 在 `done` 后异步执行。
3. 前端聊天页按 SSE 事件渲染，`done` 后刷新会话列表。
4. 补充 chat 的自动化测试（服务层事件序列、断开保存已用脚本验证，可固化为 pytest）。
