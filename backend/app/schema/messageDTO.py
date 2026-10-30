"""消息接口的请求结构。"""

from pydantic import BaseModel, Field


class CreateMessageRequest(BaseModel):
    role: str = Field(
        default="user",
        pattern="^(user|assistant|system)$",
        description="消息角色",
    )
    content: str = Field(
        min_length=1,
        max_length=20000,
        description="消息内容",
    )
