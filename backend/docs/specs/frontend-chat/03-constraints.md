# 03 开发约束：前端对话页

- 功能 slug：`frontend-chat`
- 日期：2026-11-12

## 官方技能约束（@ant-design/x-skill 开发规则）

| 编号 | 约束 | 来源技能 |
| --- | --- | --- |
| C1 | 自定义 Provider 只实现 `transformParams` / `transformLocalMessage` / `transformMessage` 三个方法，**禁止重写 request 方法** | x-chat-provider |
| C2 | `transformMessage` 返回值中**禁止加 status 字段**（status 由框架管理） | x-chat-provider |
| C3 | Provider 中的 XRequest 必须配置 `manual: true`（否则构造时抛错） | x-chat-provider / use-x-chat |
| C4 | 多会话场景每个会话独立 Provider 实例，用 Map 缓存复用 | use-x-chat |
| C5 | `Bubble.List` 消息经 `MessageInfo[]` 映射为 `{key, role, content, loading}`，用 `role` 属性配置角色样式（不是 `roles`） | use-x-chat |
| C6 | XMarkdown 流式渲染：`hasNextChunk` 必须真实反映流状态，**最后一块必须为 false**，否则不完整片段不会刷新为最终内容 | x-markdown |
| C7 | 前端环境禁止在 XRequest headers 中硬编码密钥；Bearer token 取用户会话 token（localStorage），经 umi 代理转发 | x-request |
| C8 | 用户未要求测试用例时不添加测试文件 | 全部技能 |

## 项目约定

| 编号 | 约束 |
| --- | --- |
| C9 | REST 接口一律走 umi `request`（`src/app.tsx` 已封装：自动带 token、剥离 `{code,message,data}`、401 跳登录）；SSE 聊天走 XRequest 原生 fetch |
| C10 | SSE 的 401 不经 umi 拦截器，需在 XRequest `middlewares.onResponse` 中单独处理（清 token + 跳登录） |
| C11 | 请求路径写 `/api/...`（开发环境经 umi 代理到后端 8000） |
| C12 | 后端 SSE 协议 `start` / `token` / `done` / `error` 不可变；`error` 事件在 `transformMessage` 中抛 `ChatRequestError` 触发 `requestFallback` 兜底展示 |
| C13 | 完成编写后必须运行 `tsc --noEmit` 与 `pnpm build` 通过 |
| C14 | 用户对话消息落库由后端负责（chat R5），前端不重复调用 `POST /conversation/{id}/messages` |

## 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-11-12 | 初稿 | 设计与技能调研完成后沉淀约束 |
