#!/usr/bin/env bash
# =============================================================================
# AIComics 一键启动脚本
# -----------------------------------------------------------------------------
# 用法：
#   bash scripts/start.sh              # Docker 部署（推荐，含 ComfyUI sidecar）
#   bash scripts/start.sh --no-comfyui # Docker 部署，仅核心(web+frontend)
#   bash scripts/start.sh --local      # 裸机本地部署（python venv + uvicorn）
#   bash scripts/start.sh --production # 生产模式（docker-compose.production.yml）
#   bash scripts/start.sh --help
#
# 说明：
#   - 首次运行会自动从 .env.production.example 生成 .env.docker.local /
#     .env.production.local（若缺失），并补齐 local_providers/ 骨架。
#   - ComfyUI 图像运行时依赖真实 ComfyUI runtime，需自行放入
#     local_providers/comfyui/runtime/ComfyUI 后重建 sidecar 镜像。
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="docker"
WITH_COMFYUI=true

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

# ---- 参数解析 ---------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --local)      MODE="local" ;;
    --production) MODE="production" ;;
    --no-comfyui) WITH_COMFYUI=false ;;
    --help|-h)    usage ;;
    *) echo "未知参数: $arg"; usage ;;
  esac
done

# ---- 1. 环境文件（compose 依赖，缺失则从 example 生成）-------------------------
ensure_env() {
  local f="$1" src=".env.production.example"
  if [ ! -f "$f" ]; then
    echo "[start] 生成 $f (来自 $src)"
    cp "$src" "$f"
  else
    echo "[start] 已存在 $f"
  fi
}

# ---- 2. local_providers 骨架（sidecar 构建 COPY 源，缺失会导致 build 失败）------
ensure_local_providers() {
  local dir="local_providers/comfyui/runtime/ComfyUI"
  mkdir -p "$dir"
  if [ ! -f "$dir/README.md" ]; then
    cat > "$dir/README.md" <<'EOF'
# ComfyUI Runtime 占位

本目录用于放置 ComfyUI 运行时（含 SDXL 模型），供
`Dockerfile.comfyui-sidecar` 构建 sidecar 镜像使用。

- 镜像会执行 `COPY local_providers/comfyui/runtime/ComfyUI /opt/comfyui`，
  并把 `/opt/comfyui/requirements.txt` 装进 sidecar。
- 骨架保留为空时 sidecar 镜像仍可构建，但 ComfyUI 推理不可用（stub）。
- 若要启用真实推理，把完整 ComfyUI runtime 放到本目录后：
    docker compose -f docker-compose.local-providers.yml build aicomic-comfyui
EOF
    echo "[start] 生成 local_providers/ 骨架"
  fi
}

# ---- 3. 裸机本地部署 ----------------------------------------------------------
run_local() {
  ensure_env ".env.docker.local"

  echo "[start] 准备 Python 环境 (.venv)"
  python3.12 -m venv .venv 2>/dev/null || python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
  ./.venv/bin/python -m pip install --no-cache-dir --constraint requirements-lock.txt -e ".[web,validation,local-providers]" >/dev/null

  echo "[start] 构建前端 dist"
  (cd web/frontend && npm install >/dev/null && npm run build >/dev/null)

  echo "[start] 初始化演示数据库"
  PYTHONPATH="$ROOT/src:$ROOT" ./.venv/bin/python -m aicomic.cli.main init-demo-db || true

  echo "[start] 启动后端 :7860 与前端 :8000"
  PYTHONPATH="$ROOT/src:$ROOT" ./.venv/bin/python -m uvicorn web.backend.app:app --host 0.0.0.0 --port 7860 &
  BACKEND_PID=$!
  sleep 2
  PYTHONPATH="$ROOT/src:$ROOT" ./.venv/bin/python scripts/serve_frontend_spa.py --directory "$ROOT/web/frontend/dist" --host 0.0.0.0 --port 8000 &
  FRONTEND_PID=$!
  echo "[start] 已启动 backend(pid=$BACKEND_PID) frontend(pid=$FRONTEND_PID)"
  echo "[start] 访问 http://localhost:8000/login"
  trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM EXIT
  wait
}

# ---- 4. Docker 部署 -----------------------------------------------------------
run_docker() {
  local compose_file
  if [ "$MODE" = "production" ]; then
    compose_file="docker-compose.production.yml"
    ensure_env ".env.production.local"
  else
    compose_file="docker-compose.yml"
    ensure_env ".env.docker.local"
  fi
  ensure_local_providers

  # ComfyUI/Piper sidecar 以覆盖层方式叠加在基础 compose 上（docker-compose.local-providers.yml
  # 只声明 aicomic-web 的 depends_on/environment，必须与基础文件组合使用）
  local -a files=("-f" "$compose_file")
  if $WITH_COMFYUI && [ "$MODE" != "production" ]; then
    files+=("-f" "docker-compose.local-providers.yml")
  fi

  echo "[start] docker compose ${files[*]} build"
  docker compose "${files[@]}" build

  echo "[start] docker compose ${files[*]} up -d"
  docker compose "${files[@]}" up -d

  echo "[start] 完成。前端 http://localhost:8000/login   API http://localhost:7860/api/health"
}

case "$MODE" in
  local)       run_local ;;
  docker|production) run_docker ;;
esac
