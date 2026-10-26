国家统计年鉴（2025）智能助手项目

使用FastAPI、Postgresql、Langgraph等搭建的智能助手项目，前后端同仓（monorepo）。

# 后端（backend/）

- 依赖管理：uv workspace（根目录 `uv sync`）
- 启动命令（在仓库根目录执行）：

```bash
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

- 数据库初始化：`uv run python -m backend.app.database.init_db`
- 配置：仓库根目录 `.env`

# RAG部分

- 详细文档放入了`backend\rag\docs\README.md`当中
- rag文件夹下代码不一定能执行

# 前端（frontend/）

- 待建设
