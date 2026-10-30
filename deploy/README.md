# 生产部署手册

《中国统计年鉴 2025》智能助手 —— 单云服务器部署指南。

**目标拓扑**

```
浏览器 ── 80/443 ──> nginx 容器 (host 网络)
                        │ 静态：前端 dist
                        │ /api/ 反代
                        ▼ 127.0.0.1:8000
                     backend 容器 (host 网络, 仅本机监听)
                        │ 127.0.0.1:5432
                        ▼
                     宿主机 PostgreSQL 16 + pgvector（已部署，维持现状）
```

两个容器都用 `network_mode: host`：PG 只监听本机回环，host 网络下容器直连 127.0.0.1，PG 配置零改动；对外暴露面只有 nginx 的 80/443。

## 0. 前置检查（本地执行）

1. **本地 PostgreSQL 主版本必须 ≤ 16**（服务器是 16.15）。如果本地是 17+，`pg_restore` 会拒载 dump，需先与服务器对齐版本。检查：

   ```bash
   psql -h 127.0.0.1 -p 5433 -U <user> -d <db> -c "SHOW server_version;"
   ```

2. 服务器已安装 Docker 与 compose 插件（`docker compose version`）。**除此之外宿主机不需要任何运行时（包括 git）**：uv / Python 依赖构建在容器内完成（后端镜像在构建容器里 pip 安装 uv），Node / pnpm 同理（nginx 镜像构建阶段自带）；部署文件由 CI 直接 scp 上传，服务器不依赖 git 仓库。
3. 防火墙：22（SSH 密钥登录）、80、443 开放；8000 与 5432 不开放。

## 1. 导出本地数据（本地执行）

> 导出前先清理开发/联调期间的测试数据（如 `memtest_1030`、`captcha_u_*` 等测试账号及其会话），否则它们会原样进生产库：
> ```sql
> DELETE FROM account WHERE username LIKE 'memtest_%' OR username LIKE 'captcha_u_%';
> -- 对应会话与消息可先按 user_id 清理，或保留由管理员后续处理
> ```

```bash
pg_dump -h 127.0.0.1 -p 5433 -U <user> -d <db> -Fc -f /tmp/soc-backup.dump
```

dump 包含全部业务数据（账户、会话、消息、长期记忆）与 RAG 向量数据（documents / document_chunks / chunk_retrieval），无需在服务器重跑 OCR 与 embedding 入库。`pg_dump` 同时会带出 `CREATE EXTENSION vector` 语句（恢复时自动处理 pgvector 扩展）。

## 2. 服务器目录准备（服务器执行）

服务器**不再需要 git 仓库**：CI 每次发布都会直接上传 `docker-compose.yml` 和镜像，服务器上只需要一个固定目录结构：

```bash
# 1. 创建部署目录（CI 的 deploy.yml 远程脚本按这个绝对路径操作，改路径需同步改 workflow）
sudo mkdir -p /opt/statistics_of_china/deploy
sudo chown -R $(whoami) /opt/statistics_of_china

# 2. 生成生产配置（把本地的 deploy/.env.docker.example 内容复制上来填值，
#    或先传到 /tmp 再移过来）
vim /opt/statistics_of_china/deploy/.env.docker
chmod 600 /opt/statistics_of_china/deploy/.env.docker
```

最终结构：

```
/opt/statistics_of_china/
└── deploy/
    ├── docker-compose.yml   ← CI 每次部署自动上传覆盖，无需手工维护
    └── .env.docker          ← 手工维护一次，CI 不碰
```

**填写方法**：打开本地开发用的根目录 `.env` 作为参照，按下表逐项抄改：

| 键 | 怎么填 |
| --- | --- |
| `DB_HOST` | 改为 `127.0.0.1`（服务器 PG 在本机；不要抄本地值） |
| `DB_PORT` | 改为 `5432`（服务器 PG 默认端口；本地是 5433） |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | 以服务器 PG 实际创建的库/用户/密码为准，不是抄本地 |
| `JWT_SECRET` | 重新生成一个长随机串，不要抄本地 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 照抄本地 `.env`（外部服务，通用） |
| `LLM_EMBEDDING_API_KEY` / `LLM_EMBEDDING_BASE_URL` / `LLM_EMBEDDING_MODEL` | 照抄本地（Jina 向量服务，通用） |
| `LLM_RERANK_API_KEY` / `LLM_RERANK_BASE_URL` / `LLM_RERANK_MODEL` | 照抄本地（同上） |
| 其余带 `#` 注释的行 | 保持注释，使用默认值 |

为什么不用本地 `.env` 直接传上去：它被 .gitignore 排除、不进 git；数据库地址不同（本地 5433 vs 服务器 5432）；开发密钥与生产环境应隔离。

`.env.docker` 含密钥，已被 `.dockerignore`（不进镜像）和 `.gitignore`（不进 git）同时排除。**容器如何读到它**：compose 的 `env_file` 在 `up` 时把文件的每一行解析成 backend 容器的环境变量（容器内并不存在这个文件）；代码的三个配置读取器（pydantic-settings / load_dotenv）都遵循环境变量优先，直接从环境变量取配置。可用 `docker compose -f deploy/docker-compose.yml exec backend env` 查看注入结果。

