# 03 开发约束：会话记录

- 功能 slug：`conversation`
- 日期：2026-10-26

## 代码约束

- 沿用 controller → service → mapper 分层；service/mapper 不感知 HTTP，错误由 service 抛 `HTTPException`。
- SQLAlchemy 2.0 类型化写法（`Mapped` / `mapped_column`），查询使用 `select()`。
- 模型与 DTO 分离；DTO 不包含内部字段之外的敏感信息（本功能无敏感字段）。
- 所有接口返回 `ApiResponse`；分页统一使用 `PageResult[T]`。
- 会话查询必须同时约束 `user_id` 与 `state=1`，禁止只按 id 查询。
- 路径参数统一命名 `conversation_id`，避免与模型字段混淆。

## 数据约束

- 角色值只能为 `user` / `assistant` / `system`（CHECK 约束兜底）。
- 外键：`conversation.user_id → account.id`、`message.conversation_id → conversation.id`。
- 删除为软删除（state=2），不物理删除会话与消息。
- 建表脚本 `backend/app/database/init_db.py` 需导入新模型，保证 `create_all` 注册。

## 兼容性约束

- 不新增第三方依赖。
- 新增路由注册到 `backend/app/main.py`，自动继承全局鉴权。
