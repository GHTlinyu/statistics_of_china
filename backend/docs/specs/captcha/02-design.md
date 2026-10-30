# 02 设计：登录 / 注册验证码

- 功能 slug：`captcha`
- 日期：2026-10-30

## 总体流程

```
GET /auth/captcha（公开）
  CaptchaService.generate(db)
    ├─ 清理过期记录
    ├─ 生成 4 位字符
    ├─ ImageCaptcha 渲染 PNG → base64 data URL
    ├─ code_hash = HMAC-SHA256(jwt_secret, code.upper())
    └─ 写入 captcha(id, code_hash, expires_at)
  → {captcha_id, image, expires_in}

POST /auth/login 或 /auth/register
  _ensure_captcha(db, captcha_id, captcha_code)
    ├─ SELECT ... FOR UPDATE
    ├─ 不存在 / 过期 / 摘要不匹配 → 删除记录 → 400
    └─ 匹配 → 删除记录 → 继续原有业务
  → 登录签发 token；注册创建用户
```

## 模块结构

```
backend/app/
├── model/captcha.py            captcha 表模型
├── mapper/captchaMapper.py     签发、加锁读取、删除、过期清理
├── service/captchaService.py   生成图片、摘要、校验
├── schema/captchaDTO.py        CaptchaDTO
├── schema/authDTO.py           LoginRequest / RegisterRequest 增加验证码字段
├── controller/authController.py  GET /auth/captcha；登录/注册前置校验
├── core/config.py              captcha_ttl_seconds、captcha_length
└── security/deps.py            PUBLIC_PATHS 增加 /auth/captcha
```

## 数据库表

```sql
CREATE TABLE captcha (
    id          VARCHAR(64) PRIMARY KEY,
    code_hash   VARCHAR(64) NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_captcha_expires_at ON captcha (expires_at);
```

- `id`：`uuid4().hex`，随机且不可枚举。
- `code_hash`：`HMAC-SHA256(jwt_secret, code.upper())` 的十六进制摘要，不存明文。
- `expires_at`：签发时间 + `captcha_ttl_seconds`（默认 300 秒），带索引供清理。

## 生成与校验

- 字符集：`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`，长度取 `captcha_length`（默认 4）。
- 图片：`captcha.image.ImageCaptcha(width=160, height=60)` 生成 PNG，base64 编码为 `data:image/png;base64,...`；响应只返回图片和 ID。
- 校验：先 `SELECT ... FOR UPDATE` 锁行，判断是否过期，再用 `hmac.compare_digest` 比较摘要；无论成功失败都删除记录并提交，保证一次性。
- 过期清理：每次生成新验证码时执行 `DELETE FROM captcha WHERE expires_at < now()`，避免表无限增长。
- 校验顺序：验证码校验放在 `AuthService.authenticate` / `register` 之前，验证码失败不会触发密码校验或用户查重。

## 接口定义

| 方法 | 路径 | 鉴权 | 请求 / 响应 |
| --- | --- | --- | --- |
| GET | `/auth/captcha` | 公开 | 200 `ApiResponse[CaptchaDTO]`：`{captcha_id, image, expires_in}` |
| POST | `/auth/login` | 公开 | 请求增加 `captcha_id` / `captcha_code`；验证码失败 400 |
| POST | `/auth/register` | 公开 | 请求增加 `captcha_id` / `captcha_code`；验证码失败 400 |

`LoginRequest` / `RegisterRequest` 的验证码字段为必填，长度 1~64（ID）与 1~8（字符）。

## 错误处理

| 场景 | 响应 |
| --- | --- |
| 验证码不存在 / 过期 / 错误 / 重复使用 | 400，`detail="验证码错误或已过期"`，记录已删除 |
| 缺少验证码字段 | 422（Pydantic） |
| 验证码正确但密码错误 | 401（原有语义不变） |
| 验证码正确但用户名已存在 | 409（原有语义不变） |

当前 `main.py` 未启用全局 `HTTPException` 统一处理器，验证码错误会以 FastAPI 默认的 `{"detail": ...}` 返回；前端 `errorHandler` 兼容 `message` 与 `detail` 两种字段。

## 前端

- 登录页挂载时请求 `GET /auth/captcha`，在密码输入框右侧显示验证码图片。
- 点击图片重新获取；登录失败后自动刷新并清空验证码输入。
- 提交时携带 `captcha_id` 与 `captcha_code`；验证码未加载完成时禁止提交。
- 注册页当前不存在，注册接口的调用方需要自行先获取验证码；本次不新增注册页面。

## 关键决策

1. **存储选 PostgreSQL**：项目已有 PG，无需额外部署 Redis；多 worker / 重启后验证码仍有效。
2. **自托管图片验证码**：不依赖第三方服务与密钥，适合本地和内网；防普通脚本足够，强对抗场景后续可换 Turnstile。
3. **摘要存储**：即使 `captcha` 表泄露，也无法直接得到明文验证码。
4. **一次性 + 行锁**：删除与校验在同一事务内完成，避免并发重放。
5. **本期不做限流**：按用户确认的范围只做验证码；验证码被识别服务绕过时仍可继续尝试，限流作为后续补强项。
