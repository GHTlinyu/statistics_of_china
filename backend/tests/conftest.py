"""Pytest 公共夹具：SQLite 测试库、FastAPI 客户端、鉴权与验证码辅助。"""

import os

# 必须在导入 Settings 之前写入占位配置，测试不依赖仓库根 .env
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "statistics_test")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.model.conversation import Conversation
from backend.app.model.user import User
from backend.app.schema.authDTO import TokenPayload
from backend.app.security.security import create_access_token, hash_password

# 测试库 DDL：SQLite 下 BigInteger 主键不会自增，统一改成 INTEGER PRIMARY KEY
TEST_DDL = [
    """
    CREATE TABLE account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(50) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'user',
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE conversation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title VARCHAR(255),
        state INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE message (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role VARCHAR(20) NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE captcha (
        id VARCHAR(64) PRIMARY KEY,
        code_hash VARCHAR(64) NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        memory_type VARCHAR(50) NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        content TEXT NOT NULL,
        source_conversation_id INTEGER,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


@pytest.fixture()
def engine(tmp_path) -> Iterator[Engine]:
    """每个测试一个独立的 SQLite 文件库，避免共享内存连接的并发问题。"""
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    with engine.begin() as conn:
        for statement in TEST_DDL:
            conn.execute(text(statement))

    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture()
def db(session_factory) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture()
def user(db: Session) -> User:
    user = User(
        username="tester",
        password_hash=hash_password("test123456"),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@pytest.fixture()
def other_user(db: Session) -> User:
    user = User(
        username="other",
        password_hash=hash_password("test123456"),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _auth_headers_for(user: User) -> dict[str, str]:
    token = create_access_token(
        TokenPayload(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers(user: User) -> dict[str, str]:
    return _auth_headers_for(user)


@pytest.fixture()
def other_auth_headers(other_user: User) -> dict[str, str]:
    return _auth_headers_for(other_user)


@pytest.fixture()
def conversation(db: Session, user: User) -> Conversation:
    conversation = Conversation(
        user_id=user.id,
        title="测试会话",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


@pytest.fixture()
def issue_captcha(session_factory):
    """用独立会话签发验证码，并返回明文 code 供测试使用。"""

    def _issue():
        from backend.app.service.captchaService import CaptchaService

        with session_factory() as session:
            return CaptchaService.generate(db=session)

    return _issue


@pytest.fixture()
def issued_captcha(issue_captcha):
    return issue_captcha()


@pytest.fixture()
def app(session_factory, monkeypatch) -> Iterator[FastAPI]:
    import backend.agent.tools.retrieval as retrieval_tool
    import backend.app.service.chatService as chat_service
    import backend.app.service.memoryService as memory_service

    from backend.app.database.database import get_db
    from backend.app.main import app as fastapi_app

    def override_get_db():
        with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # 流式聊天 / 记忆 / 检索工具内部使用 SessionLocal，测试统一指向 SQLite
    monkeypatch.setattr(chat_service, "SessionLocal", session_factory)
    monkeypatch.setattr(memory_service, "SessionLocal", session_factory)
    monkeypatch.setattr(retrieval_tool, "SessionLocal", session_factory)

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
