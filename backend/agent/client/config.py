"""大模型配置：从仓库根目录的 `.env` 读取。

只用 `load_dotenv()` + `os.getenv()`，不依赖 pydantic-settings，也不碰
`backend/app/database/config.py`（那个文件只负责数据库与 JWT）。

`.env` 固定在仓库根目录（本文件在 `backend/agent/client/config.py`，
向上三层即仓库根），所以无论从哪个目录启动都能读到。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

from backend.agent.client.exceptions import LLMConfigurationError

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"

# 已存在的进程环境变量优先，不会被 .env 覆盖
load_dotenv(ENV_FILE)

DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_RETRIES = 2


@dataclass(frozen=True)
class LLMConfig:
    """一次大模型调用的连接参数。"""

    model: str
    api_key: str
    base_url: str | None
    temperature: float
    timeout: float | None
    max_retries: int


def _read_text(key: str) -> str | None:
    value = os.getenv(key)
    value = value.strip() if value else ""
    return value or None


def _read_float(key: str) -> float | None:
    value = _read_text(key)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise LLMConfigurationError(f"{key} 必须是数字，当前值：{value}") from exc


def _read_int(key: str) -> int | None:
    value = _read_text(key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise LLMConfigurationError(f"{key} 必须是整数，当前值：{value}") from exc


def load_llm_config() -> LLMConfig:
    """读取并校验大模型配置，缺必填项时一次性报出所有缺失项。"""
    model = _read_text("LLM_MODEL")
    api_key = _read_text("LLM_API_KEY")

    missing = [
        name
        for name, value in (("LLM_MODEL", model), ("LLM_API_KEY", api_key))
        if value is None
    ]
    if missing:
        raise LLMConfigurationError(
            "缺少大模型配置：" + "、".join(missing) + "，请在仓库根目录的 .env 中填写"
        )

    temperature = _read_float("LLM_TEMPERATURE")
    max_retries = _read_int("LLM_MAX_RETRIES")

    return LLMConfig(
        model=cast(str, model),
        api_key=cast(str, api_key),
        base_url=_read_text("LLM_BASE_URL"),
        temperature=DEFAULT_TEMPERATURE if temperature is None else temperature,
        timeout=_read_float("LLM_TIMEOUT_SECONDS"),
        max_retries=DEFAULT_MAX_RETRIES if max_retries is None else max_retries,
    )
