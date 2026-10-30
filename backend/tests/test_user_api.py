"""用户接口与鉴权依赖：查询、404、非法 token 与公开文档。"""


def test_get_user(client, auth_headers, user):
    response = client.get(f"/user/{user.id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == user.id
    assert data["username"] == "tester"


def test_get_missing_user(client, auth_headers):
    response = client.get("/user/999999", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_invalid_token_returns_401(client, user):
    response = client.get(
        f"/user/{user.id}",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


def test_missing_token_returns_401(client, user):
    response = client.get(f"/user/{user.id}")

    assert response.status_code == 401


def test_docs_and_openapi_are_public(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
