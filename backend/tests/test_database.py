"""数据库会话依赖：yield 后关闭会话。"""

import pytest

import backend.app.database.database as database


def test_get_db_yields_and_closes(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    session = FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    generator = database.get_db()

    assert next(generator) is session
    assert session.closed is False

    with pytest.raises(StopIteration):
        next(generator)

    assert session.closed is True
