# ───────────────────────────────────────────────
# AIComics v2.0 — Dockerfile
# Python 3.11-slim production image (backend service)
# ───────────────────────────────────────────────

FROM python:3.11-slim AS base

LABEL org.opencontainers.image.title="AIComics"
LABEL org.opencontainers.image.description="AI视觉小说/漫剧生产管线"
LABEL org.opencontainers.image.version="2.0"

# ── System Dependencies ────────────────────────
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
    ; \
    rm -rf /var/lib/apt/lists/*

# ── Python Environment ─────────────────────────
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application Code ───────────────────────────
# Core scripts
COPY seedance_client.py compose_video_seedance.py compose_video.py batch_generate.py ./
COPY render_shot.py make_ep4.py ./
COPY camera_presets.py cel_shader_setup.py lighting_presets.py ./

# 3-Layer Agent system
COPY aicomic-3layer.sh ./aicomic-3layer.sh
COPY agents/decision_agent.py agents/execution_agent.py agents/supervision_agent.py ./agents/

# Sub-agent copies (also at root for backward compat)
COPY decision_agent.py execution_agent.py supervision_agent.py ./

# Local providers (ComfyUI, Blender scripts)
COPY local_providers/ ./local_providers/

# Supporting files
COPY story-bible.md ./
COPY ep*.json ./
COPY episodes/ ./episodes/

# ── Backend API ────────────────────────────────
COPY backend/main.py ./backend/main.py

# ── Entrypoint ─────────────────────────────────
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh /aicomic-3layer.sh

# ── Runtime ────────────────────────────────────
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["serve"]

# ── Development Stage (optional) ────────────────
FROM base AS dev
RUN pip install --no-cache-dir watchdog
CMD ["dev"]
