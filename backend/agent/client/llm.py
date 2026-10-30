"""大模型客户端：对项目提供统一的调用入口。

底层是 LangChain 的 `ChatOpenAI`（OpenAI 兼容协议），因此只要服务实现了
OpenAI 兼容接口（DeepSeek、通义千问、Kimi、自建 vLLM / Ollama 网关等），
改 `.env` 里的 `LLM_BASE_URL` / `LLM_MODEL` 即可切换，业务代码不变。

    from backend.agent.client import get_llm

    llm = get_llm()

    llm.chat("北京有多少个区？")                 # 同步，返回纯文本
    await llm.achat("...")                        # 异步
    for piece in llm.stream("..."):               # 同步流式
        print(piece, end="")
    async for piece in llm.astream("..."):        # 异步流式
        ...
    llm.chat_json("...")                          # JSON 模式，返回 dict
    llm.bind_tools([...])                         # 工具调用
    llm.model                                     # 原始 ChatOpenAI，供 LangGraph 直接使用

中断（停止生成）：

    token = InterruptToken()
    async for piece in llm.astream("...", interrupt=token):
        ...
        if 前端点了停止:
            token.stop()        # 下一分片到达时停止输出并关闭底层连接

需要立刻中止「还在等首个分片」的请求，可取消所在的 asyncio 任务
（token 只能阻止后续分片的消费，无法打断阻塞中的网络等待）。
"""

import json
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import suppress
from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

from backend.agent.client.config import LLMConfig, load_llm_config
from backend.agent.client.exceptions import LLMResponseError


class InterruptToken:
    """停止信号。

    在任意线程/协程里调用 `stop()`，流式接口会在下一个分片处停止并关闭连接。
    适合「前端点停止」或「用户发新消息，取消上一次生成」。
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def stop(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def is_set(self) -> bool:
        return self._event.is_set()

    @property
    def stopped(self) -> bool:
        return self._event.is_set()


def _extract_text(message: Any) -> str:
    """从消息/分片中取文本，兼容字符串内容与内容块列表。"""
    content = getattr(message, "content", message)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


def _parse_json(text: str) -> dict[str, Any]:
    """解析 JSON 响应，容忍模型用 ```json 代码块包裹。"""
    payload = text.strip()
    if payload.startswith("```"):
        payload = payload[3:]
        if payload.lstrip().lower().startswith("json"):
            payload = payload.lstrip()[4:]
        if payload.rstrip().endswith("```"):
            payload = payload.rstrip()[:-3]
        payload = payload.strip()

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LLMResponseError(f"模型返回内容不是合法 JSON：{text[:200]!r}") from exc

    if not isinstance(data, dict):
        raise LLMResponseError("模型返回的 JSON 顶层不是对象")
    return data


def _create_model(config: LLMConfig) -> ChatOpenAI:
    params: dict[str, Any] = {
        "model": config.model,
        "api_key": config.api_key,
        "temperature": config.temperature,
    }
    if config.base_url:
        params["base_url"] = config.base_url
    if config.timeout is not None:
        params["timeout"] = config.timeout
    if config.max_retries is not None:
        params["max_retries"] = config.max_retries
    return ChatOpenAI(**params)


class LLMClient:
    """统一的大模型调用入口。

    `model` 参数仅用于测试注入（可传入任意实现了 stream/astream/invoke 的对象）。
    """

    def __init__(self, model: Any | None = None) -> None:
        self._config: LLMConfig | None = None
        if model is not None:
            self._model = model
            return

        config = load_llm_config()
        self._config = config
        self._model = _create_model(config)

    @property
    def model(self) -> ChatOpenAI:
        """底层 ChatOpenAI，可直接交给 LangGraph 或做更细粒度的调用。"""
        return self._model

    @property
    def config(self) -> LLMConfig | None:
        """当前连接配置；测试注入模型时为 None。"""
        return self._config

    # ---------- 同步 ----------

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        """同步调用，返回原始 AIMessage（含 tool_calls、usage 等）。"""
        return self._model.invoke(messages, **kwargs)

    def chat(self, messages: Any, **kwargs: Any) -> str:
        """同步调用，只返回文本。"""
        return _extract_text(self.invoke(messages, **kwargs))

    def chat_json(
        self,
        messages: Any,
        *,
        schema: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """同步 JSON 调用。

        schema 为空时走 `response_format={"type": "json_object"}` 并解析文本；
        传入 Pydantic 模型时走 `with_structured_output`，返回 `model_dump()`。
        """
        if schema is not None:
            runner = self._model.with_structured_output(schema)
            result = runner.invoke(messages, **kwargs)
            if hasattr(result, "model_dump"):
                return result.model_dump()
            return dict(result)

        kwargs.setdefault("response_format", {"type": "json_object"})
        return _parse_json(self.chat(messages, **kwargs))

    def stream(
        self,
        messages: Any,
        *,
        interrupt: InterruptToken | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """同步流式输出，逐分片返回文本；`interrupt` 置位后停止并关闭连接。"""
        if interrupt is not None and interrupt.is_set():
            return

        source = self._model.stream(messages, **kwargs)
        try:
            for chunk in source:
                if interrupt is not None and interrupt.is_set():
                    break
                text = _extract_text(chunk)
                if text:
                    yield text
        finally:
            close = getattr(source, "close", None)
            if callable(close):
                with suppress(Exception):
                    close()

    # ---------- 异步 ----------

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        """异步调用，返回原始 AIMessage。"""
        return await self._model.ainvoke(messages, **kwargs)

    async def achat(self, messages: Any, **kwargs: Any) -> str:
        """异步调用，只返回文本。"""
        return _extract_text(await self.ainvoke(messages, **kwargs))

    async def achat_json(
        self,
        messages: Any,
        *,
        schema: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """异步 JSON 调用，语义同 `chat_json`。"""
        if schema is not None:
            runner = self._model.with_structured_output(schema)
            result = await runner.ainvoke(messages, **kwargs)
            if hasattr(result, "model_dump"):
                return result.model_dump()
            return dict(result)

        kwargs.setdefault("response_format", {"type": "json_object"})
        return _parse_json(await self.achat(messages, **kwargs))

    async def astream(
        self,
        messages: Any,
        *,
        interrupt: InterruptToken | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """异步流式输出，逐分片返回文本；`interrupt` 置位后停止并关闭连接。"""
        if interrupt is not None and interrupt.is_set():
            return

        source = self._model.astream(messages, **kwargs)
        try:
            async for chunk in source:
                if interrupt is not None and interrupt.is_set():
                    break
                text = _extract_text(chunk)
                if text:
                    yield text
        finally:
            aclose = getattr(source, "aclose", None)
            if callable(aclose):
                with suppress(Exception):
                    await aclose()

    # ---------- 高级能力透传 ----------

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        """绑定工具（供 LangGraph / 手工工具循环使用）。"""
        return self._model.bind_tools(tools, **kwargs)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        """结构化输出（Pydantic 模型等）。"""
        return self._model.with_structured_output(schema, **kwargs)


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    """获取进程内共享的客户端（单例），避免每次请求重复建连。"""
    return LLMClient()


def reset_llm() -> None:
    """清空单例缓存，下次调用重新读取环境变量。

    注意：`.env` 在模块导入时加载，修改 `.env` 后仍需重启进程才能生效；
    本函数用于程序内动态修改环境变量的场景（如测试）。
    """
    get_llm.cache_clear()
