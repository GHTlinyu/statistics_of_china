from langgraph.graph import START, END, StateGraph

from agent.nodes import generate_node, retrieve_node
from agent.state import AgentState


def create_graph():
    builder = StateGraph(AgentState)

    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)

    return builder.compile()


graph = create_graph()
