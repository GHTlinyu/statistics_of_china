"""消息服务：归属校验与删除约束。"""

import pytest
from fastapi import HTTPException

from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.message import Message
from backend.app.service.conversationService import ConversationService
from backend.app.service.messageService import MessageService


def _create_conversation(db, user_id):
    return ConversationService.create_conversation(
        db=db,
        user_id=user_id,
        title=None,
    )


def test_create_message_checks_ownership(db, user, other_user):
    conversation = _create_conversation(db, user.id)

    message = MessageService.create_message(
        db=db,
        conversation_id=conversation.id,
        user_id=user.id,
        role="user",
        content="hello",
    )

    assert message.id is not None
    assert message.conversation_id == conversation.id
    assert message.role == "user"

    with pytest.raises(HTTPException) as exc_info:
        MessageService.create_message(
            db=db,
            conversation_id=conversation.id,
            user_id=other_user.id,
            role="user",
            content="hijack",
        )
    assert exc_info.value.status_code == 404


def test_create_message_on_missing_conversation(db, user):
    with pytest.raises(HTTPException) as exc_info:
        MessageService.create_message(
            db=db,
            conversation_id=999_999,
            user_id=user.id,
            role="user",
            content="hello",
        )
    assert exc_info.value.status_code == 404


def test_delete_message_must_belong_to_conversation(db, user):
    conversation = _create_conversation(db, user.id)
    other_conversation = _create_conversation(db, user.id)
    message = MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="user",
            content="hello",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        MessageService.delete_message(
            db=db,
            conversation_id=other_conversation.id,
            message_id=message.id,
            user_id=user.id,
        )
    assert exc_info.value.status_code == 404

    assert MessageMapper.find_by_id(db=db, message_id=message.id) is not None

    MessageService.delete_message(
        db=db,
        conversation_id=conversation.id,
        message_id=message.id,
        user_id=user.id,
    )

    assert MessageMapper.find_by_id(db=db, message_id=message.id) is None


def test_delete_missing_message_returns_404(db, user):
    conversation = _create_conversation(db, user.id)

    with pytest.raises(HTTPException) as exc_info:
        MessageService.delete_message(
            db=db,
            conversation_id=conversation.id,
            message_id=999_999,
            user_id=user.id,
        )
    assert exc_info.value.status_code == 404
