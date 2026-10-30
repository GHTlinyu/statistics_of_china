# 03 开发约束：登录 / 注册验证码

- 功能 slug：`captcha`
- 日期：2026-10-30

## 分层与调用

- 沿用 controller → service → mapper → model 分层；controller 只做参数接收与错误转换。
- `CaptchaService` 通过 `CaptchaMapper` 访问数据库；验证码生成、摘要、图片渲染不放在 controller。
- 沿用 auth 模块的会话策略：通过 `get_db` 依赖注入 `Session`，不自行创建 `SessionLocal`。

## 安全约束

- 验证码必须先于用户名/密码校验执行；验证码失败时禁止查用户、校验密码或创建用户。
- 数据库只保存 `HMAC-SHA256(jwt_secret, code)` 摘要，禁止保存明文。
- 校验必须使用 `hmac.compare_digest`，不能直接 `==`。
- 验证码一次性：校验成功或失败都必须删除记录；删除与校验在同一事务内，使用 `SELECT ... FOR UPDATE` 防并发重放。
- 过期时间使用 UTC aware datetime；过期记录在校验时删除。
- 验证码明文不得出现在响应体、日志、异常信息中；`CaptchaDTO` 只有 `captcha_id`、`image`、`expires_in`。
- 字符生成使用 `secrets.choice`，禁止使用可预测的 `random`。

## 接口约束

- `GET /auth/captcha` 必须加入 `security/deps.py` 的 `PUBLIC_PATHS`，否则无法在登录前获取验证码。
- `LoginRequest` / `RegisterRequest` 的 `captcha_id` / `captcha_code` 为必填字段；缺失时由 Pydantic 返回 422。
- 验证码错误统一 400 + `detail="验证码错误或已过期"`，不区分不存在、过期、错误。
- 原有 401（凭据错误）与 409（用户名重复）语义不得改变。

## 图片约束

- 使用 `captcha.image.ImageCaptcha` 生成 160×60 PNG；字符集固定为 `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`，长度默认 4。
- 返回 `data:image/png;base64,...`，图片生成失败时向上抛出，由 FastAPI 返回 500，不得回退到明文验证码。
- 依赖 `captcha`（自动携带 Pillow）；不引入第三方在线验证服务。

## 配置与数据库

- `captcha_ttl_seconds`（默认 300）、`captcha_length`（默认 4）放在 `backend/app/core/config.py` 的 `Settings`，可通过 `.env` 覆盖。
- `captcha` 表由 `backend/app/database/init_db.py` 注册；新环境执行 `uv run python -m backend.app.database.init_db`。
- 每次签发新验证码时清理 `expires_at < now()` 的记录。

## 范围约束

- 本期不做登录失败限流 / 账户锁定、第三方人机验证、邮箱 / 短信验证码。
- 不新增注册页面；注册接口的调用方需自行获取并携带验证码。
- 登录 / 注册请求新增必填字段属于 API 契约变更，现有调用方必须同步更新。
