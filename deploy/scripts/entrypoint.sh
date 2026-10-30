#!/bin/sh
# 容器启动入口：幂等初始化（扩展 + 建表）后启动服务。
# PostgreSQL 已在宿主机运行，这里只做兜底，不会动已有数据。
set -e

echo "[entrypoint] checking pgvector extension..."
python - <<'PY'
from sqlalchemy import text
from backend.app.database.database import engine

with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
print("[entrypoint] vector extension ready")
PY

echo "[entrypoint] creating tables if absent..."
python -m backend.app.database.init_db

echo "[entrypoint] starting uvicorn on 127.0.0.1:8000"
exec uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
