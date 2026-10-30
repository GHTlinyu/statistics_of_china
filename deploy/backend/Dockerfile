# 后端镜像：uv 多阶段构建（依赖层缓存 + 精简运行时）
#
# 构建上下文必须是仓库根目录（compose 里已配置 context: ..）。
# 运行时工作目录固定 /app：代码用 Path(__file__).parents[3] 锚定"仓库根/.env"，
# 容器内 .env 必须挂载到 /app/.env。
#
# 云服务器不需要预装 uv / Python：构建阶段在容器内用 pip 安装 uv，
# 最终镜像自带 .venv，宿主机唯一依赖是 Docker。
# 基础镜像走 Docker Hub（国内有 registry 加速器），不依赖 ghcr.io。

# ---------- 阶段一：安装依赖 ----------
FROM python:3.12-slim AS build

# 国内服务器拉取慢时，可给 pip 加镜像源：
#   RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# 只复制依赖声明，充分利用层缓存；依赖变更时才重装
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/

# uv 依赖走 PyPI，国内慢时可加 UV_DEFAULT_INDEX：
#   ENV UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
RUN uv sync --all-packages --frozen --no-dev

# ---------- 阶段二：运行时 ----------
FROM python:3.12-slim

# 日志时间与业务习惯一致（TIMESTAMPTZ 逻辑不受影响，仅日志展示）
ENV TZ=Asia/Shanghai
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV=/app/.venv \
    PYTHONUNBUFFERED=1

COPY --from=build /app/.venv /app/.venv
COPY backend/ backend/
COPY deploy/scripts/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
