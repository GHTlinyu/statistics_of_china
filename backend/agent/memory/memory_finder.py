import json

from backend.agent.client import get_llm
from backend.agent.schema.memory_finder_schema import MemoryFinderResult


def find_memories(
    memory_catalog: list[dict],
    recent_user_messages: list[dict],
) -> MemoryFinderResult:

    if not memory_catalog:
        return MemoryFinderResult()

    memory_text = "\n\n".join(
        [
            (
                f"ID: {memory['id']}\n"
                f"标题: {memory['title']}\n"
                f"描述: {memory['description']}"
            )
            for memory in memory_catalog
        ]
    )

    history_text = "\n".join(
        [
            f"{index}. {message['content']}"
            for index, message in enumerate(
                recent_user_messages,
                start=1,
            )
        ]
    )

    prompt = f"""
你是长期记忆查找器。

你的任务是根据最近3轮对话，从用户的长期记忆目录中，
找出对当前对话真正有帮助的记忆。

你只能选择已有记忆，不允许创建、修改或总结新的长期记忆。

长期记忆目录：

{memory_text}

最近3轮对话：

{history_text}

选择规则：

1. 只有与当前对话明显相关的记忆才选择。
2. 用户长期指导 feedback，如果会影响当前回答方式，应选择。
3. 用户长期偏好或关注方向 user，如果与当前问题相关，应选择。
4. 不相关的记忆不要选择。
5. 不确定是否相关时，不要选择。
6. 不允许返回目录中不存在的 ID。
7. 可以选择多条，也可以一条都不选择。
8. 优先保持选择数量少，只加载真正有价值的记忆。

只返回合法 JSON，不要返回 Markdown 或解释文字。

格式：

{{
  "memory_ids": [1, 3]
}}

如果没有相关记忆：

{{
  "memory_ids": []
}}
"""

    response = get_llm().invoke(prompt)

    raw = response.content

    if not isinstance(raw, str):
        raise ValueError("Memory finder returned non-text content")

    data = json.loads(raw)

    result = MemoryFinderResult.model_validate(data)

    # 不信任模型返回的 ID
    valid_ids = {memory["id"] for memory in memory_catalog}

    result.memory_ids = [
        memory_id for memory_id in result.memory_ids if memory_id in valid_ids
    ]

    # 去重
    result.memory_ids = list(dict.fromkeys(result.memory_ids))

    return result
