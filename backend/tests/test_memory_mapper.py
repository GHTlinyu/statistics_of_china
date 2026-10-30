"""长期记忆数据访问：排序、归属、计数、最旧与更新。"""

from datetime import datetime, timezone

from backend.app.mapper.memoryMapper import MemoryMapper
from backend.app.model.memory import Memory


def _create(db, user_id, memory_type="user", title="标题", content="内容"):
    return MemoryMapper.create(
        db=db,
        memory=Memory(
            user_id=user_id,
            memory_type=memory_type,
            title=title,
            description="描述",
            content=content,
        ),
    )


def test_list_by_user_orders_by_updated_at_desc(db, user, other_user):
    first = _create(db, user.id, title="first")
    second = _create(db, user.id, title="second")
    _create(db, other_user.id, title="other")

    items = MemoryMapper.list_by_user(db=db, user_id=user.id)

    assert [memory.id for memory in items] == [second.id, first.id]


def test_list_by_user_respects_limit(db, user):
    _create(db, user.id, title="first")
    second = _create(db, user.id, title="second")

    items = MemoryMapper.list_by_user(db=db, user_id=user.id, limit=1)

    assert [memory.id for memory in items] == [second.id]


def test_list_by_user_and_type_is_oldest_first(db, user):
    user_first = _create(db, user.id, memory_type="user", title="u1")
    _create(db, user.id, memory_type="feedback", title="f1")
    user_second = _create(db, user.id, memory_type="user", title="u2")

    items = MemoryMapper.list_by_user_and_type(
        db=db,
        user_id=user.id,
        memory_type="user",
    )

    assert [memory.id for memory in items] == [
        user_first.id,
        user_second.id,
    ]


def test_find_by_ids_filters_ownership(db, user, other_user):
    own = _create(db, user.id)
    foreign = _create(db, other_user.id)

    items = MemoryMapper.find_by_ids(
        db=db,
        user_id=user.id,
        memory_ids=[own.id, foreign.id],
    )

    assert [memory.id for memory in items] == [own.id]
    assert (
        MemoryMapper.find_by_ids(
            db=db,
            user_id=user.id,
            memory_ids=[],
        )
        == []
    )


def test_find_by_id_filters_ownership(db, user, other_user):
    own = _create(db, user.id)
    foreign = _create(db, other_user.id)

    assert (
        MemoryMapper.find_by_id(
            db=db,
            user_id=user.id,
            memory_id=own.id,
        ).id
        == own.id
    )
    assert (
        MemoryMapper.find_by_id(
            db=db,
            user_id=user.id,
            memory_id=foreign.id,
        )
        is None
    )


def test_count_and_find_oldest(db, user, other_user):
    first = _create(db, user.id, memory_type="user", title="u1")
    second = _create(db, user.id, memory_type="feedback", title="f1")
    _create(db, other_user.id)

    assert MemoryMapper.count_by_user(db=db, user_id=user.id) == 2
    assert (
        MemoryMapper.find_oldest(db=db, user_id=user.id).id
        == first.id
    )
    assert (
        MemoryMapper.find_oldest(
            db=db,
            user_id=user.id,
            memory_type="feedback",
        ).id
        == second.id
    )
    assert (
        MemoryMapper.find_oldest(
            db=db,
            user_id=user.id,
            memory_type="missing",
        )
        is None
    )


def test_update_fields_checks_ownership_and_updates(db, user, other_user):
    own = _create(db, user.id, content="old")
    foreign = _create(db, other_user.id, content="foreign")

    MemoryMapper.update_fields(
        db=db,
        user_id=user.id,
        memory_id=own.id,
        memory_type="feedback",
        title="new",
        description="new desc",
        content="new content",
    )
    MemoryMapper.update_fields(
        db=db,
        user_id=user.id,
        memory_id=foreign.id,
        memory_type="feedback",
        title="hijack",
        description="hijack",
        content="hijack",
    )

    db.expire_all()
    own_row = db.get(Memory, own.id)
    foreign_row = db.get(Memory, foreign.id)

    assert own_row.title == "new"
    assert own_row.memory_type == "feedback"
    assert own_row.description == "new desc"
    assert own_row.content == "new content"
    assert own_row.updated_at is not None
    assert foreign_row.title == "标题"
    assert foreign_row.content == "foreign"
