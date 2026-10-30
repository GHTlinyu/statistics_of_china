"""会话服务：创建、归属校验、分页、软删除与消息归属。"""

import pytest
from fastapi import HTTPException

from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.conversation import STATE_DELETED, Conversation
from backend.app.model.message import Message
from backend.app.service.conversationService import ConversationService


def _create_conversation(db, user_id, title="测试会话"):
    return ConversationService.create_conversation(
        db=db,
        user_id=user_id,
        title=title,
    )


def test_create_and_get(db, user):
    created = _create_conversation(db, user.id, "我的会话")

    fetched = ConversationService.get_conversation(
        db=db,
        conversation_id=created.id,
        user_id=user.id,
    )

    assert fetched.id == created.id
    assert fetched.title == "我的会话"
    assert fetched.state == 1


def test_get_missing_or_foreign_returns_404(db, user, other_user):
    other_conversation = _create_conversation(db, other_user.id)

    with pytest.raises(HTTPException) as exc_info:
        ConversationService.get_conversation(
            db=db,
            conversation_id=other_conversation.id,
            user_id=user.id,
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        ConversationService.get_conversation(
            db=db,
            conversation_id=999_999,
            user_id=user.id,
        )
    assert exc_info.value.status_code == 404


def test_list_only_active_and_ordered(db, user):
    first = _create_conversation(db, user.id, "first")
    second = _create_conversation(db, user.id, "second")

    items, total = ConversationService.list_conversations(
        db=db,
        user_id=user.id,
        page=1,
        page_size=20,
    )

    assert total == 2
    assert [item.id for item in items] == [second.id, first.id]

    ConversationService.delete_conversation(
        db=db,
        conversation_id=first.id,
        user_id=user.id,
    )

    items, total = ConversationService.list_conversations(
        db=db,
        user_id=user.id,
        page=1,
        page_size=20,
    )

    assert total == 1
    assert items[0].id == second.id


def test_list_conversations_pagination(db, user):
    for index in range(3):
        _create_conversation(db, user.id, f"conversation-{index}")

    first_page, total = ConversationService.list_conversations(
        db=db,
        user_id=user.id,
        page=1,
        page_size=2,
    )
    second_page, _ = ConversationService.list_conversations(
        db=db,
        user_id=user.id,
        page=2,
        page_size=2,
    )

    assert total == 3
    assert len(first_page) == 2
    assert len(second_page) == 1


def test_list_messages_checks_conversation_ownership(db, user, other_user):
    conversation = _create_conversation(db, user.id)
    MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="user",
            content="hello",
        ),
    )

    items, total = ConversationService.list_messages(
        db=db,
        conversation_id=conversation.id,
        user_id=user.id,
        page=1,
        page_size=20,
    )

    assert total == 1
    assert items[0].content == "hello"

    with pytest.raises(HTTPException) as exc_info:
        ConversationService.list_messages(
            db=db,
            conversation_id=conversation.id,
            user_id=other_user.id,
            page=1,
            page_size=20,
        )
    assert exc_info.value.status_code == 404


def test_delete_conversation_soft_deletes(db, user):
    conversation = _create_conversation(db, user.id)

    ConversationService.delete_conversation(
        db=db,
        conversation_id=conversation.id,
        user_id=user.id,
    )

    with pytest.raises(HTTPException):
        ConversationService.get_conversation(
            db=db,
            conversation_id=conversation.id,
            user_id=user.id,
        )

    db.expire_all()
    row = db.get(Conversation, conversation.id)

    assert row is not None
    assert row.state == STATE_DELETED


def test_delete_missing_or_foreign_returns_404(db, user, other_user):
    other_conversation = _create_conversation(db, other_user.id)

    with pytest.raises(HTTPException) as exc_info:
        ConversationService.delete_conversation(
            db=db,
            conversation_id=other_conversation.id,
            user_id=user.id,
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException):
        ConversationService.delete_conversation(
            db=db,
            conversation_id=999_999,
            user_id=user.id,
        )
