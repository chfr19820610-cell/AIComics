#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_ROOT="${PROJECT_ROOT}/web/frontend"
LOG_DIR="${PROJECT_ROOT}/logs/local_web_stack"
STATE_DIR="${PROJECT_ROOT}/state/tmp/local_web_stack"

BACKEND_PORT="${AICOMIC_LOCAL_BACKEND_PORT:-7861}"
FRONTEND_PORT="${AICOMIC_LOCAL_FRONTEND_PORT:-8001}"
BACKEND_HOST="${AICOMIC_LOCAL_BACKEND_HOST:-127.0.0.1}"
FRONTEND_HOST="${AICOMIC_LOCAL_FRONTEND_HOST:-127.0.0.1}"
BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
FRONTEND_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}"
WEB_CONFIG_PATH="${AICOMIC_WEB_CONFIG_PATH:-${PROJECT_ROOT}/config/web.development.yaml}"
BACKEND_PID_FILE="${STATE_DIR}/backend.pid"
FRONTEND_PID_FILE="${STATE_DIR}/frontend.pid"

mkdir -p "${LOG_DIR}" "${STATE_DIR}"

print_usage() {
  cat <<EOF
Usage: $(basename "$0") <up|down|restart|status|logs>

Defaults:
  backend:  ${BACKEND_URL}
  frontend: ${FRONTEND_URL}
  config:   ${WEB_CONFIG_PATH}

Environment overrides:
  AICOMIC_LOCAL_BACKEND_PORT
  AICOMIC_LOCAL_FRONTEND_PORT
  AICOMIC_LOCAL_BACKEND_HOST
  AICOMIC_LOCAL_FRONTEND_HOST
  AICOMIC_WEB_CONFIG_PATH
  AICOMIC_NORMAL_USER_PASSWORD
  AICOMIC_PYTHON_BIN

Examples:
  scripts/manage_local_web_stack.sh up
  scripts/manage_local_web_stack.sh status
  scripts/manage_local_web_stack.sh logs
  scripts/manage_local_web_stack.sh down
EOF
}

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

resolve_npm_bin() {
  local candidate
  for candidate in npm npm.cmd; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      command -v "${candidate}"
      return 0
    fi
  done
  return 1
}

launch_detached() {
  local workdir="$1"
  local stdout_log="$2"
  local stderr_log="$3"
  local env_json="$4"
  shift 4
  local python_bin
  python_bin="$(resolve_python_bin)"
  "${python_bin}" - "$workdir" "$stdout_log" "$stderr_log" "$env_json" "$@" <<'PY'
import json
import os
import subprocess
import sys

workdir = sys.argv[1]
stdout_log = sys.argv[2]
stderr_log = sys.argv[3]
env_overrides = json.loads(sys.argv[4])
command = sys.argv[5:]
env = os.environ.copy()
env.update(env_overrides)

with open(stdout_log, "ab") as stdout, open(stderr_log, "ab") as stderr, open(os.devnull, "rb") as stdin:
    process = subprocess.Popen(
        command,
        cwd=workdir,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
        close_fds=True,
    )
print(process.pid)
PY
}

load_local_password() {
  if [[ -n "${AICOMIC_NORMAL_USER_PASSWORD:-}" ]]; then
    printf '%s\n' "${AICOMIC_NORMAL_USER_PASSWORD}"
    return 0
  fi

  local env_file="${PROJECT_ROOT}/.env.production.local"
  if [[ -f "${env_file}" ]]; then
    local value
    value="$(awk -F= '/^AICOMIC_NORMAL_USER_PASSWORD=/{sub(/^[^=]*=/, "", $0); print $0; exit}' "${env_file}")"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    if [[ -n "${value}" ]]; then
      printf '%s\n' "${value}"
      return 0
    fi
  fi

  return 1
}

