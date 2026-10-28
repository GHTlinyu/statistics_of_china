"""外部模型接口的 JSON POST 封装：超时、有限重试、统一报错。"""

import json
import time
from typing import Any

import httpx

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
RETRY_BACKOFF_SECONDS = 0.5


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout: float,
    max_retries: int,
    error_type: type[Exception],
) -> dict[str, Any]:
    """POST JSON 并返回解析后的响应体。

    429 / 5xx 与网络错误按 `max_retries` 重试，其余 4xx 直接抛错。
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_error = f"请求 {url} 失败"

    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            last_error = f"请求 {url} 失败：{exc}"
        else:
            if response.status_code < 400:
                try:
                    return response.json()
                except json.JSONDecodeError as exc:
                    raise error_type(f"{url} 返回内容不是合法 JSON") from exc

            body = response.text[:300]
            last_error = f"{url} 返回 {response.status_code}：{body}"
            if response.status_code not in RETRYABLE_STATUS:
                raise error_type(last_error)

        if attempt < max_retries:
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

    raise error_type(last_error)
