from pydantic import BaseModel, Field


class MemoryFinderResult(BaseModel):
    memory_ids: list[int] = Field(
        default_factory=list,
        description="与当前最近会话相关、需要加载的长期记忆ID",
    )
