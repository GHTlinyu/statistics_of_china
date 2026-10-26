# 01 需求规格：认证与 Token 签发/校验

- 功能 slug：`auth-token`
- 状态：已确认
- 日期：2026-10-26

## 背景与目标

项目当前无任何认证机制，数据库 `account` 表中也没有用户数据。需要参照 Spring Security 的思路，实现一套简单可用的 token 签发与校验机制，并提供一个用户注册接口，保证后续新增接口默认处于受保护状态。

## 需求条目（已与用户确认）

| 编号 | 需求 | 说明 |
| --- | --- | --- |
| R1 | JWT 签发与校验 | 使用 PyJWT，HS256 签名，载荷含 `sub`（user_id）、`username`、`role`、`exp`。校验失败返回 401。 |
| R2 | 密码哈希 | 使用 `pwdlib[argon2]`（FastAPI 官方推荐方案），注册时哈希入库，登录时校验。 |
| R3 | 用户注册接口 | `POST /auth/register`：提交 `username` + `password`，注册成功返回用户信息（201），不签发 token；用户名已存在返回 409。 |
| R4 | 登录接口 | `POST /auth/login`：验证用户名密码后签发 JWT，返回 `access_token`、`token_type`、过期时长；凭据错误返回 401。 |
| R5 | 当前用户接口 | `GET /auth/me`：返回当前登录用户信息（token 载荷内容），作为鉴权链路示范。 |
| R6 | 全项目默认鉴权 | 除白名单外的所有接口默认要求携带合法 `Authorization: Bearer <token>`，保证后续开发的接口自动受保护。 |
| R7 | 配置化 | JWT 密钥与有效期通过 `.env` 配置（`Settings` 新增 `jwt_secret`、`jwt_expire_minutes`），密钥不写入代码。 |

## 公开接口白名单

以下路径免鉴权（其余全部默认要求 token）：

- `GET /health`（健康检查探针）
- `POST /auth/register`、`POST /auth/login`
- `GET /docs`、`GET /redoc`、`GET /openapi.json`（开发期 API 文档）

## 非目标（本期不做）

- refresh token / token 主动吊销（登出）
- 细粒度 RBAC 权限校验（token 中的 `role` 字段本期仅承载，不做接口级角色控制）
- 密码找回、修改密码
- 注册后的邮箱/手机验证

## 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-10-26 | 密码哈希由 bcrypt 改为 argon2（pwdlib） | 用户要求采用 FastAPI 官方推荐方案 |
| 2026-10-26 | 鉴权范围由"仅示范接口"改为"全项目默认鉴权 + 白名单" | 用户要求保证后续开发接口的安全 |
