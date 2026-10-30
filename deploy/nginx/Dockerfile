# nginx 镜像：阶段一在容器内构建前端 dist，阶段二承载静态 + 反代后端
#
# 构建上下文必须是仓库根目录（compose 里已配置 context: ..）。

# ---------- 阶段一：构建前端 ----------
FROM node:22-alpine AS frontend

RUN npm install -g pnpm@11

WORKDIR /app

# 先复制依赖声明利用层缓存，再复制前端源码
# .npmrc 带 npmmirror 源（npm / pnpm 共用），保证容器内下载依赖也走国内源
COPY .npmrc pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY frontend/ frontend/

RUN pnpm install --frozen-lockfile \
    && pnpm build

# ---------- 阶段二：nginx ----------
FROM nginx:1.27-alpine

COPY --from=frontend /app/frontend/dist /usr/share/nginx/html
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80 443
