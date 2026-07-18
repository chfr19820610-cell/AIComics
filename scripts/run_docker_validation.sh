#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
IMAGE_NAME="${AICOMIC_DOCKER_IMAGE:-aicomic-system-validation:local}"
RUN_ID="${AICOMIC_DOCKER_RUN_ID:-docker_validation_$(date +%Y%m%d%H%M%S)}"
LOG_PATH="${PROJECT_ROOT}/reports/${RUN_ID}.log"
DOCKER_BIN="${DOCKER_BIN:-docker}"

if ! command -v "${DOCKER_BIN}" >/dev/null 2>&1; then
  if [[ -x /Applications/Docker.app/Contents/Resources/bin/docker ]]; then
    export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH}"
    DOCKER_BIN="docker"
  fi
fi

mkdir -p "${PROJECT_ROOT}/reports" "${PROJECT_ROOT}/state" "${PROJECT_ROOT}/jobs"

{
  echo "RUN_ID=${RUN_ID}"
  echo "IMAGE_NAME=${IMAGE_NAME}"
  "${DOCKER_BIN}" build -f "${PROJECT_ROOT}/Dockerfile" -t "${IMAGE_NAME}" "${PROJECT_ROOT}"
  build_status=$?
  if [[ ${build_status} -ne 0 ]]; then
    echo "DOCKER_BUILD_STATUS=${build_status}"
    exit "${build_status}"
  fi

  "${DOCKER_BIN}" run --rm \
    -v "${PROJECT_ROOT}/reports:/app/reports" \
    -v "${PROJECT_ROOT}/state:/app/state" \
    -v "${PROJECT_ROOT}/jobs:/app/jobs" \
    "${IMAGE_NAME}" \
    sh -lc 'python scripts/run_demo_validation.py && python scripts/validate_full_system_suite.py'
  run_status=$?
  echo "DOCKER_RUN_STATUS=${run_status}"
  exit "${run_status}"
} 2>&1 | tee "${LOG_PATH}"

exit "${PIPESTATUS[0]}"
