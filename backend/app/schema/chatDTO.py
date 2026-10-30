"""聊天接口的请求 / SSE 事件结构。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="用户本轮问题",
    )


class ChatEvent(BaseModel):
    """SSE 通用事件。

    前端按 `type` 分发，`data` 里放该事件的具体字段：
    - start: {"conversation_id": 1}
    - token: {"content": "..."}
    - done:  {"conversation_id": 1, "message_id": 42}
    - error: {"code": "...", "message": "..."}
    """

    type: Literal["start", "token", "done", "error"]
    data: dict[str, Any] = Field(default_factory=dict)
