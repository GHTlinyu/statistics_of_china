# 04 交付：长期记忆

- 功能 slug：`memory`
- 日期：2026-10-30
- 状态：已实现并完成真实联调（真实数据库、真实 finder / extractor / LLM）

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/mapper/memoryMapper.py` | 新增：用户记忆的列表、按类型列表、批量读取、计数、最旧查询、创建与更新 |
| `backend/app/service/memoryService.py` | 新增：读路径 finder 编排、写路径 extractor / updater 编排与容量控制 |
| `backend/app/service/chatService.py` | `ChatTurn` 增加 `user_id` / `memories`；流开始前读取记忆；assistant 落库后投递后台提取任务 |
| `backend/app/controller/chatController.py` | 把 `user_id` / `memories` 传入 `stream_answer` |
| `backend/agent/memory/memory_finder.py` | 修正：最近用户消息按 `dict["content"]` 拼 prompt |
| `backend/docs/specs/chat/*.md` | 同步更新聊天需求、设计、约束、交付 |
| `backend/docs/specs/memory/*.md` | 新增本功能四件套 |

## 验证结果

| 场景 | 方式 | 结果 |
| --- | --- | --- |
| 模块编译与导入 | `python -m compileall`、导入 `backend.app.main` / `chatService` / `memoryService` | 通过 |
| REPLACE 目标 | SQLite + mock updater 返回其他同类型 ID | 强制替换最旧同类型记忆，通过 |
| MERGE 目标 | SQLite + mock updater 返回同类型 ID | 更新指定记忆，数量不变，通过 |
| 非法 MERGE ID | mock 返回不存在的 ID | 忽略且不写库，通过 |
| 无同类型兜底 | 10 条 feedback 用户新增 user 记忆 | 替换全局最旧并改为 user 类型，数量保持 10，通过 |
| 越权 UPDATE | 用 user 2 更新 user 1 的记忆 | 不写库，通过 |
| 读路径上下文 | mock finder 捕获入参 | 最近 2 条用户消息 + 本轮问题，顺序正确，通过 |
| finder prompt | mock LLM 捕获 prompt | 输出 `1. hello`，未出现 dict repr，通过 |
| 容量内 CREATE | SQLite + mock extractor | 写入成功，`source_conversation_id` 为本轮会话，通过 |
| UPDATE 落库 | SQLite + mock extractor | 标题与内容更新，通过 |
| extractor 异常 | mock 抛 `RuntimeError` | 只记日志，不向上抛，通过 |
| 空记忆目录 | finder 设为必须不被调用 | 直接返回空，通过 |

## 手工联调（已执行，2026-10-30）

环境：真实 PostgreSQL + 真实 embedding / rerank / LLM；测试用户 `memtest_1030`（id 4），会话 9。

```bash
# 1. 确认 memory 表存在（新环境执行一次）
uv run python -m backend.app.database.init_db

# 2. 启动服务
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# 3. 连续两轮提问，观察第二轮回答是否遵守第一轮产生的记忆
curl -N -X POST http://127.0.0.1:8000/conversation/<id>/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content":"以后回答统计数据时请用表格，并注明年份"}'
```

| 场景 | 结果 |
| --- | --- |
| 建表 | `init_db` 创建 `memory` 表，其余表不受影响 |
| 第一轮（提格式要求） | `start` / `token` / `done` 正常 |
| 后台提取 | `memory` 表出现 1 条 `feedback` 记忆：标题「统计数据回答格式要求」，内容「当回答统计数据时，应使用 Markdown 表格呈现数据，并在表格中明确标注年份」，`source_conversation_id=9` |
| 第二轮（2024 年全国人口） | 回答使用 Markdown 表格并标注年份 → finder 选中记忆并注入 prompt 生效 |
| 无关问题（讲数字笑话） | 回答为纯文本、无表格 → finder 过滤不相关记忆 |
| 无价值对话（笑话轮） | 提取后记忆数量不变（1 条）→ extractor 正确判断无长期价值 |
| 客户端断开 | curl 中途截断后部分回答已落库（57 字），与接入前行为一致 |

## 已知限制

1. finder 在流开始前同步调用，首 token 延迟增加一次 LLM 调用时间。
2. 提取为纯 best-effort：LLM 超时、返回非法 JSON 或 updater 决策失败时本轮不写入，不回滚其他已成功的操作。
3. 并发的两轮问答可能同时触发提取，容量判断没有加锁，极端情况下可能短暂超过 10 条。
4. 未新增记忆管理 API / 前端页面；记忆正文不写日志。
5. 自动化测试目前以一次性脚本验证，尚未固化为 pytest。

## 后续建议

1. 把本次 SQLite mock 用例固化为 pytest（容量、越权、降级、finder 输入）。
2. 如首 token 延迟不可接受，可把 finder 移到 `stream_answer` 内、`start` 事件之后执行，或与检索并行。
3. 需要时再补记忆管理 API 与前端页面。
