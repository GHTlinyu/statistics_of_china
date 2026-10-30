国家统计年鉴（2025）智能助手项目

使用FastAPI、Postgresql、Langgraph等搭建的智能助手项目，前后端同仓（monorepo）。

# 后端（backend/）

- 依赖管理：uv workspace（根目录 `uv sync`）
- 启动命令（在仓库根目录执行）：

```bash
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

- 数据库初始化：`uv run python -m backend.app.database.init_db`
- 单元测试：`uv run --package statistics-of-china-backend pytest backend/tests`（详见 `backend/tests/README.md`）
- 配置：仓库根目录 `.env`

# RAG部分

- 详细文档放入了`backend\rag\docs\README.md`当中
- rag文件夹下代码不一定能执行

# 前端（frontend/）

- 技术栈：Umi Max（umi 4）+ React + antd + TypeScript
- 依赖管理：pnpm workspace（根目录 `pnpm install`；Node 由 fnm 管理）
- 开发服务器（在仓库根目录执行）：

```bash
pnpm dev   # http://localhost:8001，/api 请求自动代理到后端 8000
```

- 生产构建：`pnpm build`
- 登录页对接 `POST /auth/login`；token 存 localStorage，请求自动携带（见 `frontend/src/app.tsx`）
