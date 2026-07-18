#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DOCKER_BIN="${DOCKER_BIN:-docker}"

resolve_python_bin() {
  if [[ -n "${AICOMIC_PYTHON_BIN:-}" && -x "${AICOMIC_PYTHON_BIN}" ]]; then
    printf '%s\n' "${AICOMIC_PYTHON_BIN}"
    return 0
  fi

  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    printf '%s\n' "${PROJECT_ROOT}/.venv/bin/python"
    return 0
  fi

  local candidate
  for candidate in python3.12 python3 python; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      command -v "${candidate}"
      return 0
    fi
  done

  return 1
}

PYTHON_BIN="$(resolve_python_bin || true)"

if ! command -v "${DOCKER_BIN}" >/dev/null 2>&1; then
  if [[ -x /Applications/Docker.app/Contents/Resources/bin/docker ]]; then
    export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH}"
    DOCKER_BIN="docker"
  fi
fi

MODE="${1:-local}"
ACTION="${2:-up}"
USE_SIDECARS="${AICOMIC_USE_LOCAL_PROVIDER_SIDECARS:-1}"

case "${MODE}" in
  local)
    COMPOSE_FILES=(-f "${PROJECT_ROOT}/docker-compose.yml")
    if [[ "${USE_SIDECARS}" == "1" ]]; then
      COMPOSE_FILES+=(-f "${PROJECT_ROOT}/docker-compose.local-providers.yml")
    fi
    ;;
  production)
    COMPOSE_FILES=(-f "${PROJECT_ROOT}/docker-compose.production.yml")
    if [[ "${USE_SIDECARS}" == "1" ]]; then
      COMPOSE_FILES+=(-f "${PROJECT_ROOT}/docker-compose.production.local-providers.yml")
    fi
    ;;
  *)
    echo "Unsupported mode: ${MODE}" >&2
    exit 1
    ;;
esac

COMFYUI_BUILD_FLAG="--build"
if [[ "${MODE}" == "local" && "${USE_SIDECARS}" == "1" ]]; then
  if [[ -n "${PYTHON_BIN}" && -x "${PYTHON_BIN}" ]]; then
    if "${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/manage_comfyui_image_cache.py" ensure >/dev/null; then
      COMFYUI_BUILD_FLAG="--no-build"
    fi
  fi
fi

build_system_image_if_using_comfyui_cache() {
  if [[ "${COMFYUI_BUILD_FLAG}" == "--no-build" ]]; then
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" build aicomic-web
  fi
}

if [[ $# -ge 2 ]]; then
  shift 2
elif [[ $# -eq 1 ]]; then
  shift 1
fi

case "${ACTION}" in
  up)
    build_system_image_if_using_comfyui_cache
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" up -d "${COMFYUI_BUILD_FLAG}" "$@"
    ;;
  down)
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" down "$@"
    ;;
  restart)
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" down
    build_system_image_if_using_comfyui_cache
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" up -d "${COMFYUI_BUILD_FLAG}" "$@"
    ;;
  ps)
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" ps "$@"
    ;;
  logs)
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" logs "$@"
    ;;
  config)
    "${DOCKER_BIN}" compose "${COMPOSE_FILES[@]}" config "$@"
    ;;
  *)
    echo "Unsupported action: ${ACTION}" >&2
    exit 1
    ;;
esac
