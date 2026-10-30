"""会话数据访问：归属、分页、标题、活跃时间与软删除。"""

from datetime import datetime, timedelta, timezone

from backend.app.mapper.conversationMapper import ConversationMapper
from backend.app.model.conversation import STATE_DELETED


def test_create_and_find_by_id(db, user, other_user):
    conversation = ConversationMapper.create(
        db=db,
        user_id=user.id,
        title="我的会话",
    )

    found = ConversationMapper.find_by_id(
        db=db,
        conversation_id=conversation.id,
        user_id=user.id,
    )
    foreign = ConversationMapper.find_by_id(
        db=db,
        conversation_id=conversation.id,
        user_id=other_user.id,
    )

    assert found is not None
    assert found.id == conversation.id
    assert foreign is None


def test_list_by_user_excludes_deleted_and_paginates(db, user):
    first = ConversationMapper.create(db=db, user_id=user.id, title="first")
    second = ConversationMapper.create(db=db, user_id=user.id, title="second")

    ConversationMapper.soft_delete(
        db=db,
        conversation_id=first.id,
        user_id=user.id,
        state=STATE_DELETED,
    )

    items, total = ConversationMapper.list_by_user(
        db=db,
        user_id=user.id,
        page=1,
        page_size=20,
    )

    assert total == 1
    assert items[0].id == second.id

    empty_items, _ = ConversationMapper.list_by_user(
        db=db,
        user_id=user.id,
        page=2,
        page_size=20,
    )
    assert empty_items == []


def test_update_title(db, user):
    conversation = ConversationMapper.create(
        db=db,
        user_id=user.id,
        title=None,
    )

    ConversationMapper.update_title(
        db=db,
        conversation_id=conversation.id,
        title="新标题",
    )

    db.expire_all()
    row = db.get(type(conversation), conversation.id)

    assert row.title == "新标题"


def test_touch_refreshes_updated_at(db, user):
    conversation = ConversationMapper.create(
        db=db,
        user_id=user.id,
        title="t",
    )
    old_time = datetime.now(timezone.utc) - timedelta(days=1)
    conversation.updated_at = old_time
    db.commit()

    ConversationMapper.touch(db=db, conversation_id=conversation.id)

    db.expire_all()
    row = db.get(type(conversation), conversation.id)
    updated_at = row.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    assert updated_at > old_time


def test_soft_delete_returns_affected_rows(db, user, other_user):
    conversation = ConversationMapper.create(
        db=db,
        user_id=user.id,
        title="t",
    )

    foreign = ConversationMapper.soft_delete(
        db=db,
        conversation_id=conversation.id,
        user_id=other_user.id,
        state=STATE_DELETED,
    )
    first = ConversationMapper.soft_delete(
        db=db,
        conversation_id=conversation.id,
        user_id=user.id,
        state=STATE_DELETED,
    )
    second = ConversationMapper.soft_delete(
        db=db,
        conversation_id=conversation.id,
        user_id=user.id,
        state=STATE_DELETED,
    )

    assert foreign == 0
    assert first == 1
    assert second == 0
