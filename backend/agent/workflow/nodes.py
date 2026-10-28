import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from rag.embedding import EmbeddingService
from rag.retriever import DocumentRetriever
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)


load_dotenv()


embedding_service = EmbeddingService()

retriever = DocumentRetriever(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
)


llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL"),
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL"),
    temperature=0,
)


def build_memory_context(
    memories: list[dict],
) -> str:

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


def retrieve_node(state: AgentState) -> dict:
    question = state["question"]

    query_embedding = embedding_service.encode_query(question)

    documents = retriever.search(
        query_embedding=query_embedding,
        top_k=5,
    )

    return {
        "documents": documents,
    }


def generate_node(state: AgentState) -> dict:
    question = state["question"]
    documents = state["documents"]
    history = state["history"]
    memories = state["memories"]

    memory_context = build_memory_context(memories)

    context_parts = []

    for index, document in enumerate(documents, start=1):
        context_parts.append(
            f"""
                文档 {index}

                标题：
                {document["title"]}

                内容：
                {document["content"]}
                """
        )

    context = "\n".join(context_parts)

    system_prompt = f"""
        你是中国国家统计年鉴数据查询助手。

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
                4. 如果长期记忆与用户当前明确要求冲突，以当前用户要求为准。
        """
    messages = [
        SystemMessage(content=system_prompt),
        *history,
        HumanMessage(content=question),
    ]

    response = llm.invoke(messages)

    return {
        "answer": response.content,
    }
