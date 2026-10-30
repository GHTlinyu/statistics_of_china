# 03 开发约束：长期记忆

- 功能 slug：`memory`
- 日期：2026-10-29

## 分层与调用

- `MemoryService` 放在 `backend/app/service/`，只通过 `MemoryMapper` 访问数据库；不得在 controller 或 agent 层直接写 SQL。
- agent 层的 `find_memories` / `extract_memories` / `decide_memory_update` 只做 LLM 调用与解析，不接触数据库。
- `ChatService` 只调用 `MemoryService`，不直接依赖 `MemoryMapper`。

## 读路径约束

- 记忆目录最多 10 条；目录为空时禁止调用 finder。
- finder 输入固定为「最近 2 条用户消息 + 本轮问题」，本轮问题在保存 user 消息之前传入。
- finder 返回的 ID 必须用 `user_id` 回表校验，禁止直接信任。
- 读路径任何异常都必须吞掉并降级为空列表，不能返回 500，也不能中断聊天。

## 写路径约束

- 只在 assistant 消息成功落库、且回答非空时触发；客户端中断或生成失败不触发。
- 提取在 `done` 事件前以 `asyncio.create_task(asyncio.to_thread(...))` 投递，禁止在事件循环里同步执行 LLM 或数据库 I/O。
- 后台任务的引用必须被持有，避免被垃圾回收；任务异常只记日志。
- 最近消息固定最多 20 条（约 10 轮）。
- 每个用户最多 10 条记忆；满额时只能更新已有记录，不能继续插入。
- `UPDATE` / `MERGE` / `REPLACE` 的 `memory_id` 必须先校验属于当前用户。
- `REPLACE` 的目标由系统指定（最旧同类型或全局最旧），不采信模型返回的其他 ID。
- 写入前对 `title` 做 255 字符截断。

## 日志与隐私

- 日志只记录 `user_id`、`conversation_id`、操作数量、异常堆栈；禁止打印记忆正文与用户完整问题。
- 模型调用失败记录 `exc_info`，便于排查，但不得把异常原文返回给前端。

## 数据库

- `memory` 表由 `backend/app/database/init_db.py` 注册；新环境需执行 `uv run python -m backend.app.database.init_db` 建表。
- 读写使用 `SessionLocal()` 短会话，LLM 调用期间不得持有会话。