port_pid() {
  local port="$1"
  lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

is_pid_running() {
  local pid="$1"
  [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null
}

read_pid_file() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    tr -d '[:space:]' < "${file}"
  fi
}

remove_pid_file_if_stale() {
  local file="$1"
  local pid
  pid="$(read_pid_file "${file}")"
  if [[ -n "${pid}" ]] && ! is_pid_running "${pid}"; then
    rm -f "${file}"
  fi
}

wait_for_http_ok() {
  local url="$1"
  local seconds="${2:-30}"
  local deadline=$((SECONDS + seconds))
  while (( SECONDS < deadline )); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_port() {
  local port="$1"
  local seconds="${2:-30}"
  local deadline=$((SECONDS + seconds))
  while (( SECONDS < deadline )); do
    if [[ -n "$(port_pid "${port}")" ]]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

stop_pid_file_process() {
  local file="$1"
  local pid
  pid="$(read_pid_file "${file}")"
  if [[ -n "${pid}" ]] && is_pid_running "${pid}"; then
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 1
    if is_pid_running "${pid}"; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
  fi
  rm -f "${file}"
}

stop_port_process() {
  local port="$1"
  local pid
  pid="$(port_pid "${port}")"
  if [[ -n "${pid}" ]]; then
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 1
    if is_pid_running "${pid}"; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
  fi
}

start_backend() {
  local python_bin password stdout_log stderr_log pid
  python_bin="$(resolve_python_bin)"
  password="$(load_local_password)" || {
    echo "Missing AICOMIC_NORMAL_USER_PASSWORD. Export it or set it in .env.production.local." >&2
    exit 1
  }

  stdout_log="${LOG_DIR}/backend.stdout.log"
  stderr_log="${LOG_DIR}/backend.stderr.log"

  if [[ -n "$(port_pid "${BACKEND_PORT}")" ]]; then
    echo "Backend port ${BACKEND_PORT} is already in use." >&2
    exit 1
  fi

  pid="$(launch_detached \
    "${PROJECT_ROOT}" \
    "${stdout_log}" \
    "${stderr_log}" \
    "{\"PYTHONPATH\":\"${PROJECT_ROOT}/src:${PROJECT_ROOT}\",\"AICOMIC_WEB_CONFIG_PATH\":\"${WEB_CONFIG_PATH}\",\"AICOMIC_NORMAL_USER_PASSWORD\":\"${password}\"}" \
    "${python_bin}" -m uvicorn web.backend.app:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}")"
  echo "${pid}" > "${BACKEND_PID_FILE}"

  wait_for_port "${BACKEND_PORT}" 30 || {
    echo "Backend failed to listen on ${BACKEND_URL}. Check ${stderr_log}." >&2
    exit 1
  }
  wait_for_http_ok "${BACKEND_URL}/api/health" 30 || {
    echo "Backend health check failed at ${BACKEND_URL}/api/health. Check ${stderr_log}." >&2
    exit 1
  }
}

start_frontend() {
  local npm_bin stdout_log stderr_log pid
  npm_bin="$(resolve_npm_bin)"
  stdout_log="${LOG_DIR}/frontend.stdout.log"
  stderr_log="${LOG_DIR}/frontend.stderr.log"

  if [[ -n "$(port_pid "${FRONTEND_PORT}")" ]]; then
    echo "Frontend port ${FRONTEND_PORT} is already in use." >&2
    exit 1
  fi

  pid="$(launch_detached \
    "${FRONTEND_ROOT}" \
    "${stdout_log}" \
    "${stderr_log}" \
    "{\"UMI_APP_API_BASE_URL\":\"${BACKEND_URL}\"}" \
    "${npm_bin}" run dev -- --port "${FRONTEND_PORT}" --host "${FRONTEND_HOST}")"
  echo "${pid}" > "${FRONTEND_PID_FILE}"

  wait_for_port "${FRONTEND_PORT}" 60 || {
    echo "Frontend failed to listen on ${FRONTEND_URL}. Check ${stderr_log}." >&2
    exit 1
  }
  wait_for_http_ok "${FRONTEND_URL}/login" 60 || {
    echo "Frontend login page check failed at ${FRONTEND_URL}/login. Check ${stderr_log}." >&2
    exit 1
  }
}

status_json() {
  local backend_pid frontend_pid backend_port_pid frontend_port_pid backend_health frontend_login
  remove_pid_file_if_stale "${BACKEND_PID_FILE}"
  remove_pid_file_if_stale "${FRONTEND_PID_FILE}"

  backend_pid="$(read_pid_file "${BACKEND_PID_FILE}")"
  frontend_pid="$(read_pid_file "${FRONTEND_PID_FILE}")"
  backend_port_pid="$(port_pid "${BACKEND_PORT}")"
  frontend_port_pid="$(port_pid "${FRONTEND_PORT}")"
  backend_health="down"
  frontend_login="down"
  if curl -fsS "${BACKEND_URL}/api/health" >/dev/null 2>&1; then
    backend_health="ok"
  fi
  if curl -fsS "${FRONTEND_URL}/login" >/dev/null 2>&1; then
    frontend_login="ok"
  fi

  cat <<EOF
{
  "backend": {
    "url": "${BACKEND_URL}",
    "pid_file": "${BACKEND_PID_FILE}",
    "pid": "${backend_pid}",
    "listener_pid": "${backend_port_pid}",
    "health": "${backend_health}",
    "stdout_log": "${LOG_DIR}/backend.stdout.log",
    "stderr_log": "${LOG_DIR}/backend.stderr.log"
  },
  "frontend": {
    "url": "${FRONTEND_URL}",
    "pid_file": "${FRONTEND_PID_FILE}",
    "pid": "${frontend_pid}",
    "listener_pid": "${frontend_port_pid}",
    "health": "${frontend_login}",
    "stdout_log": "${LOG_DIR}/frontend.stdout.log",
    "stderr_log": "${LOG_DIR}/frontend.stderr.log",
    "api_base_url": "${BACKEND_URL}"
  }
}
EOF
}

up_action() {
  remove_pid_file_if_stale "${BACKEND_PID_FILE}"
  remove_pid_file_if_stale "${FRONTEND_PID_FILE}"

  if curl -fsS "${BACKEND_URL}/api/health" >/dev/null 2>&1 && curl -fsS "${FRONTEND_URL}/login" >/dev/null 2>&1; then
    echo "Local web stack is already running."
    status_json
    return 0
  fi

  if [[ -n "$(port_pid "${BACKEND_PORT}")" || -n "$(port_pid "${FRONTEND_PORT}")" ]]; then
    echo "One or more target ports are already occupied. Run 'down' first or free the ports." >&2
    exit 1
  fi

  start_backend
  start_frontend

  echo "Local web stack is ready."
  echo "Backend:  ${BACKEND_URL}"
  echo "Frontend: ${FRONTEND_URL}/creator?project_id=horror_real_sample_20260513015958"
  status_json
}

down_action() {
  stop_pid_file_process "${FRONTEND_PID_FILE}"
  stop_pid_file_process "${BACKEND_PID_FILE}"
  stop_port_process "${FRONTEND_PORT}"
  stop_port_process "${BACKEND_PORT}"
  echo "Local web stack stopped."
}

logs_action() {
  echo "== backend stdout =="
  tail -n 40 "${LOG_DIR}/backend.stdout.log" 2>/dev/null || true
  echo
  echo "== backend stderr =="
  tail -n 40 "${LOG_DIR}/backend.stderr.log" 2>/dev/null || true
  echo
  echo "== frontend stdout =="
  tail -n 40 "${LOG_DIR}/frontend.stdout.log" 2>/dev/null || true
  echo
  echo "== frontend stderr =="
  tail -n 40 "${LOG_DIR}/frontend.stderr.log" 2>/dev/null || true
}

ACTION="${1:-status}"

case "${ACTION}" in
  up)
    up_action
    ;;
  down)
    down_action
    ;;
  restart)
    down_action
    up_action
    ;;
  status)
    status_json
    ;;
  logs)
    logs_action
    ;;
  -h|--help|help)
    print_usage
    ;;
  *)
    echo "Unsupported action: ${ACTION}" >&2
    print_usage >&2
    exit 1
    ;;
esac
