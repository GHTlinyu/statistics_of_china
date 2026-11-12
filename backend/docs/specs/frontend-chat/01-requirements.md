# 01 需求规格：前端对话页

- 功能 slug：`frontend-chat`
- 状态：已确认
- 日期：2026-11-12

## 背景与目标

后端接口已基本完成（认证、会话、消息、SSE 流式问答，见 `backend/docs/specs/chat/`、`backend/docs/specs/conversation/`）。本期开发前端对话页面，基于 `@ant-design/x`（UI 组件）+ `@ant-design/x-sdk`（useXChat / XRequest），实现完整的「提问 → 流式回答」体验。后端 SSE 为自定义协议（`start` / `token` / `done` / `error`），需自定义 Chat Provider 适配。

## 需求条目

| 编号 | 需求 | 说明 |
| --- | --- | --- |
| R1 | 技术栈 | 前端新增依赖 `@ant-design/x`、`@ant-design/x-sdk`（2.10.x，peer 兼容现有 antd 6 / React 19）。 |
| R2 | 页面布局 | 左侧会话列表（Conversations 组件）+ 右侧聊天区（Bubble.List 消息流 + Sender 输入框），替换现有 Home 页（保留退出登录入口）。 |
| R3 | 自定义 Chat Provider | 实现 `AbstractChatProvider` 子类，用 XRequest（`manual: true`）请求 `POST /conversation/{id}/chat`，将后端 SSE 事件映射为流式输出。 |
| R4 | 流式问答 | 发送后立即显示用户消息与加载占位；`token` 事件追加内容实时渲染；`done` 标记完成；`error` 事件显示兜底文案。 |
| R5 | 多会话 | 会话列表来自 `GET /conversation`（分页、按活跃倒序）；切换会话加载历史消息 `GET /conversation/{id}/messages`（正序渲染）；每个会话独立 Provider 实例。 |
| R6 | 新建/删除会话 | 新建调用 `POST /conversation`（首条消息后标题由后端自动填充，需刷新列表）；删除调用 `DELETE /conversation/{id}`。 |
| R7 | 停止生成 | Sender 提供取消按钮，触发 abort 断开 SSE；已生成的部分回答由后端落库，刷新后可见。 |
| R8 | Markdown 渲染 | assistant 消息按 Markdown 流式渲染（支持代码块、表格），使用 `@ant-design/x-markdown`。 |
| R9 | 认证与代理 | 请求经 umi `/api` 代理到后端 8000；Bearer token 从 localStorage 注入；SSE 请求不经过 umi request 拦截器，401 跳登录需在 XRequest 错误处理中单独实现。 |
| R10 | 空态 | 首次进入/当前会话无消息时显示欢迎空态与建议问题（Prompts）。 |

## 非目标

- 引用来源展示（后端尚无 sources 事件）
- 消息编辑/重试、会话重命名
- 移动端适配

## 验收标准

1. 登录后进入对话页，发送问题可见流式输出，Markdown 渲染正确。
2. 会话列表可切换、新建、删除；切换会话正确加载历史消息。
3. 停止生成后，刷新页面可见已生成的部分回答（后端已落库）。
4. token 过期时跳转登录页。
5. `tsc --noEmit` 类型检查通过。

## 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-11-12 | 初稿 | 用户提出前端对话页需求，技术方案为 @ant-design/x + x-sdk |
