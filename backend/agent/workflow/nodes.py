"""Agent 工作流节点：检索 → 生成。"""

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from backend.agent.client import get_llm
from backend.agent.tools import search_yearbook
from backend.agent.workflow.state import AgentState

logger = logging.getLogger(__name__)

# 进入 prompt 的检索条数；工具内部会按 4 倍放大召回
RETRIEVE_TOP_N = 5


def build_memory_context(memories: list[dict]) -> str:
    """把筛选后的长期记忆拼成 prompt 片段。"""

    if not memories:
        return "无相关长期记忆。"

    parts = []

    for memory in memories:
        memory_type = memory["memory_type"]
        title = memory["title"]
        content = memory["content"]

        if memory_type == "user":
            type_name = "用户长期信息"
        elif memory_type == "feedback":
            type_name = "用户长期指导"
        else:
            continue

        parts.append(
            f"""
[{type_name}]
标题：{title}
内容：{content}
""".strip()
        )

    if not parts:
        return "无相关长期记忆。"

    return "\n\n".join(parts)


def format_documents(documents: list[dict]) -> str:
    """把检索结果拼成 prompt 里的资料片段。"""

    parts = []

    for index, document in enumerate(documents, start=1):
        title = document.get("title") or ""
        content = document.get("content") or ""
        parts.append(f"文档 {index}\n标题：{title}\n内容：{content}")

    return "\n\n".join(parts)


async def retrieve_node(state: AgentState) -> dict:
    question = state["question"]

    # 工具是同步实现（DB + 外部接口），放到线程里跑，避免阻塞事件循环
    raw = await asyncio.to_thread(
        search_yearbook.invoke,
        {"query": question, "top_k": RETRIEVE_TOP_N},
    )
    documents = json.loads(raw)

    logger.info("检索完成：question=%r，命中 %d 条", question, len(documents))

    return {"documents": documents}


async def generate_node(state: AgentState) -> dict:
    question = state["question"]
    documents = state.get("documents") or []
    history = state.get("history") or []
    memories = state.get("memories") or []

    context = format_documents(documents)
    memory_context = build_memory_context(memories)

    system_prompt = f"""你是中国国家统计年鉴数据查询助手。

请严格根据提供的统计年鉴资料回答用户问题。

要求：
1. 不要编造资料中不存在的数据。
2. 如果资料不足以回答问题，明确说明无法从当前资料中确定。
3. 优先给出准确、简洁的回答。
4. 如涉及统计数据，应保持原始数据含义，不随意推断。

用户问题：
{question}

统计年鉴资料：
{context}

【相关长期记忆】
{memory_context}

长期记忆使用规则：
1. user 类型用于理解用户长期偏好、习惯和关注方向。
2. feedback 类型是用户对回答方式的长期指导，应在当前场景适用时遵守。
3. 长期记忆不是统计事实来源，不允许根据长期记忆编造统计数据。
4. 如果长期记忆与当前用户明确要求冲突，以当前用户要求为准。
"""

    messages = [
        SystemMessage(content=system_prompt),
        *history,
        HumanMessage(content=question),
    ]

    # 逐块流式生成，同时通过 LangGraph 的 custom 流把 token 交给上层
    writer = get_stream_writer()
    parts: list[str] = []

    async for piece in get_llm().astream(messages):
        if not piece:
            continue
        parts.append(piece)
        writer({"content": piece})

    return {"answer": "".join(parts)}
