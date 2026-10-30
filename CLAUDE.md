# 项目说明

《中国统计年鉴 2025》智能助手：基于 FastAPI + PostgreSQL（pgvector）+ LangGraph 的 RAG 问答服务。前后端同仓的 monorepo：`backend/`（Python/uv workspace 成员）与 `frontend/`（Umi Max/React + pnpm workspace 成员）。

## 常用命令

**后端（uv 命令在仓库根目录执行**，uv 自动发现 workspace；后端代码统一使用 `backend.app.*` 绝对导入）：

```bash
uv sync --all-packages                                   # 安装/同步所有 workspace 成员依赖
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000   # 启动 API 服务
uv run python -m backend.app.database.init_db            # 初始化数据库表
uv run --package statistics-of-china-backend pytest backend/tests   # 运行后端单元测试
uv run python scripts/setup_agent_skills.py              # 建立 .claude/skills 联接
```

> 注意：根目录的 `uv sync` **只同步依赖为空的根项目**，会卸载 `backend` 成员的依赖；同步依赖必须用 `uv sync --all-packages`（或在 `backend/` 目录执行 `uv sync`）。

**前端（pnpm 命令在仓库根目录执行**；Node 由 fnm 管理，版本见根目录 `.node-version`，需 `fnm env` 已生效）：

```bash
pnpm install                                            # 安装前端依赖（npmmirror 源）
pnpm dev                                                # 启动前端开发服务器（8001，/api 代理到后端 8000）
pnpm build                                              # 前端生产构建
```

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `backend/app/` | 后端服务层：`database/`（引擎、会话、配置）、`model/`（SQLAlchemy 模型）、`controller/`、`service/`、`mapper/`、`schema/`、`security/` |
| `backend/agent/` | LangGraph 智能体（待建设） |
| `backend/rag/` | 知识库数据与设计文档，详见 `backend/rag/docs/README.md` |
| `backend/docs/specs/` | 功能开发全链路文档，见 `backend/docs/specs/README.md` |
| `frontend/` | 前端项目（@umijs/max + antd）：`.umirc.ts`（路由/代理）、`src/app.tsx`（全局请求封装）、`src/pages/`（页面） |
| `.agent/skills/` | 项目 Agent Skills 源文件 |
| `scripts/` | 开发辅助脚本 |
| `.env` | 仓库根目录的密钥配置（数据库与 LLM），后端经锚定路径读取 |

## 功能开发流程

- 每个新功能在 `backend/docs/specs/<feature-slug>/` 下建立独立目录，按链路推进：
  `01-requirements.md`（需求规格） → `02-design.md`（设计） → `03-constraints.md`（开发约束） → `04-delivery.md`（交付）
- 模板位于 `backend/docs/specs/_templates/`，新建功能时复制到功能目录
- 需求或设计发生变更时，先更新文档并记录变更，再修改代码

## 开发约定

- 使用 `uv` 管理依赖，不直接使用 `pip`；后端为 workspace 成员，依赖声明在 `backend/pyproject.toml`
- 前端使用 `pnpm` 管理依赖（workspace 声明在根 `pnpm-workspace.yaml`），不直接使用 npm/yarn；npm 源为 npmmirror
- Python 3.12+，类型注解写全；Node.js ≥ 18（fnm 管理，见 `.node-version`）
- SQLAlchemy 使用 2.0 类型化写法（`Mapped` / `mapped_column`）
- 数据库会话通过 `backend.app.database.database.get_db` 依赖注入
- 新增配置项统一加到 `backend/app/database/config.py` 的 `Settings` 中，通过仓库根 `.env` 提供值（`config.py` 已锚定根目录，工作目录不影响读取）
- API、业务逻辑、数据访问分层；Pydantic schema 与 ORM 模型分开定义
- 前端页面请求一律使用 umi 的 `request`（`src/app.tsx` 已封装：自动带 Bearer token、剥离 `{code,message,data}` 统一结构、401 跳登录页），不直接写 axios/fetch
- 前端开发端口 8001（`frontend/.env` 的 `PORT`），后端 8000；开发环境跨域通过 umi 代理 `/api` 解决
- 与用户交流使用中文，代码标识符使用英文

## RAG 数据注意事项

- `backend/rag/` 下的 `.md`、`.json` 文件体积很大，**不要整文件读取**，按需检索或用脚本处理
- 知识库入库的三张表（documents、document_chapters、document_chunks）设计见 `backend/rag/docs/README.md`
- `.env` 中保存数据库与 LLM 密钥，不要写入代码、日志或提交到仓库

## Agent Skills

- 技能放在 `.agent/skills/<name>/SKILL.md`，模板见 `.agent/templates/SKILL.md`
- Claude Code 通过 `.claude/skills` 目录联接识别技能；克隆仓库后执行 `scripts/setup_agent_skills.py`
- 新增或修改技能后需重启会话才会加载
