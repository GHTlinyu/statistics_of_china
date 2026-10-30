from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    """通用分页结果。"""

    items: list[T]
    total: int
    page: int
    page_size: int
