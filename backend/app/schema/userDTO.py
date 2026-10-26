from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserDTO(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
