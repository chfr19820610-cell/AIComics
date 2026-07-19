# ===== Stage 1: Builder =====
FROM python:3.12.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install build system
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy only dependency manifests first (leverage Docker layer caching)
COPY pyproject.toml requirements-lock.txt ./
COPY src/ src/

# Install all dependencies into a temporary location
RUN python -m pip install --no-cache-dir \
    --constraint requirements-lock.txt \
    --target /build/site-packages \
    -e ".[web,validation,local-providers]"

# ===== Stage 2: Runtime =====
FROM python:3.12.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AICOMIC_REQUIRE_FULL_DEPENDENCY_AUDIT=1
ENV PYTHONPATH=/app/src:/app:/build/site-packages

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /build/site-packages /build/site-packages

# Copy source code and runtime files
COPY pyproject.toml requirements-lock.txt ./
COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY web/ web/

# Create runtime directories
RUN mkdir -p reports state logs

CMD ["sh", "-lc", "python scripts/run_demo_validation.py && python scripts/validate_full_system_suite.py"]
