from typing import Literal

from pydantic import BaseModel


class MemoryUpdateDecision(BaseModel):
    action: Literal["MERGE", "REPLACE"]

    memory_id: int

    title: str

    description: str

    content: str
