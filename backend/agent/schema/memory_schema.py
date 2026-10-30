from typing import Literal

from pydantic import BaseModel, Field


class MemoryOperation(BaseModel):
    action: Literal["CREATE", "UPDATE"]

    memory_id: int | None = Field(
        default=None,
        description="UPDATE 时填写已有记忆ID；CREATE 时为 null",
    )

    memory_type: Literal["user", "feedback"]

    title: str

    description: str

    content: str


class MemoryExtractionResult(BaseModel):
    operations: list[MemoryOperation] = Field(
        default_factory=list,
        description="本次需要执行的长期记忆变更；没有需要保存的记忆时返回空数组",
    )
