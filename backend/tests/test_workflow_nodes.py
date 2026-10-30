"""Agent 工作流节点：检索、生成与 prompt 片段。"""

import json

from langchain_core.messages import AIMessage, HumanMessage

import backend.agent.workflow.nodes as nodes


class FakeWriter:
    def __init__(self):
        self.writes = []

    def __call__(self, value):
        self.writes.append(value)


class FakeLLM:
    def __init__(self, pieces):
        self.pieces = list(pieces)
        self.messages = None

    async def astream(self, messages):
        self.messages = messages
        for piece in self.pieces:
            yield piece


def test_format_documents():
    text = nodes.format_documents(
        [
            {"title": "表 1", "content": "140828"},
            {"title": "表 2", "content": "94350"},
        ]
    )

    assert "文档 1" in text
    assert "标题：表 1" in text
    assert "内容：140828" in text
    assert "文档 2" in text


def test_format_documents_empty():
    assert nodes.format_documents([]) == ""


def test_build_memory_context_empty():
    assert nodes.build_memory_context([]) == "无相关长期记忆。"


def test_build_memory_context_skips_unknown_types():
    text = nodes.build_memory_context(
        [
            {
                "memory_type": "user",
                "title": "偏好",
                "content": "喜欢表格",
            },
            {
                "memory_type": "feedback",
                "title": "指导",
                "content": "注明来源",
            },
            {
                "memory_type": "other",
                "title": "忽略",
                "content": "不应出现",
            },
        ]
    )

    assert "用户长期信息" in text
    assert "偏好" in text
    assert "用户长期指导" in text
    assert "指导" in text
    assert "忽略" not in text


async def test_retrieve_node_invokes_tool(monkeypatch):
    class FakeTool:
        def __init__(self):
            self.args = None

        def invoke(self, args):
            self.args = args
            return json.dumps(
                [{"title": "表 1", "content": "140828"}],
                ensure_ascii=False,
            )

    tool = FakeTool()
    monkeypatch.setattr(nodes, "search_yearbook", tool)

    result = await nodes.retrieve_node({"question": "2024 年人口"})

    assert tool.args == {
        "query": "2024 年人口",
        "top_k": nodes.RETRIEVE_TOP_N,
    }
    assert result == {
        "documents": [{"title": "表 1", "content": "140828"}]
    }


async def test_generate_node_streams_and_injects_context(monkeypatch):
    llm = FakeLLM(["你", "好"])
    writer = FakeWriter()
    monkeypatch.setattr(nodes, "get_llm", lambda: llm)
    monkeypatch.setattr(nodes, "get_stream_writer", lambda: writer)

    result = await nodes.generate_node(
        {
            "question": "人口",
            "documents": [{"title": "表 1", "content": "140828"}],
            "history": [
                HumanMessage(content="上一轮"),
                AIMessage(content="上一答"),
            ],
            "memories": [
                {
                    "memory_type": "feedback",
                    "title": "格式",
                    "content": "用 Markdown 表格",
                }
            ],
        }
    )

    assert result == {"answer": "你好"}
    assert writer.writes == [{"content": "你"}, {"content": "好"}]
    assert len(llm.messages) == 4
    assert llm.messages[0].type == "system"
    assert "人口" in llm.messages[0].content
    assert "表 1" in llm.messages[0].content
    assert "用 Markdown 表格" in llm.messages[0].content
    assert llm.messages[-1].content == "人口"
