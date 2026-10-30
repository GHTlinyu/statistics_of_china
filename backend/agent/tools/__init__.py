"""Agent 工具集合。"""

from backend.agent.tools.retrieval import search_yearbook

TOOLS = [search_yearbook]

__all__ = ["TOOLS", "search_yearbook"]
