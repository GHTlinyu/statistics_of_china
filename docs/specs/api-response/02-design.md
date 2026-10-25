# 02 设计：通用响应结构

- 功能 slug：`api-response`
- 日期：2026-10-26

## 核心 Schema

新增 `app/schema/responseDTO.py`：

```python
class ApiResponse(BaseModel, Generic[T]):
    code: int = 200          # 业务码：成功恒 200；错误时为对应 HTTP 状态码
    message: str = "success"
    data: T | None = None

    @classmethod
    def ok(cls, data=None, message="success") -> "ApiResponse[Any]"
    @classmethod
    def error(cls, code, message) -> "ApiResponse[None]"
```

- 使用泛型 `Generic[T]`，各接口声明 `response_model=ApiResponse[UserDTO]` 等，`data` 字段获得准确的类型校验与 OpenAPI 文档。
- 成功响应 body 中 `code` 恒为 200（业务成功语义），HTTP 状态码保留原有语义（如注册仍为 201 Created）。

## 异常统一（仅业务代码）

在 `app/main.py` 注册全局异常处理器：

| 异常 | 输出 |
| --- | --- |
| 业务代码抛出的 `HTTPException` | HTTP 状态码不变；body `{"code": <status>, "message": <detail>, "data": null}`；保留原响应头（如 `WWW-Authenticate`） |
| 框架层异常（未匹配路径 404、405、参数校验 422） | 保持 FastAPI 默认格式（`{"detail": ...}`），不做统一 |

鉴权依赖抛出的 401 自动被 `HTTPException` 处理器统一，无需改动 `app/security/deps.py`。

## 改造范围

| 接口 | 原返回 | 新返回 |
| --- | --- | --- |
| `GET /health` | `{"status":"ok"}` | `data={"status":"ok"}` |
| `POST /auth/register` | `UserDTO` | `ApiResponse[UserDTO]` |
| `POST /auth/login` | `TokenResponse` | `ApiResponse[TokenResponse]` |
| `GET /auth/me` | `TokenPayload` | `ApiResponse[TokenPayload]` |
| `GET /user/{id}` | `UserDTO` | `ApiResponse[UserDTO]` |

## "特殊处理"的界定

以下场景可以例外（不套用统一结构），但必须在接口设计文档中注明理由：

- 与第三方系统兼容要求固定格式的回调/探针接口
- 文件下载、流式（SSE）响应
