"""Pydantic DTO：响应结构、分页与参数校验。"""

import pytest
from pydantic import ValidationError

from backend.app.schema.authDTO import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from backend.app.schema.captchaDTO import CaptchaDTO
from backend.app.schema.chatDTO import ChatRequest
from backend.app.schema.messageDTO import CreateMessageRequest
from backend.app.schema.pageDTO import PageResult
from backend.app.schema.responseDTO import ApiResponse


def test_api_response_helpers():
    ok = ApiResponse.ok({"x": 1})
    assert ok.model_dump() == {
        "code": 200,
        "message": "success",
        "data": {"x": 1},
    }

    error = ApiResponse.error(400, "bad")
    assert error.model_dump() == {
        "code": 400,
        "message": "bad",
        "data": None,
    }


def test_page_result():
    page = PageResult[int](items=[1, 2], total=2, page=1, page_size=10)

    assert page.items == [1, 2]
    assert page.total == 2
    assert page.page == 1
    assert page.page_size == 10


def test_login_request_requires_captcha_fields():
    with pytest.raises(ValidationError):
        LoginRequest(username="alice", password="secret")

    request = LoginRequest(
        username="alice",
        password="secret",
        captcha_id="id",
        captcha_code="ABCD",
    )
    assert request.captcha_code == "ABCD"


def test_register_request_validates_lengths():
    with pytest.raises(ValidationError):
        RegisterRequest(
            username="ab",
            password="secret",
            captcha_id="id",
            captcha_code="ABCD",
        )

    with pytest.raises(ValidationError):
        RegisterRequest(
            username="alice",
            password="12345",
            captcha_id="id",
            captcha_code="ABCD",
        )

    valid = RegisterRequest(
        username="alice",
        password="secret",
        captcha_id="id",
        captcha_code="ABCD",
    )
    assert valid.username == "alice"


def test_captcha_dto():
    dto = CaptchaDTO(
        captcha_id="id",
        image="data:image/png;base64,x",
        expires_in=300,
    )

    assert dto.expires_in == 300


def test_chat_request_limits():
    with pytest.raises(ValidationError):
        ChatRequest(content="")

    with pytest.raises(ValidationError):
        ChatRequest(content="x" * 4001)

    assert ChatRequest(content="hello").content == "hello"


def test_create_message_role_pattern():
    with pytest.raises(ValidationError):
        CreateMessageRequest(role="admin", content="x")

    assert CreateMessageRequest(role="user", content="x").role == "user"


def test_token_response_defaults():
    response = TokenResponse(access_token="token", expires_in=60)

    assert response.token_type == "bearer"
