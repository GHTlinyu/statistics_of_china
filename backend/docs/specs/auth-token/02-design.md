# 02 设计：认证与 Token 签发/校验

- 功能 slug：`auth-token`
- 日期：2026-10-26

## 模块结构（沿用现有分层）

```
app/
├── security/
│   ├── security.py        # 密码哈希（pwdlib/argon2）、JWT 签发与解析（PyJWT）
│   └── deps.py            # FastAPI 依赖：get_current_user（全局鉴权入口）
├── controller/
│   └── authController.py  # GET /auth/captcha、POST /auth/register、POST /auth/login、GET /auth/me
├── service/
│   ├── authService.py     # 注册、认证业务逻辑
│   └── captchaService.py  # 验证码生成、图片渲染与校验
├── schema/
│   ├── authDTO.py         # RegisterRequest / LoginRequest / TokenResponse / TokenPayload
│   └── captchaDTO.py      # CaptchaDTO
├── mapper/
│   ├── userMapper.py      # 新增 find_by_username、create
│   └── captchaMapper.py   # 验证码数据访问
└── model/
    └── captcha.py         # captcha 表
```

## 核心机制

### 1. 密码哈希（argon2 via pwdlib）

- `PasswordHash.recommended()`（argon2），注册时 `hash_password()` 后写入 `account.password_hash`（VARCHAR(255) 足够容纳 argon2 哈希串）。
- 登录时 `verify_password()`；对损坏哈希用 try/except 兜底返回 False。

### 2. JWT 签发与校验（PyJWT，HS256）

载荷：

```json
{
  "sub": "<user_id>",
  "username": "<username>",
  "role": "<role>",
  "iat": "<签发时间>",
  "exp": "<过期时间>"
}
```

- 签发：`jwt.encode(payload, settings.jwt_secret, algorithm="HS256")`
- 解析：`jwt.decode(token, secret, algorithms=["HS256"])`，捕获 `ExpiredSignatureError` / `InvalidTokenError` 统一转为 401。
- 简单版权衡：校验签名后**不查库**，直接信任载荷构造 `TokenPayload`（性能好、无状态；代价是用户被删/禁用后 token 在有效期内仍可用，本期接受，后续需要可加查库校验 `is_active`）。

### 3. 全项目默认鉴权 + 白名单

- 在 `app = FastAPI(dependencies=[Depends(get_current_user)])` 挂**全局依赖**，所有路由（含文档路由）默认执行鉴权。
- `get_current_user` 内部维护白名单 `PUBLIC_PATHS`，路径命中则直接放行（返回 None）；否则解析 `Authorization: Bearer <token>`，失败抛 401（带 `WWW-Authenticate: Bearer` 头）。
- 新增接口默认受保护，无需任何额外代码；如需公开，把路径加入白名单即可。
- 路由层如需当前用户，在 handler 上显式声明 `Depends(get_current_user)` —— FastAPI 依赖缓存保证同一请求只执行一次鉴权，不会重复解析 token。

## 接口定义

| 方法 | 路径 | 鉴权 | 请求体 | 响应 |
| --- | --- | --- | --- | --- |
| GET | `/auth/captcha` | 公开 | — | 200 `{captcha_id, image, expires_in}` |
| POST | `/auth/register` | 公开 | `{username, password, captcha_id, captcha_code}` | 201 `UserDTO`；400 验证码错误；409 用户名已存在 |
| POST | `/auth/login` | 公开 | `{username, password, captcha_id, captcha_code}` | 200 `{access_token, token_type, expires_in}`；400 验证码错误；401 凭据错误 |
| GET | `/auth/me` | 需 token | — | 200 当前用户（`TokenPayload` 对应 DTO） |
| GET | `/user/{id}` | 需 token（自动生效） | — | 200 `UserDTO`；404 |

## 数据流

- **验证码**：`GET /auth/captcha` → `CaptchaService.generate` 生成 4 位字符与 PNG，`code_hash` 入库并清理过期记录 → 返回 `captcha_id` / `image` / `expires_in`。
- **注册**：controller → 校验验证码（一次性删除）→ service（查重 by username）→ 哈希密码 → mapper.create → 返回 UserDTO（201）。
- **登录**：controller → 校验验证码（一次性删除）→ service（find_by_username）→ verify_password → security.create_access_token → 返回 token（401 on fail）。
- **受保护接口**：全局依赖解析 Bearer token → 成功则放行（handler 可按需接收 `TokenPayload`）；失败 401。

验证码的详细设计（表结构、摘要、一次性、前端交互）见 `backend/docs/specs/captcha/02-design.md`。

## 配置项（`app/core/config.py` Settings 新增）

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `jwt_secret` | str | 无（必填） | JWT 签名密钥，由 `.env` 提供 |
| `jwt_expire_minutes` | int | 1440 | token 有效期（分钟），默认 24h |
| `captcha_ttl_seconds` | int | 300 | 验证码有效期（秒） |
| `captcha_length` | int | 4 | 验证码字符数（服务端限制 4~8） |

## 依赖变更（backend/pyproject.toml）

| 包 | 用途 | 兼容性 |
| --- | --- | --- |
| `pyjwt>=2.10` | JWT 签发/校验 | 纯 Python，与现有依赖零冲突 |
| `pwdlib[argon2]>=0.2` | argon2 密码哈希 | 纯 Python + argon2-cffi（有 Windows wheel），与现有依赖零冲突 |
| `captcha>=0.7.1` | 图片验证码渲染 | 依赖 Pillow，有 Windows / Linux wheel |
