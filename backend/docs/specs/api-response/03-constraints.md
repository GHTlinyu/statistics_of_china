# 03 开发约束：通用响应结构

- 功能 slug：`api-response`
- 日期：2026-10-26

## 代码约束

- Schema 统一放在 `app/schema/responseDTO.py`，类名 `ApiResponse`（与现有 `userDTO.py`/`authDTO.py` 命名风格一致）。
- 成功响应一律通过 `ApiResponse.ok(...)` 构造，不手写 dict。
- 控制器声明 `response_model=ApiResponse[XxxDTO]`，返回 `ApiResponse` 实例；业务逻辑层（service/mapper）不感知响应包装，仍返回领域对象。
- 业务代码的错误一律通过抛 `HTTPException` 产生，由全局异常处理器统一为 `ApiResponse` 格式，**不在业务代码里手写错误响应体**。
- 框架层异常（未匹配路径 404、405、参数校验 422）保持 FastAPI 默认格式，**不**注册额外处理器。
- 成功 body `code` 恒 200；业务错误 body `code` = HTTP 状态码。
- 新增接口默认使用统一结构；例外场景须在接口文档注明（见 02-design 的界定）。

## 兼容性约束

- 依赖 FastAPI 与 Pydantic v2 的泛型 `response_model` 能力，不新增任何第三方包。
- 异常处理器不改变 HTTP 状态码与安全响应头（`WWW-Authenticate` 等必须保留）。
