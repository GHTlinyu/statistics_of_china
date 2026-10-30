"""会话接口：创建、列表、详情、删除、消息分页与越权。"""

from backend.app.mapper.messageMapper import MessageMapper
from backend.app.model.message import Message
from backend.app.service.conversationService import ConversationService


def test_create_conversation(client, auth_headers, user):
    response = client.post(
        "/conversation",
        json={"title": "新会话"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "新会话"
    assert data["user_id"] == user.id
    assert data["state"] == 1


def test_create_conversation_without_title(client, auth_headers):
    response = client.post(
        "/conversation",
        json={},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"]["title"] is None


def test_list_conversations_returns_newest_first(client, auth_headers):
    first = client.post(
        "/conversation",
        json={"title": "first"},
        headers=auth_headers,
    ).json()["data"]
    second = client.post(
        "/conversation",
        json={"title": "second"},
        headers=auth_headers,
    ).json()["data"]

    response = client.get("/conversation", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    assert [item["id"] for item in data["items"]] == [second["id"], first["id"]]


def test_get_own_and_foreign_conversation(
    client,
    db,
    auth_headers,
    other_auth_headers,
    user,
    other_user,
    conversation,
):
    own = client.get(
        f"/conversation/{conversation.id}",
        headers=auth_headers,
    )
    assert own.status_code == 200
    assert own.json()["data"]["id"] == conversation.id

    foreign = ConversationService.create_conversation(
        db=db,
        user_id=other_user.id,
        title="other",
    )

    denied = client.get(
        f"/conversation/{foreign.id}",
        headers=auth_headers,
    )
    allowed = client.get(
        f"/conversation/{foreign.id}",
        headers=other_auth_headers,
    )

    assert denied.status_code == 404
    assert allowed.status_code == 200


def test_delete_conversation(client, auth_headers, conversation):
    response = client.delete(
        f"/conversation/{conversation.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    assert (
        client.get(
            f"/conversation/{conversation.id}",
            headers=auth_headers,
        ).status_code
        == 404
    )
    assert client.get(
        "/conversation", headers=auth_headers
    ).json()["data"]["total"] == 0
    assert (
        client.delete(
            f"/conversation/{conversation.id}",
            headers=auth_headers,
        ).status_code
        == 404
    )


def test_list_messages_paginates(
    client,
    db,
    auth_headers,
    conversation,
):
    first = MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="user",
            content="first",
        ),
    )
    second = MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="assistant",
            content="second",
        ),
    )
    third = MessageMapper.create(
        db=db,
        message=Message(
            conversation_id=conversation.id,
            role="user",
            content="third",
        ),
    )

    page_one = client.get(
        f"/conversation/{conversation.id}/messages",
        params={"page": 1, "page_size": 2},
        headers=auth_headers,
    )
    page_two = client.get(
        f"/conversation/{conversation.id}/messages",
        params={"page": 2, "page_size": 2},
        headers=auth_headers,
    )

    assert page_one.status_code == 200
    assert page_one.json()["data"]["total"] == 3
    assert [item["id"] for item in page_one.json()["data"]["items"]] == [
        first.id,
        second.id,
    ]
    assert [item["id"] for item in page_two.json()["data"]["items"]] == [
        third.id,
    ]


def test_pagination_validation(client, auth_headers, conversation):
    assert (
        client.get(
            "/conversation",
            params={"page": 0},
            headers=auth_headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/conversation",
            params={"page_size": 101},
            headers=auth_headers,
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/conversation/{conversation.id}/messages",
            params={"page_size": 101},
            headers=auth_headers,
        ).status_code
        == 422
    )


def test_messages_of_foreign_conversation_returns_404(
    client,
    db,
    auth_headers,
    other_user,
):
    foreign = ConversationService.create_conversation(
        db=db,
        user_id=other_user.id,
        title="other",
    )

    response = client.get(
        f"/conversation/{foreign.id}/messages",
        headers=auth_headers,
    )

    assert response.status_code == 404
