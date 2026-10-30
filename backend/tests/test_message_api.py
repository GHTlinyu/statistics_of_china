"""消息接口：新增、删除、越权与非法参数。"""

from backend.app.service.conversationService import ConversationService


def _create_message(client, conversation_id, headers, content="hello"):
    return client.post(
        f"/conversation/{conversation_id}/messages",
        json={"role": "user", "content": content},
        headers=headers,
    )


def test_create_message(client, auth_headers, conversation):
    response = _create_message(
        client,
        conversation.id,
        auth_headers,
        "hello",
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["conversation_id"] == conversation.id
    assert data["role"] == "user"
    assert data["content"] == "hello"

    listing = client.get(
        f"/conversation/{conversation.id}/messages",
        headers=auth_headers,
    )
    assert listing.json()["data"]["total"] == 1


def test_create_message_rejects_invalid_role(client, auth_headers, conversation):
    response = client.post(
        f"/conversation/{conversation.id}/messages",
        json={"role": "admin", "content": "hello"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_message_on_foreign_conversation(
    client,
    db,
    other_auth_headers,
    conversation,
):
    response = _create_message(
        client,
        conversation.id,
        other_auth_headers,
    )

    assert response.status_code == 404


def test_delete_message(client, auth_headers, conversation):
    created = _create_message(
        client,
        conversation.id,
        auth_headers,
    ).json()["data"]

    response = client.delete(
        f"/conversation/{conversation.id}/messages/{created['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert client.get(
        f"/conversation/{conversation.id}/messages",
        headers=auth_headers,
    ).json()["data"]["total"] == 0
    assert (
        client.delete(
            f"/conversation/{conversation.id}/messages/{created['id']}",
            headers=auth_headers,
        ).status_code
        == 404
    )


def test_delete_message_with_wrong_conversation(
    client,
    db,
    auth_headers,
    user,
    conversation,
):
    created = _create_message(
        client,
        conversation.id,
        auth_headers,
    ).json()["data"]
    other_conversation = ConversationService.create_conversation(
        db=db,
        user_id=user.id,
        title="other",
    )

    response = client.delete(
        f"/conversation/{other_conversation.id}/messages/{created['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert client.get(
        f"/conversation/{conversation.id}/messages",
        headers=auth_headers,
    ).json()["data"]["total"] == 1


def test_delete_message_on_foreign_conversation(
    client,
    other_auth_headers,
    conversation,
):
    response = client.delete(
        f"/conversation/{conversation.id}/messages/1",
        headers=other_auth_headers,
    )

    assert response.status_code == 404
