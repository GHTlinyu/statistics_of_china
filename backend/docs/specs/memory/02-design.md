# 02 设计：长期记忆

- 功能 slug：`memory`
- 日期：2026-10-29

## 总体流程

```
读路径（流开始前，prepare_chat_turn 内）
  ├─ MemoryMapper.list_by_user(user_id, limit=10)         记忆目录
  ├─ MessageMapper.find_recent_user_messages(conv, limit=2) 最近 2 条用户消息
  ├─ find_memories(目录, 最近 2 条 + 本轮问题)              LLM 选 ID
  ├─ MemoryMapper.find_by_ids(user_id, ids)                回表校验归属
  └─ ChatTurn.memories → graph.astream({"memories": ...})

写路径（assistant 落库后，后台任务）
  ├─ MessageMapper.find_recent_by_conversation(conv, limit=20)
  ├─ MemoryMapper.list_by_user(user_id, limit=10)          已有记忆
  ├─ extract_memories(已有记忆, 最近 20 条)                 LLM → CREATE / UPDATE
  └─ 逐条落库：未满直接 CREATE；已满走 updater MERGE / REPLACE
```

## 模块结构

```
backend/app/
├── mapper/memoryMapper.py        memory 表数据访问（新增）
└── service/memoryService.py     记忆读写编排（新增）

backend/agent/memory/
└── memory_finder.py              修正：recent_user_messages 按 dict["content"] 拼 prompt
```

`MemoryService` 负责数据库与 agent 层函数的编排；`ChatService` 只负责把读到的记忆放进 `ChatTurn`、把提取动作交给后台任务。

## 读路径

`MemoryService.find_long_term_memories(user_id, conversation_id, current_question)`：

1. 短会话读取记忆目录，按 `updated_at desc, id desc` 取前 10 条；目录为空直接返回 `[]`，不调用 LLM。
2. 读取该会话最近 2 条用户消息，与本轮问题拼成 3 段用户输入交给 `find_memories`。
3. 用 finder 返回的 ID 回表 `find_by_ids(user_id, ids)`，非本人 ID 自然被过滤。
4. 返回 `list[dict]`（`id` / `memory_type` / `title` / `description` / `content`），供 `build_memory_context` 使用。

调用位置：`prepare_chat_turn` 中、`prepare_turn` 保存本轮 user 消息之前，与参考示例 `controller/chat.py` 的顺序一致。Finder 是同步 LLM 调用，`_prepare_turn` 是 FastAPI 同步依赖，在线程池中执行，不阻塞事件循环。

## 写路径与容量

`MemoryService.extract_and_save(user_id, conversation_id)` 在后台线程执行：

1. 读取最近 20 条消息（约 10 轮）与用户已有记忆（最多 10 条）。
2. `extract_memories` 返回 `CREATE` / `UPDATE` 操作列表。
3. 逐条应用：
   - `UPDATE`：按 `(user_id, memory_id)` 查找，存在才更新。
   - `CREATE` 且数量 < 10：直接插入，`source_conversation_id` 记为本轮会话。
   - `CREATE` 且数量 ≥ 10：
     - 有同类型记忆：`decide_memory_update` 决定 `MERGE`（合并到指定同类型记忆）或 `REPLACE`（强制替换最旧同类型记忆）。
     - 无同类型记忆：直接替换全局最旧一条。

`memory.title` 为 `VARCHAR(255)`，写入前按 255 截断。每次操作使用短会话，LLM 决策期间不持有数据库会话。

## 错误处理

| 场景 | 处理 |
| --- | --- |
| 无记忆目录 | 读路径直接返回空，跳过 finder |
| finder 超时 / JSON 非法 / 配置缺失 | 记录警告，按无记忆继续聊天 |
| extractor 失败 | 记录警告，本轮不写入 |
| updater 失败 | 跳过当前条 CREATE，不影响其他操作 |
| 模型返回越权 / 不存在 ID | 校验后忽略并记录警告 |
| 客户端中途断开 | `done` 未产出，不触发提取，只保留部分回答 |

## 关键决策

1. **读写分离时机**：读在流开始前（与参考示例一致），写在 `done` 之后后台执行；写失败不影响用户已经看到的回答。
2. **回表校验**：finder / extractor / updater 的 ID 全部视为不可信输入，所有落库都以 `user_id + memory_id` 为准。
3. **容量兜底**：REPLACE 的目标不由模型决定；同类型场景强制最旧同类型，无同类型则全局最旧，保证 10 条上限不被突破。
4. **短会话**：读写都使用 `SessionLocal()` 短会话，LLM 调用期间不占用连接。
5. **修复 finder 输入**：`memory_finder` 原来把消息当字符串迭代，接入时统一传 dict 并取 `content`，避免 prompt 污染。