## 3. 恢复数据到服务器 PG（服务器执行）

```bash
# 上传 dump 后，恢复到新建库最安全（先建库，避免 --clean 误伤）
sudo -u postgres createdb <db_name>
pg_restore -h 127.0.0.1 -p 5432 -U postgres -d <db_name> -v soc-backup.dump
```

- 恢复完成后 `\dx` 应能看到 `vector` 扩展；`\dt` 应能看到 9 张表（documents、document_chapters、document_chunks、chunk_retrieval、account、conversation、message、memory、captcha）。
- 若此前库里已有同名表导致恢复报错，先 `dropdb <db_name> && createdb <db_name>` 再恢复。
- 本地没有单独设置 `captcha` 表的话（表在第一次 init_db 时已建），以 `\dt` 实际结果为准；`entrypoint.sh` 会幂等补建缺的表。

## 4. 首次启动（走 CI）

服务器上**没有代码仓库**（部署文件由 CI 直接上传），所以不能在服务器本地 `--build`。首次启动两种方式：

**方式 A：CI 部署（推荐）**——服务器就绪后（目录、`.env.docker`、数据恢复完成），push 一次代码触发流水线，CI 完成构建 → 上传 → load → 启动，全程无需服务器操作。

**方式 B：手动 load（CI 不可用时）**——按 8.4 节把镜像 tar 与 compose 文件传上来后：

```bash
gunzip -c /tmp/soc-deploy/soc-backend.tar.gz | docker load
gunzip -c /tmp/soc-deploy/soc-nginx.tar.gz | docker load
cd /opt/statistics_of_china && docker compose -f deploy/docker-compose.yml up -d --no-build
```

查看状态：

```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f backend
```

## 5. 启动验证清单（服务器执行）

```bash
# 1. 健康检查（经 nginx 反代，公开接口，无需 token）
curl -s https://creative-idea-generator.site/api/health

# 2. HTTP 应 301 跳转 HTTPS
curl -I http://creative-idea-generator.site/

# 3. 验证码接口（公开，确认后端连通）
curl -s https://creative-idea-generator.site/api/auth/captcha | head -c 200

# 4. 容器状态：两个服务都是 running / healthy
docker compose -f deploy/docker-compose.yml ps
```

然后浏览器访问 `https://creative-idea-generator.site/`：登录页应正常显示验证码图片；登录后应能创建会话并**流式**收到聊天回答（token 逐字出现说明 SSE 反代正常）。

## 6. 数据备份（服务器，crontab）

容器 PG 不存在（PG 在宿主机），直接对宿主机 PG 定时 dump：

```bash
mkdir -p /var/backups/soc
# 每天凌晨 3 点备份，保留 14 天
sudo crontab -e
# 0 3 * * * pg_dump -h 127.0.0.1 -U postgres -d <db_name> -Fc -f /var/backups/soc/$(date +\%F).dump
# 10 3 * * * find /var/backups/soc -name '*.dump' -mtime +14 -delete
```

建议再把 dump 同步到对象存储或另一台机器（本机磁盘坏了备份也就没了）。

## 7. HTTPS 证书

证书文件由服务器手工维护，CI 不碰。约定位置：

```
/opt/statistics_of_china/deploy/nginx/certs/
├── fullchain.pem      # 证书链
└── private.key        # 私钥
```

项目文件已配置好：compose 把该目录只读挂载进 nginx 容器（`/etc/nginx/certs`），nginx.conf 的 443 块读取这两个文件，80 端口全部 301 跳转 HTTPS。发布一次（push 或手动触发 CI）后生效。

验证：

```bash
curl -I https://creative-idea-generator.site/api/health   # 应返回 200
curl -I http://creative-idea-generator.site/              # 应返回 301 → https
```

证书到期后：把新的 `fullchain.pem` / `private.key` 覆盖上传到同一目录，然后：

```bash
cd /opt/statistics_of_china
docker compose -f deploy/docker-compose.yml exec nginx nginx -s reload
```

（无需重新构建镜像；文件是挂载进容器的，reload 即生效。）

## 8. 更新发布（GitHub Actions）

推荐走 CI 流水线：GitHub runner 上构建镜像 → scp 传服务器 → 服务器 load 后重启，不需要镜像仓库，**服务器也不需要 git**。

### 8.1 一次性准备

1. 代码推到 GitHub，服务器上按第 2 节准备目录：

   ```bash
   sudo mkdir -p /opt/statistics_of_china/deploy
   sudo chown -R $(whoami) /opt/statistics_of_china
   ```

2. 服务器上创建生产配置（CI 不碰密钥）：

   ```bash
   vim /opt/statistics_of_china/deploy/.env.docker && chmod 600 /opt/statistics_of_china/deploy/.env.docker
   ```

3. GitHub 仓库 Settings → Secrets and variables → Actions，新增（与 SSH 连接测试共用）：
   - `ECS_SSH_PRIVATE_KEY`（CI 专用私钥，服务器对应用户的 `authorized_keys` 已放公钥）
   - `ECS_USER`（部署用户）
   - `ECS_HOST`（服务器 IP 或域名）

