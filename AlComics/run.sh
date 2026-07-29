#!/bin/bash
#
# run.sh — AIComics v2.0 一键启动
#
# Usage:
#   ./run.sh              # 默认启动所有服务 (docker compose up -d)
#   ./run.sh build        # 重新构建并启动
#   ./run.sh episode 01   # 执行EP01管线 (3层Agent)
#   ./run.sh logs         # 查看日志
#   ./run.sh stop         # 停止所有服务
#   ./run.sh cleanup      # 停止并清理数据卷
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 检查 .env ──────────────────────────────────
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        echo "⚠️  .env 不存在，从 .env.example 创建..."
        cp .env.example .env
        echo "📝 请编辑 .env 填入你的 API Key 后重新运行"
        echo "   关键变量: AICOMICS_JWT_SECRET, SEEDANCE_API_KEY"
        exit 0
    else
        echo "❌ .env 和 .env.example 都不存在"
        exit 1
    fi
fi

# ── 加载 .env 变量（用于端口显示）─────────────
set -a; source .env; set +a

# ── 命令路由 ────────────────────────────────────
CMD="${1:-up}"

case "$CMD" in
    up)
        echo "🚀 启动 AIComics 服务..."
        docker compose up -d
        echo ""
        echo "📌 服务地址:"
        echo "   AIComics Web:  http://localhost:${AICOMICS_PORT:-8080}"
        echo "   Backend API:   http://localhost:${AICOMICS_PORT:-8080}/api"
        echo "   Ollama:        http://localhost:${OLLAMA_PORT:-11434}"
        echo "   ComfyUI:       http://localhost:${COMFYUI_PORT:-8188}"
        echo ""
        echo "📋 查看日志:  ./run.sh logs"
        echo "🎬 执行管线:  ./run.sh episode 01"
        ;;
    build)
        echo "🔨 构建并启动..."
        docker compose up -d --build
        ;;
    episode)
        shift
        EP="${1:-01}"
        echo "🎬 执行 EP${EP} 管线..."
        docker compose exec -T backend ./aicomic-3layer.sh --episode "$EP"
        ;;
    logs)
        shift
        docker compose logs -f "$@"
        ;;
    stop)
        echo "🛑 停止服务..."
        docker compose down
        ;;
    cleanup)
        echo "🧹 停止并清理数据..."
        docker compose down -v
        echo "   已清除 volumes (ollama_data, comfyui_data, backend_data)"
        ;;
    *)
        echo "用法: $0 [up|build|episode|logs|stop|cleanup]"
        echo ""
        echo "  up         启动所有服务 (默认)"
        echo "  build      重新构建并启动"
        echo "  episode N  执行第N集管线 (如 episode 01)"
        echo "  logs       查看日志"
        echo "  stop       停止服务"
        echo "  cleanup    停止并清理数据"
        ;;
esac
