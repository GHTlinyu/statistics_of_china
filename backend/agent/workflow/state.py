from typing import TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    # 当前用户问题
    question: str

    # 当前 conversation 的短期上下文
    history: list[BaseMessage]

    # Memory Finder 筛选后的长期记忆
    memories: list[dict]

    # RAG 检索结果
    documents: list[dict]

    # 最终回答
    answer: str
