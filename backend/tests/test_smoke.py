"""测试底座冒烟：应用可启动、公开接口可用。"""


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 200,
        "message": "success",
        "data": {"status": "ok"},
    }


def test_captcha_is_public(client):
    response = client.get("/auth/captcha")

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"captcha_id", "image", "expires_in"}
    assert data["image"].startswith("data:image/png;base64,")


def test_protected_endpoint_requires_token(client):
    response = client.get("/conversation")

    assert response.status_code == 401
