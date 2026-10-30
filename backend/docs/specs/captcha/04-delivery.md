# 04 交付：登录 / 注册验证码

- 功能 slug：`captcha`
- 日期：2026-10-30
- 状态：已实现并完成真实联调（真实 PostgreSQL、真实图片生成、前端生产构建）

## 改动清单

| 文件 | 改动 |
| --- | --- |
| `backend/pyproject.toml` | 新增 `captcha>=0.7.1`（自动携带 Pillow） |
| `backend/app/model/captcha.py` | 新增 `captcha` 表模型 |
| `backend/app/mapper/captchaMapper.py` | 新增：签发、加锁读取、删除、过期清理 |
| `backend/app/service/captchaService.py` | 新增：生成图片、摘要、校验、一次性销毁 |
| `backend/app/schema/captchaDTO.py` | 新增 `CaptchaDTO` |
| `backend/app/schema/authDTO.py` | `LoginRequest` / `RegisterRequest` 增加必填验证码字段 |
| `backend/app/controller/authController.py` | 新增 `GET /auth/captcha`；登录/注册前置校验 |
| `backend/app/service/authService.py` | 登录 401 / 注册 409 文案统一为中文 |
| `backend/app/security/deps.py` | `PUBLIC_PATHS` 增加 `/auth/captcha` |
| `backend/app/core/config.py` | 新增 `captcha_ttl_seconds`、`captcha_length` |
| `backend/app/database/init_db.py` | 注册 `Captcha` 模型 |
| `frontend/src/pages/Login/index.tsx` | 验证码展示、刷新、提交与失败后自动刷新 |
| `frontend/src/app.tsx` | 错误提示兼容 `message` 与 `detail`；登录/注册自身 401 不再按会话过期跳转 |
| `frontend/.umirc.ts` | 修复多异步 chunk 的 esbuild helper 冲突（`esbuildMinifyIIFE`） |

## 验证结果（真实数据库）

| 场景 | 结果 |
| --- | --- |
| `GET /auth/captcha` 无 token | 200；返回 `captcha_id` / `image` / `expires_in`，无明文验证码 ✅ |
| 验证码图片 | 可解析 PNG，160×60，data URL 约 10 KB ✅ |
| 登录缺少验证码字段 | 422 ✅ |
| 登录验证码错误 / 不存在 | 400，`detail="验证码错误或已过期"` ✅ |
| 登录验证码正确 + 密码正确 | 200，签发 token ✅ |
| 同一验证码重放 | 400；校验后记录已删除 ✅ |
| 验证码大小写不敏感 | 200 ✅ |
| 验证码过期 | 400 ✅ |
| 注册验证码错误 | 400，且未创建用户 ✅ |
| 注册验证码正确 | 201，创建用户成功 ✅ |
| 新用户登录 | 200 ✅ |
| 验证码正确但密码错误 | 401，`detail="用户名或密码错误"` ✅ |
| 重复用户名注册 | 409，`detail="用户名已存在"` ✅ |
| 登录后访问 `/auth/me`、`/conversation` | 200；无 token 访问受保护接口 401 ✅ |
| 数据库内容 | 仅 `code_hash`、`expires_at` 等，无明文；使用后记录删除 ✅ |
| 前端生产构建 | `pnpm build` 成功（先修复既有 esbuild helper 冲突）✅ |

## 手工验证

```bash
# 获取验证码（公开，返回 data:image/png;base64,...）
curl http://127.0.0.1:8000/auth/captcha

# 登录（需先从图片中读取验证码）
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "secret123",
    "captcha_id": "<captcha_id>",
    "captcha_code": "<image code>"
  }'

# 注册同样需要 captcha_id / captcha_code
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "secret123",
    "captcha_id": "<captcha_id>",
    "captcha_code": "<image code>"
  }'
```

前端：`pnpm dev` 打开 `http://localhost:8001/login`，验证码图片应显示在密码框下方，点击可刷新；登录失败后自动换一张。

## 已知限制

1. 未做登录失败限流 / 账户锁定（按确认范围）；验证码被 OCR 或打码平台绕过时仍可持续尝试。
2. 登录 / 注册请求新增必填字段，属于 API 契约变更；现有外部调用方必须同步更新。
3. 当前没有注册页面，注册接口的调用方需自行获取验证码。
4. `GET /auth/captcha` 可被匿名高频调用，会持续写入并清理 `captcha` 表；本期未加限流。
5. 验证码图片能挡住普通脚本，但不针对专门的 OCR / 打码平台。
6. 前端未做自动化 UI 测试，仅完成生产构建与接口联调。
7. 测试期间创建了用户 `captcha_u_48e447`（密码 `test123456`），如不需要可手动清理。

## 后续建议

1. 增加按 IP + 用户名的失败限流 / 临时锁定，作为验证码之外的第二道防线。
2. 强对抗场景可替换为 Cloudflare Turnstile / reCAPTCHA（需外部密钥）。
3. 如需完整的注册体验，补注册页面并复用同一验证码接口。
4. 可增加定时清理任务，替代当前「签发时顺带清理」。