### 8.2 发布方式

| 方式 | 操作 |
| --- | --- |
| 自动 | push 到 `master` 即触发（`.github/workflows/deploy.yml` 已配）；只想手动时注释掉 workflow 里的 `push` 块 |
| 手动 | Actions 页面 → deploy workflow → Run workflow |

流水线顺序：**单元测试（205 个用例）→ 构建两个镜像 → scp 上传（镜像 + docker-compose.yml）→ 服务器放置部署文件 + load + compose up**。测试失败会阻断部署。

### 8.3 回滚

部署脚本会在 load 前把上一版镜像标记为 `soc-*-previous`，服务器上回滚：

```bash
docker tag soc-backend:previous soc-backend:latest
docker tag soc-nginx:previous soc-nginx:latest
docker compose -f deploy/docker-compose.yml up -d --no-build
```

### 8.4 无 CI 时的手动发布（备选）

服务器上没有 git 仓库时，手动上传部署文件与镜像：

```bash
# 本地：打包镜像 + compose 文件上传
docker save soc-backend:latest | gzip -1 > soc-backend.tar.gz
docker save soc-nginx:latest | gzip -1 > soc-nginx.tar.gz
scp soc-backend.tar.gz soc-nginx.tar.gz deploy/docker-compose.yml <server>:/tmp/soc-deploy/

# 服务器：放置文件 → 加载 → 启动
mkdir -p /opt/statistics_of_china/deploy
cp /tmp/soc-deploy/docker-compose.yml /opt/statistics_of_china/deploy/
gunzip -c /tmp/soc-deploy/soc-backend.tar.gz | docker load
gunzip -c /tmp/soc-deploy/soc-nginx.tar.gz | docker load
cd /opt/statistics_of_china && docker compose -f deploy/docker-compose.yml up -d --no-build
```

- 后端镜像因依赖声明层缓存，普通代码改动重建很快（只重新 COPY 代码层）。
- 前端改动会重新触发 `pnpm build`，耗时较长，属正常。
- 若改了 `backend/pyproject.toml` 依赖，build 阶段会自动重装。
- 数据库结构有变化时，`entrypoint.sh` 里的 `init_db`（create_all）只会**新建缺失的表**，不会改已有表结构；需要加列/改列时先手工在服务器 PG 执行迁移 SQL，再更新代码。

## 9. 故障排查

| 现象 | 排查 |
| --- | --- |
| 流水线在「上传镜像」或「加载镜像」步骤失败 | `ECS_SSH_PRIVATE_KEY` / `ECS_USER` / `ECS_HOST` 三个 secret 是否配置正确；服务器 `authorized_keys` 是否有对应公钥 |
| 流水线在「放置部署文件」步骤失败 | 部署用户对 `/opt/statistics_of_china` 是否有写权限（`sudo chown -R $(whoami) /opt/statistics_of_china`） |
| backend 起不来，日志报连接 PG 失败 | `deploy/.env.docker` 的 `DB_HOST=127.0.0.1`、`DB_PORT=5432`、库名/用户/密码是否与宿主机 PG 一致；PG 的 `pg_hba.conf` 是否允许 127.0.0.1 的 md5/scram 认证 |
| entrypoint 报 `permission denied to create extension "vector"` | 数据库用户无扩展权限。用 postgres 超级用户执行一次：`psql -h 127.0.0.1 -U postgres -d <db> -c "CREATE EXTENSION IF NOT EXISTS vector;"`，之后重启容器 |
| 聊天回答一次性全部吐出（不流式） | nginx 的 `proxy_buffering off` 是否生效（本仓库配置已含）；确认请求走的是 `/api/` 反代而不是直连 8000 |
| 访问 `/api/...` 返回 nginx 404 | 反代规则 `proxy_pass http://127.0.0.1:8000/;` 尾部斜杠被删会导致路径拼接错误，对照 `deploy/nginx/nginx.conf` |
| 验证码图片不显示或乱码 | 后端日志看 `/auth/captcha` 是否 200；容器内 Pillow 与 captcha 包自带字体，无需系统字体 |
| 前端页面 404（刷新后） | SPA 回退规则 `try_files $uri $uri/ /index.html;` 是否生效 |
| 服务器重启后服务没起来 | compose 已配 `restart: unless-stopped`；确认 docker 服务本身开机自启（`systemctl enable docker`） |
| 数据库连接间歇性断开 | 宿主机 PG 的 `tcp_keepalives` / 系统 idle 超时；backend 连接池默认 `pool_pre_ping=True` 已带连接探活 |

## 10. 已知边界

- 验证码表 `captcha` 会在 entrypoint 的 init_db 里幂等创建；服务器 PG 若从未跑过 init_db，首次启动会自动补齐全部缺表。
- 检索与 LLM 均为外部 API（Jina / 你的 LLM 网关），服务器需能出网访问；不通时聊天会返回 `error` 事件。
- host 网络下 backend 的 8000 端口必须空闲（无其他进程占用）。
- `frontend/dist` 不进 git，由 nginx 镜像构建阶段生成；服务器上不必单独跑前端构建。
