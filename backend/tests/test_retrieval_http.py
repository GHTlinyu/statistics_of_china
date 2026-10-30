"""外部接口 POST 封装：重试、退避与非 JSON 响应。"""

import json
from types import SimpleNamespace

import httpx
import pytest

import backend.app.retrieval.http as http_module


class DummyError(RuntimeError):
    pass


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeClient:
    responses = []
    calls = []
    last_headers = None

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, **kwargs):
        FakeClient.calls.append(url)
        FakeClient.last_headers = kwargs["headers"]
        response = FakeClient.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture(autouse=True)
def patch_http(monkeypatch):
    FakeClient.responses = []
    FakeClient.calls = []
    FakeClient.last_headers = None
    monkeypatch.setattr(
        http_module,
        "httpx",
        SimpleNamespace(
            Client=FakeClient,
            RequestError=httpx.RequestError,
        ),
    )
    sleeps = []
    monkeypatch.setattr(http_module.time, "sleep", sleeps.append)

    return sleeps


def _post_json(**overrides):
    params = {
        "url": "http://example.test/api",
        "payload": {"a": 1},
        "api_key": "test-key",
        "timeout": 5.0,
        "max_retries": 2,
        "error_type": DummyError,
    }
    params.update(overrides)

    return http_module.post_json(**params)


def test_success_and_headers(patch_http):
    FakeClient.responses = [FakeResponse(200, {"ok": True})]

    result = _post_json()

    assert result == {"ok": True}
    assert FakeClient.last_headers == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }


def test_non_retryable_status_raises_immediately(patch_http):
    FakeClient.responses = [FakeResponse(400, text="bad request")]

    with pytest.raises(DummyError) as exc_info:
        _post_json()

    assert "400" in str(exc_info.value)
    assert FakeClient.calls == ["http://example.test/api"]


def test_retryable_status_is_retried(patch_http):
    FakeClient.responses = [FakeResponse(500, text="oops"), FakeResponse(200, {"ok": True})]

    result = _post_json()

    assert result == {"ok": True}
    assert len(FakeClient.calls) == 2
    assert patch_http == [0.5]


def test_retries_are_exhausted(patch_http):
    FakeClient.responses = [
        FakeResponse(500, text="oops"),
        FakeResponse(502, text="oops"),
        FakeResponse(503, text="oops"),
    ]

    with pytest.raises(DummyError):
        _post_json()

    assert len(FakeClient.calls) == 3
    assert patch_http == [0.5, 1.0]


def test_network_error_is_retried(patch_http):
    FakeClient.responses = [
        httpx.ConnectError("boom"),
        FakeResponse(200, {"ok": True}),
    ]

    result = _post_json()

    assert result == {"ok": True}
    assert len(FakeClient.calls) == 2


def test_all_network_errors_raise(patch_http):
    FakeClient.responses = [
        httpx.ConnectError("boom"),
        httpx.ConnectError("boom"),
        httpx.ConnectError("boom"),
    ]

    with pytest.raises(DummyError) as exc_info:
        _post_json()

    assert "请求" in str(exc_info.value)


def test_invalid_json_raises_error_type(patch_http):
    FakeClient.responses = [
        FakeResponse(200, json.JSONDecodeError("bad", "", 0)),
    ]

    with pytest.raises(DummyError):
        _post_json()
