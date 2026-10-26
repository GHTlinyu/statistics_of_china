# 项目说明

《中国统计年鉴 2025》智能助手：基于 FastAPI + PostgreSQL（pgvector）+ LangGraph 的 RAG 问答服务。前后端同仓的 monorepo：`backend/`（Python/uv workspace 成员）与 `frontend/`（待建设）。

## 常用命令

**所有 uv 命令在仓库根目录执行**（uv 自动发现 workspace；后端代码统一使用 `backend.app.*` 绝对导入）：

```bash
uv sync                                                  # 安装/同步依赖
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000   # 启动 API 服务
uv run python -m backend.app.database.init_db            # 初始化数据库表
uv run python scripts/setup_agent_skills.py              # 建立 .claude/skills 联接
```

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `backend/app/` | 后端服务层：`database/`（引擎、会话、配置）、`model/`（SQLAlchemy 模型）、`controller/`、`service/`、`mapper/`、`schema/`、`security/` |
| `backend/agent/` | LangGraph 智能体（待建设） |
| `backend/rag/` | 知识库数据与设计文档，详见 `backend/rag/docs/README.md` |
| `backend/docs/specs/` | 功能开发全链路文档，见 `backend/docs/specs/README.md` |
| `frontend/` | 前端项目（待建设） |
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
- Python 3.12+，类型注解写全
- SQLAlchemy 使用 2.0 类型化写法（`Mapped` / `mapped_column`）
- 数据库会话通过 `backend.app.database.database.get_db` 依赖注入
- 新增配置项统一加到 `backend/app/database/config.py` 的 `Settings` 中，通过仓库根 `.env` 提供值（`config.py` 已锚定根目录，工作目录不影响读取）
- API、业务逻辑、数据访问分层；Pydantic schema 与 ORM 模型分开定义
- 与用户交流使用中文，代码标识符使用英文

## RAG 数据注意事项

- `backend/rag/` 下的 `.md`、`.json` 文件体积很大，**不要整文件读取**，按需检索或用脚本处理
- 知识库入库的三张表（documents、document_chapters、document_chunks）设计见 `backend/rag/docs/README.md`
- `.env` 中保存数据库与 LLM 密钥，不要写入代码、日志或提交到仓库

## Agent Skills

- 技能放在 `.agent/skills/<name>/SKILL.md`，模板见 `.agent/templates/SKILL.md`
- Claude Code 通过 `.claude/skills` 目录联接识别技能；克隆仓库后执行 `scripts/setup_agent_skills.py`
- 新增或修改技能后需重启会话才会加载
