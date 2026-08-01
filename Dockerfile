# =============================================================================
# AIComics 全栈镜像（后端 + 前端 dist 一体化）
# -----------------------------------------------------------------------------
# Stage 1: 构建前端 dist
# Stage 2: Python 后端运行时 + 拷贝前端产物
# 构建: docker compose -f docker-compose.yml build  (或 bash scripts/start.sh)
# =============================================================================
FROM node:18-alpine AS frontend-builder

WORKDIR /build
COPY web/frontend/package.json web/frontend/package-lock.json ./web/frontend/
# umijs 构建
RUN cd web/frontend && (npm ci || npm install) && npm run build

# -----------------------------------------------------------------------------
FROM python:3.12.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AICOMIC_REQUIRE_FULL_DEPENDENCY_AUDIT=1

WORKDIR /app

COPY . .

# 前端静态产物（Node 阶段构建结果）
COPY --from=frontend-builder /build/web/frontend/dist ./web/frontend/dist

RUN mkdir -p reports state logs \
    && python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --constraint requirements-lock.txt -e ".[web,validation,local-providers]"

ENV PYTHONPATH=/app/src:/app

CMD ["sh", "-lc", "python scripts/run_demo_validation.py && python scripts/validate_full_system_suite.py"]
