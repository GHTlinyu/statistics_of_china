"""消息数据访问：分页、最近消息、最近用户消息与删除。"""

from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.message import Message


def _create(db, conversation_id, role, content):
    return MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        ),
    )


def test_list_by_conversation_paginates_in_ascending_order(db, conversation):
    first = _create(db, conversation.id, "user", "first")
    second = _create(db, conversation.id, "assistant", "second")
    third = _create(db, conversation.id, "user", "third")

    page_one, total = MessageMapper.list_by_conversation(
        db=db,
        conversation_id=conversation.id,
        page=1,
        page_size=2,
    )
    page_two, _ = MessageMapper.list_by_conversation(
        db=db,
        conversation_id=conversation.id,
        page=2,
        page_size=2,
    )

    assert total == 3
    assert [message.id for message in page_one] == [first.id, second.id]
    assert [message.id for message in page_two] == [third.id]


def test_find_recent_returns_ascending_order(db, conversation):
    _create(db, conversation.id, "user", "first")
    second = _create(db, conversation.id, "assistant", "second")
    third = _create(db, conversation.id, "user", "third")

    recent = MessageMapper.find_recent_by_conversation(
        db=db,
        conversation_id=conversation.id,
        limit=2,
    )

    assert [message.id for message in recent] == [second.id, third.id]


def test_find_recent_user_messages_only_users(db, conversation):
    _create(db, conversation.id, "user", "u1")
    _create(db, conversation.id, "assistant", "a1")
    second_user = _create(db, conversation.id, "user", "u2")
    third_user = _create(db, conversation.id, "user", "u3")

    recent = MessageMapper.find_recent_user_messages(
        db=db,
        conversation_id=conversation.id,
        limit=2,
    )

    assert [message.id for message in recent] == [
        second_user.id,
        third_user.id,
    ]


def test_find_and_delete_by_id(db, conversation):
    message = _create(db, conversation.id, "user", "hello")

    found = MessageMapper.find_by_id(db=db, message_id=message.id)
    assert found is not None
    assert found.content == "hello"

    MessageMapper.delete_by_id(db=db, message_id=message.id)

    assert MessageMapper.find_by_id(db=db, message_id=message.id) is None
