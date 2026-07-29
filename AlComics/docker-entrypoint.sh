#!/bin/bash
#
# docker-entrypoint.sh — AIComics backend container entrypoint
#
# Modes:
#   serve   (default) Start the API server (uvicorn)
#   dev     Start with hot-reload for development
#   run     Execute a one-shot 3-layer agent pipeline
#   shell   Drop into a bash shell
#
set -euo pipefail

# ── Ensure required directories ────────────────
mkdir -p /app/{data,output,source_frames,audio,episodes,manifests,tasks,supervision,assets,outputs,temp}

# ── Validate critical env vars ──────────────────
if [[ -z "${AICOMICS_JWT_SECRET:-}" ]]; then
    echo "[ENTRYPOINT] ⚠️  AICOMICS_JWT_SECRET not set. Using default (insecure for production)."
fi

if [[ -z "${SEEDANCE_API_KEY:-}" ]] && [[ "${SEEDANCE_API_KEY:-}" != "«redacted:sk-…»" ]]; then
    echo "[ENTRYPOINT] ⚠️  SEEDANCE_API_KEY not set. Video generation will fail."
fi

# ── Display banner ─────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║     AIComics v2.0 · Production Pipeline  ║"
echo "╚═══════════════════════════════════════════╝"
echo "  OLLAMA:  ${OLLAMA_BASE_URL:-http://ollama:11434}"
echo "  COMFYUI: ${COMFY_URL:-http://comfyui:8188}"
echo "  WORKDIR: /app"
echo "  BACKEND: 0.0.0.0:${BACKEND_PORT:-8000}"
echo ""

# ── Command dispatch ───────────────────────────
CMD="${1:-serve}"

case "$CMD" in
    serve)
        echo "[ENTRYPOINT] Starting API server (uvicorn)..."
        exec python -m uvicorn backend.main:app \
            --host 0.0.0.0 \
            --port "${BACKEND_PORT:-8000}" \
            --log-level info \
            --no-access-log
        ;;
    dev)
        echo "[ENTRYPOINT] Starting dev server with hot-reload..."
        exec python -m uvicorn backend.main:app \
            --host 0.0.0.0 \
            --port "${BACKEND_PORT:-8000}" \
            --reload \
            --log-level debug
        ;;
    run)
        shift
        echo "[ENTRYPOINT] Running 3-layer pipeline: ./aicomic-3layer.sh $@"
        exec ./aicomic-3layer.sh "$@"
        ;;
    shell)
        exec /bin/bash
        ;;
    *)
        echo "[ENTRYPOINT] Unknown command: $CMD"
        echo "Usage: docker run aicomis [serve|dev|run|shell]"
        exit 1
        ;;
esac
