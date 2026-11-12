# 04 交付：前端对话页

- 功能 slug：`frontend-chat`
- 日期：2026-11-12

## 交付内容

| 文件 | 说明 |
| --- | --- |
| `frontend/src/services/chat/types.ts` | 类型定义：ChatEvent（SSE 事件）、ChatMessage、ChatInput、ConversationDTO、MessageDTO、PageResult、CurrentUser |
| `frontend/src/services/chat/provider.ts` | `BackendChatProvider`（AbstractChatProvider 子类，适配私有 SSE 协议）、`ChatRequestError`、Provider 实例缓存与 401 处理 |
| `frontend/src/services/chat/conversationApi.ts` | 会话/消息 REST 封装（umi request） |
| `frontend/src/pages/Chat/index.tsx` | 对话页：Conversations 侧栏 + Bubble.List + Sender + 欢迎空态（Welcome/Prompts）+ XMarkdown 流式渲染 |
| `frontend/.umirc.ts` | `/home` 路由改指 Chat 页（原 Home 页已删除） |
| `frontend/package.json` | 新增 `@ant-design/x`、`@ant-design/x-sdk`、`@ant-design/x-markdown`（均 2.10.0） |

## 需求对照

| 需求 | 状态 | 说明 |
| --- | --- | --- |
| R1 技术栈 | ✅ | 三个包 2.10.0，peer 兼容 antd 6 / React 19 |
| R2 页面布局 | ✅ | 替换 Home 页，退出登录保留在侧栏底部 |
| R3 自定义 Provider | ✅ | 只实现三个转换方法，`manual: true`，SSE 经默认解析器 + JSON.parse 按类型分发 |
| R4 流式问答 | ✅ | placeholder（loading）→ token 追加（updating）→ done（success）；error 事件抛 `ChatRequestError` 触发 requestFallback |
| R5 多会话 | ✅ | useXConversations + 每会话独立 Provider + 异步 defaultMessages 加载历史 |
| R6 新建/删除会话 | ✅ | 新建走 `POST /conversation` + queueRequest；删除走 `DELETE` + 释放 Provider 缓存 |
| R7 停止生成 | ✅ | Sender onCancel → abort；AbortError 兜底展示部分内容 +「已停止生成」（后端落库完整部分） |
| R8 Markdown 渲染 | ✅ | XMarkdown 流式渲染，`hasNextChunk` 与消息状态联动，末块为 false |
| R9 认证与代理 | ✅ | REST 走 umi request；SSE 走 XRequest + `/api` 代理，401 经 middlewares.onResponse 处理 |
| R10 空态 | ✅ | Welcome + Prompts 建议问题（点击即发送） |

## 验证情况

| 验证项 | 结果 |
| --- | --- |
| `tsc --noEmit` | ✅ 通过 |
| `pnpm build` | ✅ 构建成功 |
| SSE 线上格式 | ✅ 实测：`data: {"type": ..., "data": {...}}\n\n` 帧，与 XRequest 默认解析器（`\n\n`/`\n`/`:` 分隔）完全匹配 |
| 端到端联调（真实问答） | ✅ 2026-11-12 通过：注册/登录（人工识别验证码）→ 创建会话 → 直连 SSE 问答（start→29×token→done，回答正确）→ 消息落库（user+assistant）→ 会话标题自动填充 → **经前端 8001 代理** SSE 问答同样正常（47 帧） |
| 多轮对话 | ✅ 第二轮追问正常（message_id=34，历史上下文由后端注入） |

## 遗留事项

- 浏览器人工走查：dev 服务已在 8001 运行，可用测试账号 `e2e_test_user` / `test123456` 打开 `http://localhost:8001` 体验（登录需验证码）
- 会话列表仅取第一页 20 条、历史消息仅取最新一页 50 条，后续可加分页加载
- 引用来源展示（后端无 sources 事件，本期非目标）

## 变更记录

| 日期 | 变更 | 原因 |
| --- | --- | --- |
| 2026-11-12 | 初稿 | 代码交付完成 |
| 2026-11-12 | 端到端联调通过，更新验证情况 | 数据库恢复可用后完成实测 |
