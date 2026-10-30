# 03 开发约束：认证与 Token 签发/校验

- 功能 slug：`auth-token`
- 日期：2026-10-26

## 分层与代码风格

- 沿用现有分层：controller（路由与参数校验）→ service（业务逻辑）→ mapper（数据访问），schema 层放 Pydantic DTO，ORM 模型与 DTO 分离。
- Python 3.12+，全部类型注解；SQLAlchemy 2.0 类型化写法（`Mapped` / `mapped_column`）。
- 数据库会话通过 `app.database.database.get_db` 依赖注入，不自行创建 session。
- 代码标识符英文，与用户交流中文。

## 安全约束

- `jwt_secret` 只从 `.env` 读取（经 `Settings`），**严禁**硬编码进代码、日志或提交到仓库。
- 密码明文**严禁**出现在日志、异常信息、响应体中；登录失败统一返回"用户名或密码错误"，不区分用户名不存在与密码错误。
- 认证失败统一 401 + `WWW-Authenticate: Bearer`；用户名重复返回 409。
- 登录 / 注册必须先校验一次性验证码，验证码失败返回 400，且不得继续查用户、校验密码或创建用户；验证码规则见 `backend/docs/specs/captcha/03-constraints.md`。
- `password_hash` 不出现在任何 API 响应中（DTO 不含该字段）。
- 鉴权依赖为全局依赖，新增接口默认受保护；公开接口必须显式加入 `PUBLIC_PATHS` 白名单。

## 依赖约束

- 使用 `uv` 管理依赖（`uv sync`），不直接使用 `pip`。
- 新增包：`pyjwt`、`pwdlib[argon2]`、`captcha`（验证码渲染，依赖 Pillow）；不引入 passlib（与 bcrypt 4.x 有已知兼容问题，且本功能未采用 bcrypt）。
- 版本锁定在 `pyproject.toml` 的 `[project].dependencies`，lockfile 由 `uv sync` 生成。
