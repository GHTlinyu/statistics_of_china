# 01 需求规格：会话记录

- 功能 slug：`conversation`
- 状态：已确认
- 日期：2026-10-26

## 背景与目标

提供会话记录查看能力（非聊天发送功能）：用户可以查看自己的会话列表、会话详情及会话中的历史消息。角色分为人类（`user`）与人工智能（`assistant`），另有 `system`。

## 需求条目

| 编号 | 需求 | 说明 |
| --- | --- | --- |
| R1 | 会话数据模型 | `conversation` 表：id、user_id（外键 account.id）、title、state、created_at、updated_at。`message` 表：id、conversation_id（外键 conversation.id）、role、content、created_at。 |
| R2 | 角色约束 | `role` 仅允许 `user` / `assistant` / `system`，由 CHECK 约束保证。 |
| R3 | 会话列表 | `GET /conversation`：分页返回当前用户 `state=1` 的会话，按 `updated_at` 倒序。 |
| R4 | 会话详情 | `GET /conversation/{id}`：返回会话信息；不属于当前用户或已删除返回 404。 |
| R5 | 消息分页 | `GET /conversation/{id}/messages`：分页返回该会话消息，按 `created_at` 正序（对话顺序）。 |
| R6 | 创建会话 | `POST /conversation`：创建属于当前用户的会话，`title` 可选，`state` 默认 1。 |
| R7 | 删除会话 | `DELETE /conversation/{id}`：软删除，`state` 置为 2，消息保留。 |
| R8 | state 语义 | `state=1` 正常；其他值（本期删除用 2）视为删除/归档，列表与详情均不可见。 |
| R9 | 数据隔离 | 所有接口仅能访问当前登录用户自己的会话，越权一律 404（不泄露存在性）。 |
| R10 | 统一响应 | 所有接口使用 `ApiResponse` 结构；分页数据使用 `PageResult`。 |

## 非目标

- 发送消息 / 聊天补全（后续聊天功能）
- 会话重命名、归档恢复
- 消息编辑、删除
- 全文检索

## 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-10-26 | 初稿 | 用户提出会话记录需求 |
