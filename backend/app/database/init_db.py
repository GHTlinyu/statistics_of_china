"""初始化数据库表结构的脚本。

用法:
    uv run python -m app.database.init_db
"""

from backend.app.database.database import Base, engine
from backend.app.model.chunk_retrieval import ChunkRetrieval  # noqa: F401
from backend.app.model.conversation import Conversation  # noqa: F401
from backend.app.model.memory import Memory  # noqa: F401
from backend.app.model.message import Message  # noqa: F401
from backend.app.model.user import User  # noqa: F401  确保模型注册到 Base.metadata


def create_tables() -> None:
    """在 PostgreSQL 中创建所有已注册模型的表（已存在的表会跳过）。"""
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_tables()
    print("数据库表创建完成")
