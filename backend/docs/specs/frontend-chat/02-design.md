# 02 设计：前端对话页

- 功能 slug：`frontend-chat`
- 日期：2026-11-12

## 技术选型

| 包 | 版本 | 用途 |
| --- | --- | --- |
| `@ant-design/x` | 2.10.x | UI 组件：Conversations、Bubble.List、Sender、Welcome、Prompts |
| `@ant-design/x-sdk` | 2.10.x | useXChat、useXConversations、XRequest、AbstractChatProvider |
| `@ant-design/x-markdown` | 2.10.x | assistant 消息流式 Markdown 渲染 |

peer 依赖：`antd ^6.1.1`（已有 6.6.7）、`react >=18`（已有 19）——均兼容。

## 目录结构

```
frontend/src/
├── pages/Chat/index.tsx           # 对话页：侧栏 + 消息流 + 输入框
├── services/chat/types.ts         # ChatMessage、SSE 事件类型、API DTO 类型
├── services/chat/sse.ts           # SSE 流解析（XRequest transformStream）
├── services/chat/provider.ts      # BackendChatProvider（AbstractChatProvider 子类）
├── services/chat/conversationApi.ts  # 会话/消息 REST 封装（umi request）
└── .umirc.ts                      # /home 路由改指 Chat 页
```

## 后端协议（已实现，直接对接）

### SSE 聊天流

`POST /conversation/{id}/chat`，body `{content}`，响应 `text/event-stream`，每行 `data: {json}\n\n`，事件结构：

```json
{"type": "start",  "data": {"conversation_id": 1}}
{"type": "token",  "data": {"content": "..."}}
{"type": "done",   "data": {"conversation_id": 1, "message_id": 42}}
{"type": "error",  "data": {"code": "...", "message": "..."}}
```

### REST 接口（统一 `{code, message, data}` 结构，umi request 已剥离）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/conversation?page=1&page_size=20` | 会话列表（updated_at 倒序） |
| POST | `/conversation` | 新建会话，返回 ConversationDTO |
| GET | `/conversation/{id}/messages?page=1&page_size=50` | 历史消息（created_at 正序） |
| DELETE | `/conversation/{id}` | 删除会话 |

## 数据流设计

### 消息模型

```ts
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
```

### 自定义 Provider（核心）

```ts
class BackendChatProvider extends AbstractChatProvider<ChatMessage, Input, Output>
```

- `Input = { content: string }`，`Output = { content: string }`
- `request`：`XRequest('/api/conversation/{id}/chat', { manual: true, method: 'POST', headers: {Authorization} })`；URL 随 conversationKey 变化，每个会话独立 Provider 实例（`providerCache: Map<string, BackendChatProvider>`）
- `transformLocalMessage`：用户消息 → `{role: 'user', content}`
- SSE 解析：`transformStream` 把 `text/event-stream` 的 `data:` 行逐条解析为 JSON，按 `type` 分发：
  - `token` → `onUpdate({content: 追加片段}, ...)`（流式追加）
  - `done` / `error` → 结束；`error` 抛错触发 `requestFallback`
- 非 200（如 401）：按 XRequest onError 处理，401 清 token 跳登录

### 多会话

- `useXConversations`：conversations 来自 `GET /conversation` 第一页（20 条）；key = 后端会话 id 字符串
- `useXChat({ provider, conversationKey, defaultMessages, requestFallback })`
- `defaultMessages`：异步拉 `GET /conversation/{id}/messages`（page_size 50），映射为 `MessageInfo<ChatMessage>`；历史消息渲染时取最新一页即可
- 新建会话：先 `POST /conversation` 拿到后端 id，再 `addConversation` + 切换（后端标题自动填充逻辑保留，发消息后刷新列表）
- 删除会话：`DELETE` 成功后 `removeConversation`，删除的是当前会话则切到下一个或新建空会话

### 停止生成

- `Sender.onCancel → abort()`：断开 SSE；后端落库已生成的部分回答（chat R6）
- `requestFallback`：`AbortError` → 显示「已停止生成」，其他错误 → 显示 error 事件文案

### 认证与错误处理

- REST 走 umi `request`（已有拦截器：自动带 token、401 跳登录）
- SSE 走 XRequest 原生 fetch：token 从 localStorage 注入 headers；401 响应单独处理（清 token + 跳 `/login`）

## 页面布局

```
┌─────────────┬──────────────────────────────┐
│ 会话列表     │  Bubble.List（消息流）        │
│ (Conversations)│                              │
│  + 新建按钮  │  ├ assistant: Markdown 渲染    │
│             │  └ user: 右侧气泡              │
│  ─────────  │  ──────────────────────────── │
│ 用户区      │  Sender（输入框 + 停止按钮）    │
│ + 退出登录   │                              │
└─────────────┴──────────────────────────────┘
```

- 空态（当前会话无消息）：Welcome + Prompts 建议问题，点击即发送
- `/home` 路由改指 Chat 页；用户信息与退出登录放侧栏底部
- assistant 消息用 `@ant-design/x-markdown` 渲染（支持表格、代码块高亮）

## 验收对照

| 需求 | 设计落点 |
| --- | --- |
| R1 | 依赖三个 @ant-design/x 系列包 |
| R2 | Chat 页替换 Home，路由调整 |
| R3 | `provider.ts` 自定义 Provider + `sse.ts` 解析 |
| R4 | useXChat 消息状态机 + requestPlaceholder/requestFallback |
| R5 | useXConversations + defaultMessages 异步加载 |
| R6 | conversationApi 新建/删除 |
| R7 | Sender onCancel → abort |
| R8 | x-markdown 渲染 assistant 内容 |
| R9 | XRequest headers 注入 token；401 单独处理 |
| R10 | Welcome + Prompts 空态 |

## 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-11-12 | 初稿 | 需求确认后设计 |
