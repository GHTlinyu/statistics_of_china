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

2. 服务器已安装 Docker 与 compose 插件（`docker compose version`）。**除此之外宿主机不需要任何运行时**：uv / Python 依赖构建在容器内完成（后端镜像在构建容器里 pip 安装 uv），Node / pnpm 同理（nginx 镜像构建阶段自带）。
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

## 2. 上传代码与配置

```bash
# 方式 A：git 分发（推荐，服务器可直连仓库）
git clone <repo-url> statistics_of_china && cd statistics_of_china

# 方式 B：本地打包上传
tar --exclude=.git --exclude=node_modules --exclude=.venv \
    -czf soc.tar.gz . && scp soc.tar.gz <server>:~/ && ssh <server> tar -xzf soc.tar.gz
```

```bash
# 生成生产配置
cd statistics_of_china
cp deploy/.env.docker.example deploy/.env.docker
vim deploy/.env.docker
#   必改：DB_PASSWORD、JWT_SECRET（重新生成）、LLM_API_KEY、LLM_EMBEDDING_API_KEY、LLM_RERANK_API_KEY
#   确认：DB_HOST=127.0.0.1、DB_PORT=5432、DB_NAME/DB_USER 与宿主机 PG 实际一致

chmod 600 deploy/.env.docker
```

`.env.docker` 含密钥，已被 `.dockerignore`（不进镜像）和 `.gitignore`（不进 git）同时排除；compose 通过 `env_file` 把它注入运行时的环境变量，容器内等效挂载在 `/app/.env`。

## 3. 恢复数据到服务器 PG（服务器执行）

```bash
# 上传 dump 后，恢复到新建库最安全（先建库，避免 --clean 误伤）
sudo -u postgres createdb <db_name>
pg_restore -h 127.0.0.1 -p 5432 -U postgres -d <db_name> -v soc-backup.dump
```

- 恢复完成后 `\dx` 应能看到 `vector` 扩展；`\dt` 应能看到 9 张表（documents、document_chapters、document_chunks、chunk_retrieval、account、conversation、message、memory、captcha）。
- 若此前库里已有同名表导致恢复报错，先 `dropdb <db_name> && createdb <db_name>` 再恢复。
- 本地没有单独设置 `captcha` 表的话（表在第一次 init_db 时已建），以 `\dt` 实际结果为准；`entrypoint.sh` 会幂等补建缺的表。

## 4. 构建与启动

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

首次构建会拉取基础镜像并安装依赖，需要几分钟；之后普通重启 `docker compose -f deploy/docker-compose.yml up -d` 即可。

**国内服务器加速（可选）**：构建拉取 `python:3.12-slim` / `node:22-alpine` / `nginx:1.27-alpine` 都走 Docker Hub，建议先配置 registry 加速器（阿里云/腾讯云都有免费加速地址，写入 `/etc/docker/daemon.json` 后 `systemctl restart docker`）；构建容器内 pip / pnpm 下载依赖慢时，按 `deploy/backend/Dockerfile` 与 `deploy/nginx/Dockerfile` 中的注释切换国内镜像源。

查看状态：

```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f backend
```

## 5. 启动验证清单（服务器执行）

```bash
# 1. nginx 直接服务静态首页
curl -s http://127.0.0.1/ | head -20

# 2. /api 反代 → 后端健康检查（公开接口，无需 token）
curl -s http://127.0.0.1/api/health

# 3. 验证码接口（公开）
curl -s http://127.0.0.1/api/auth/captcha | head -c 200

# 4. 容器状态：两个服务都是 running / healthy
docker compose -f deploy/docker-compose.yml ps
```

然后浏览器访问 `http://<服务器IP>/`：登录页应正常显示验证码图片；登录后应能创建会话并**流式**收到聊天回答（token 逐字出现说明 SSE 反代正常）。

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

## 7. HTTPS 证书（域名已解析到服务器后）

用 acme.sh 的 webroot 模式（不中断 nginx）：

```bash
curl https://get.acme.sh | sh
~/.acme.sh/acme.sh --issue -d creative-idea-generator.site \
  -d www.creative-idea-generator.site \
  -w /var/www/html

# webroot 目录：nginx 容器内是 /usr/share/nginx/html，宿主机上先建目录，
# 并在 nginx 配置 80 块临时加 location ^~ /.well-known/acme-challenge/
# { alias /var/www/html/.well-known/acme-challenge/; } 后 reload。
# 或者用 DNS API 验证（不需要动 nginx），推荐：
# ~/.acme.sh/acme.sh --issue -d creative-idea-generator.site --dns dns_ali
```

签好后：

1. compose 中取消 nginx 的证书卷挂载注释：
   `- /root/.acme.sh/creative-idea-generator.site_ecc:/etc/nginx/certs:ro`
   （acme.sh 默认目录；用 `--cert-home` 自定义过则按实际路径）
2. `deploy/nginx/nginx.conf`：取消 443 server 块注释，并在 80 块加
   `return 301 https://$host$request_uri;`
3. 重启：`docker compose -f deploy/docker-compose.yml up -d --build nginx`
4. 证书续期：acme.sh 默认自动续期，续期后执行
   `docker compose -f deploy/docker-compose.yml exec nginx nginx -s reload`
   （或写进 acme.sh 的 `--reloadcmd`）

## 8. 更新发布

```bash
cd statistics_of_china
git pull   # 或重新上传代码
docker compose -f deploy/docker-compose.yml up -d --build
```

- 后端镜像因依赖声明层缓存，普通代码改动重建很快（只重新 COPY 代码层）。
- 前端改动会重新触发 `pnpm build`，耗时较长，属正常。
- 若改了 `backend/pyproject.toml` 依赖，build 阶段会自动重装。
- 数据库结构有变化时，`entrypoint.sh` 里的 `init_db`（create_all）只会**新建缺失的表**，不会改已有表结构；需要加列/改列时先手工在服务器 PG 执行迁移 SQL，再更新代码。

## 9. 故障排查

| 现象 | 排查 |
| --- | --- |
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
