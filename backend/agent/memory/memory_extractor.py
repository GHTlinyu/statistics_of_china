import json

from pydantic import ValidationError

from backend.agent.client import get_llm
from backend.agent.schema.memory_schema import MemoryExtractionResult


def extract_memories(
    existing_memories: list[dict],
    recent_messages: list[dict],
) -> MemoryExtractionResult:

    memories_text = "\n".join(
        [
            (
                f"ID: {memory['id']}\n"
                f"类型: {memory['memory_type']}\n"
                f"标题: {memory['title']}\n"
                f"描述: {memory['description']}"
            )
            for memory in existing_memories
        ]
    )

    history_text = "\n".join(
        [f"{message['role']}: {message['content']}" for message in recent_messages]
    )

    prompt = f"""
你是长期记忆提取器。

你的任务是根据最近10轮对话，判断是否存在值得跨会话长期保存的信息。

长期记忆只允许两类：

user：
用户长期稳定的偏好、习惯、关注方向。

feedback：
用户对助手提出的长期指导、纠正和行为规则。

已有长期记忆：

{memories_text or "暂无"}

最近10轮对话：

{history_text}

规则：

1. 单次查询、临时要求、普通问答不要保存。
2. 已有记忆已经包含相同信息时，不要重复创建。
3. 新信息修改或补充已有记忆时，使用 UPDATE。
4. UPDATE 必须使用已有记忆 ID。
5. 一次允许生成多条操作。
6. 没有长期记忆价值时返回空 operations。
7. user 与 feedback 不要混淆。

你必须只返回合法 JSON。
不要输出 Markdown。
不要输出 ```json。
不要输出任何解释文字。

返回结构必须严格为：

{{
  "operations": [
    {{
      "action": "CREATE",
      "memory_id": null,
      "memory_type": "user",
      "title": "标题",
      "description": "摘要",
      "content": "完整记忆内容"
    }}
  ]
}}

UPDATE 示例：

{{
  "operations": [
    {{
      "action": "UPDATE",
      "memory_id": 1,
      "memory_type": "feedback",
      "title": "标题",
      "description": "摘要",
      "content": "完整记忆内容"
    }}
  ]
}}

没有需要保存的记忆：

{{
  "operations": []
}}
"""

    response = get_llm().invoke(prompt)

    raw = response.content

    if not isinstance(raw, str):
        raise ValueError("Memory extractor returned non-text content")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Memory extractor returned invalid JSON: {raw}") from exc

    try:
        return MemoryExtractionResult.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"Memory extractor output schema validation failed: {data}"
        ) from exc
