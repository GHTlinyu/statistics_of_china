# 04 交付：通用响应结构

- 功能 slug：`api-response`
- 日期：2026-10-26
- 状态：已交付并验证

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `app/schema/responseDTO.py` | 新增：泛型 `ApiResponse[T]`（code/message/data）+ `ok()`/`error()` 辅助方法 |
| `app/main.py` | 注册全局异常处理器（仅业务代码抛出的 `HTTPException`）；`/health` 改用统一结构 |
| `app/controller/userController.py` | `GET /user/{id}` 返回 `ApiResponse[UserDTO]` |
| `app/controller/authController.py` | register/login/me 三个接口返回 `ApiResponse[...]` |

## 统一范围（变更后）

- **业务代码**抛出的 `HTTPException`（401/404/409 等，来自 controller/service/鉴权依赖）→ 统一 `ApiResponse` 结构。
- **框架层**异常（未匹配路径 404、405、请求参数校验 422）→ FastAPI 默认格式（`{"detail": ...}`），不注册额外处理器。

注：FastAPI 0.141 存在两个 `HTTPException` 类（业务代码抛 `fastapi.exceptions.HTTPException`，路由层抛 `starlette.exceptions.HTTPException`）。当前只注册业务类的处理器，路由层异常自然保持默认格式，符合"仅业务代码统一"的约定。

## 验证结果（实测）

| 场景 | 响应 |
| --- | --- |
| `GET /health` | 200 `{"code":200,"message":"success","data":{"status":"ok"}}` ✅ |
| `POST /auth/register` 新用户 | 201 `data` 为 `UserDTO` ✅ |
| `POST /auth/register` 重复 | 409 统一格式 ✅ |
| `POST /auth/login` | 200 `data` 含 `access_token` ✅ |
| `GET /auth/me` 带 token | 200 `data` 为当前用户 ✅ |
| `GET /user/{id}` 带 token | 200 `data` 为 `UserDTO` ✅ |
| 无 token 访问受保护接口 | 401 统一格式 ✅ |
| 资源不存在（业务 404） | 404 统一格式 ✅ |
| 未匹配路径 | 404 FastAPI 默认格式 ✅ |
| 方法不允许（DELETE /health） | 405 FastAPI 默认格式 ✅ |
| 参数校验失败 | 422 FastAPI 默认格式 ✅ |

## 已知风险提示

FastAPI 默认 422 校验错误会回显用户输入（如密码过短时，`input` 字段会包含原始密码明文）。如后续需要，可在 `app/main.py` 为 `RequestValidationError` 注册一个剔除 `input` 字段的处理器。
