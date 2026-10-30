"""认证接口：验证码、登录、注册、token 流转。"""

import base64
import io

from PIL import Image

from backend.app.mapper.userMapper import UserMapper
from backend.app.model.captcha import Captcha


def _login_payload(captcha, username="tester", password="test123456"):
    return {
        "username": username,
        "password": password,
        "captcha_id": captcha.captcha_id,
        "captcha_code": captcha.code,
    }


def test_captcha_response_has_no_plaintext_code(client):
    response = client.get("/auth/captcha")

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"captcha_id", "image", "expires_in"}
    assert "code" not in data

    raw = base64.b64decode(data["image"].split(",", 1)[1])
    image = Image.open(io.BytesIO(raw))
    assert image.size == (160, 60)
    assert image.format == "PNG"


def test_login_requires_captcha_fields(client, user):
    response = client.post(
        "/auth/login",
        json={"username": "tester", "password": "test123456"},
    )

    assert response.status_code == 422


def test_login_rejects_wrong_captcha(client, user):
    response = client.post(
        "/auth/login",
        json={
            "username": "tester",
            "password": "test123456",
            "captcha_id": "missing",
            "captcha_code": "ABCD",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "验证码错误或已过期"


def test_login_success_then_me(client, user, issue_captcha, session_factory):
    captcha = issue_captcha()

    response = client.post("/auth/login", json=_login_payload(captcha))

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    assert token

    me = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["user_id"] == user.id
    assert me.json()["data"]["username"] == "tester"

    with session_factory() as db:
        assert db.get(Captcha, captcha.captcha_id) is None


def test_login_replay_rejected(client, user, issue_captcha):
    captcha = issue_captcha()
    payload = _login_payload(captcha)

    first = client.post("/auth/login", json=payload)
    second = client.post("/auth/login", json=payload)

    assert first.status_code == 200
    assert second.status_code == 400


def test_login_wrong_password(client, user, issue_captcha):
    captcha = issue_captcha()
    payload = _login_payload(captcha, password="wrong-password")

    response = client.post("/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "用户名或密码错误"
    assert response.headers["www-authenticate"] == "Bearer"


def test_register_requires_captcha_fields(client):
    response = client.post(
        "/auth/register",
        json={"username": "newuser", "password": "test123456"},
    )

    assert response.status_code == 422


def test_register_wrong_captcha_does_not_create_user(client, session_factory):
    response = client.post(
        "/auth/register",
        json={
            "username": "newuser",
            "password": "test123456",
            "captcha_id": "missing",
            "captcha_code": "ABCD",
        },
    )

    assert response.status_code == 400

    with session_factory() as db:
        assert UserMapper.find_by_username(db=db, username="newuser") is None


def test_register_success_then_login(client, issue_captcha, session_factory):
    register_captcha = issue_captcha()

    response = client.post(
        "/auth/register",
        json={
            "username": "newuser",
            "password": "test123456",
            "captcha_id": register_captcha.captcha_id,
            "captcha_code": register_captcha.code,
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["username"] == "newuser"

    with session_factory() as db:
        user = UserMapper.find_by_username(db=db, username="newuser")
        assert user is not None
        assert user.password_hash != "test123456"

    login_captcha = issue_captcha()
    login = client.post(
        "/auth/login",
        json=_login_payload(login_captcha, username="newuser"),
    )

    assert login.status_code == 200


def test_duplicate_register_returns_409(client, user, issue_captcha):
    captcha = issue_captcha()

    response = client.post(
        "/auth/register",
        json={
            "username": "tester",
            "password": "test123456",
            "captcha_id": captcha.captcha_id,
            "captcha_code": captcha.code,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "用户名已存在"


def test_protected_endpoint_with_token(client, user, issue_captcha):
    captcha = issue_captcha()
    login = client.post("/auth/login", json=_login_payload(captcha))
    token = login.json()["data"]["access_token"]

    response = client.get(
        "/conversation",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 0
