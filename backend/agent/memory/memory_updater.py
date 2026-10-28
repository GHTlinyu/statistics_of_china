import json

from backend.agent.client import get_llm
from backend.agent.schema.memory_schema import MemoryOperation
from backend.agent.schema.memory_updater_schema import MemoryUpdateDecision


def decide_memory_update(
    new_memory: MemoryOperation,
    existing_memories: list[dict],
    oldest_memory_id: int,
) -> MemoryUpdateDecision:

    existing_text = "\n\n".join(
        [
            (
                f"ID: {memory['id']}\n"
                f"标题: {memory['title']}\n"
                f"描述: {memory['description']}\n"
                f"完整内容: {memory['content']}"
            )
            for memory in existing_memories
        ]
    )

    prompt = f"""
你是长期记忆更新器。

用户长期记忆最多只能保存10条。

现在产生了一条新的长期记忆，但当前记忆槽位已经满。

你的任务是判断：

1. 如果新记忆与已有某条记忆语义高度相关，则使用 MERGE：
   - 将新旧信息合并
   - 不丢失仍然有效的重要信息
   - memory_id 使用被合并的已有记忆ID

2. 如果没有适合合并的已有记忆，则使用 REPLACE：
   - memory_id 必须使用系统指定的最旧记忆ID
   - 用新记忆完全覆盖旧记忆

注意：
- 这里只会提供和新记忆相同 memory_type 的已有记忆。
- 不允许选择不存在的 memory_id。
- 不要因为存在少量关键词相似就强行 MERGE。
- 合并后的内容必须可以独立理解。
- title 应简洁。
- description 用于后续 Agent 快速判断记忆是否相关。
- content 保存完整长期信息。

新记忆：

类型：
{new_memory.memory_type}

标题：
{new_memory.title}

描述：
{new_memory.description}

内容：
{new_memory.content}

已有同类型记忆：

{existing_text}

如果没有合适的合并对象，需要覆盖的最旧记忆ID：

{oldest_memory_id}

只返回合法 JSON。

MERGE 示例：

{{
  "action": "MERGE",
  "memory_id": 3,
  "title": "统计数据回复规范",
  "description": "用户要求数据使用Markdown表格并注明年份。",
  "content": "涉及统计数据时，应使用Markdown表格，并明确注明统计年份。"
}}

REPLACE 示例：

{{
  "action": "REPLACE",
  "memory_id": {oldest_memory_id},
  "title": "新的长期记忆",
  "description": "新的记忆描述",
  "content": "新的完整记忆内容"
}}
"""

    response = get_llm().invoke(prompt)

    raw = response.content

    if not isinstance(raw, str):
        raise ValueError("MemoryUpdater returned non-text content")

    data = json.loads(raw)

    return MemoryUpdateDecision.model_validate(data)
