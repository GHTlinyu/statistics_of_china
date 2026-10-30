# 04 交付：认证与 Token 签发/校验

- 功能 slug：`auth-token`
- 日期：2026-10-26
- 状态：已交付并验证

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `pyproject.toml` | 新增 `pyjwt>=2.10.1`、`pwdlib[argon2]>=0.2.1` |
| `.env` | 新增 `JWT_SECRET`（随机生成）、`JWT_EXPIRE_MINUTES=1440` |
| `app/core/config.py` | `Settings` 新增 `jwt_secret`、`jwt_expire_minutes` |
| `app/security/security.py` | 新增：argon2 密码哈希、JWT 签发/解析 |
| `app/security/deps.py` | 新增：`get_current_user` 全局鉴权依赖 + `PUBLIC_PATHS` 白名单 |
| `app/schema/authDTO.py` | 新增：`RegisterRequest`、`LoginRequest`、`TokenResponse`、`TokenPayload` |
| `app/service/authService.py` | 新增：`register`（查重+哈希）、`authenticate`（凭据校验） |
| `app/mapper/userMapper.py` | 新增：`find_by_username`、`create` |
| `app/controller/authController.py` | 新增：`POST /auth/register`、`POST /auth/login`、`GET /auth/me` |
| `app/main.py` | 挂载全局鉴权依赖，注册 auth 路由 |

## 验证结果（实测）

| 场景 | 结果 |
| --- | --- |
| `GET /health` 无 token | 200 ✅ |
| `GET /user/1` 无 token | 401 ✅ |
| `GET /auth/me` 伪造 token | 401 ✅ |
| `POST /auth/register` 新用户 | 201，返回 UserDTO（不含 password_hash）✅ |
| `POST /auth/register` 重复用户名 | 409 ✅ |
| `POST /auth/login` 密码错误 | 401（不区分用户不存在/密码错）✅ |
| `POST /auth/login` 正确凭据 | 200，签发 JWT ✅ |
| `GET /auth/me` 携带合法 token | 200，返回载荷用户信息 ✅ |
| `GET /user/1` 携带合法 token | 200 ✅ |
| `GET /docs`、`GET /openapi.json` 无 token | 200 ✅ |

## 使用方式

> 2026-10-30 起登录 / 注册必须携带 `captcha_id` 与 `captcha_code`，最新示例见 `backend/docs/specs/captcha/04-delivery.md`。

```bash
# 注册（公开）
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"secret123"}'

# 登录获取 token（公开）
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"secret123"}'

# 携带 token 访问受保护接口
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8000/auth/me
```

## 后续开发者注意事项

- 新增接口**默认受保护**；如需公开，把路径加入 `app/security/deps.py` 的 `PUBLIC_PATHS`。
- 如需在 handler 中获取当前用户，声明 `current_user: Annotated[TokenPayload, Depends(get_current_user)]`（同一请求只解析一次 token）。
- 本期 token 校验后不查库（无状态），用户被删/禁用后 token 在有效期内仍可用；如需强制校验 `is_active`，在 `decode_access_token` 之后增加一次数据库查询即可。

## 2026-10-30 验证码接入

登录 / 注册已接入一次性图片验证码，并新增公开接口 `GET /auth/captcha`；改动清单、联调结果与已知限制见 `backend/docs/specs/captcha/04-delivery.md`。
