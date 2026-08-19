#!/usr/bin/env bash
# =============================================================================
# AIComics ComfyUI 真实 runtime 一键安装脚本
# -----------------------------------------------------------------------------
# 把 local_providers/comfyui_runtime/ComfyUI 从「stub（仅 README）」变成
# 「真实可出图的 ComfyUI runtime」，并做真出图验证。
#
# 用法：
#   bash scripts/install_comfyui_runtime.sh                  # 在线克隆(默认)
#   bash scripts/install_comfyui_runtime.sh --clone          # 在线克隆(显式)
#   bash scripts/install_comfyui_runtime.sh --reuse /path/to/ComfyUI
#                                                           # 复用已装好的 ComfyUI
#   bash scripts/install_comfyui_runtime.sh --model anythingV5.safetensors
#                                                           # 指定要下载的模型
#   bash scripts/install_comfyui_runtime.sh --no-verify      # 装完不跑真出图
#   bash scripts/install_comfyui_runtime.sh --verify-only    # 仅对已装 runtime 出图
#
# 依赖：
#   - git、python3.12（或 3.11）
#   - 在线克隆需要能访问 github.com（联网前提）
#   - 真出图需要能访问 huggingface.co 下载模型权重（联网前提）
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT/local_providers/comfyui_runtime/ComfyUI"
VENV_DIR="$RUNTIME_DIR/.venv"
PORT="${AICOMIC_COMFYUI_PORT:-8188}"
HOST="${AICOMIC_COMFYUI_HOST:-127.0.0.1}"

MODE="clone"
REUSE_SRC=""
MODEL=""
VERIFY=true

usage() { sed -n '5,24p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

for arg in "$@"; do
  case "$arg" in
    --clone)          MODE="clone" ;;
    --reuse)          MODE="reuse" ;;
    --no-verify)      VERIFY=false ;;
    --verify-only)    MODE="verify" ;;
    --help|-h)        usage ;;
    --model)          echo "需指定 --model <权重文件名>"; exit 1 ;;
    --model=*)        MODEL="${arg#*=}" ;;
    --reuse=*)        REUSE_SRC="${arg#*=}"; MODE="reuse" ;;
    *) echo "未知参数: $arg"; usage ;;
  esac
done

log() { printf '[install-comfyui] %s\n' "$*"; }
fail() { printf '[install-comfyui] ✗ %s\n' "$*" >&2; exit 1; }

# ---- 校验 python 可用 ------------------------------------------------------
PY=""
for cand in python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || fail "未找到 python3.12/3.11/3"

# ---- verify-only：只跑真出图 --------------------------------------------------
if [ "$MODE" = "verify" ]; then
  log "verify-only 模式：对 $RUNTIME_DIR 做真出图验证"
  exec bash "$ROOT/scripts/validate_comfyui_real_image.sh" "$HOST" "$PORT"
fi

# ---- 安装 runtime -------------------------------------------------------------
if [ "$MODE" = "reuse" ]; then
  [ -n "$REUSE_SRC" ] || fail "--reuse 需要源路径，如 --reuse=/Users/me/ComfyUI"
  [ -d "$REUSE_SRC" ] || fail "源路径不存在: $REUSE_SRC"
  [ -f "$REUSE_SRC/main.py" ] || fail "源路径不是 ComfyUI 根目录(缺 main.py): $REUSE_SRC"
  log "复用现有 ComfyUI: $REUSE_SRC -> $RUNTIME_DIR"
  mkdir -p "$RUNTIME_DIR"
  # 用软链让 runtime 指向真实安装，避免整目录拷贝
  rm -f "$RUNTIME_DIR/main.py" 2>/dev/null || true
  if [ ! -e "$RUNTIME_DIR/main.py" ]; then
    ln -s "$REUSE_SRC/main.py" "$RUNTIME_DIR/main.py"
  fi
  if [ ! -e "$RUNTIME_DIR/models" ]; then
    ln -s "$REUSE_SRC/models" "$RUNTIME_DIR/models"
  fi
  if [ -f "$REUSE_SRC/requirements.txt" ] && [ ! -e "$RUNTIME_DIR/requirements.txt" ]; then
    ln -s "$REUSE_SRC/requirements.txt" "$RUNTIME_DIR/requirements.txt"
  fi
else
  if [ -e "$RUNTIME_DIR/main.py" ]; then
    log "已存在 main.py，跳过克隆（如需重装请先删除 $RUNTIME_DIR）"
  else
    log "克隆 ComfyUI 到 $RUNTIME_DIR ..."
    mkdir -p "$(dirname "$RUNTIME_DIR")"
    if [ -d "$RUNTIME_DIR/.git" ]; then
      log "已有 .git，执行 git pull"
      (cd "$RUNTIME_DIR" && git pull --ff-only)
    else
      git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$RUNTIME_DIR"
    fi
  fi
fi

# ---- venv + 依赖 -------------------------------------------------------------
if [ ! -x "$VENV_DIR/bin/python" ]; then
  log "创建 venv: $VENV_DIR"
  "$PY" -m venv "$VENV_DIR"
fi

# reuse 模式下：若源 ComfyUI 已有可用 venv，直接复用其解释器，避免重装 torch（体积大且需联网）
if [ "$MODE" = "reuse" ] && [ -x "$REUSE_SRC/.venv/bin/python" ]; then
  log "复用源 venv: $REUSE_SRC/.venv/bin/python"
  # 用源 venv 的 python 替代新建空 venv 的 python
  ln -sf "$REUSE_SRC/.venv/bin/python" "$VENV_DIR/bin/python" 2>/dev/null || \
    cp "$REUSE_SRC/.venv/bin/python" "$VENV_DIR/bin/python" 2>/dev/null || true
  log "已复用源 venv，跳过 torch 重装"
else
  log "安装 ComfyUI requirements (torch 等，体积较大，需联网 PyPI)..."
  "$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
  "$VENV_DIR/bin/python" -m pip install -r "$RUNTIME_DIR/requirements.txt" --no-cache-dir
fi

# ---- 模型权重 -----------------------------------------------------------------
if [ -n "$MODEL" ]; then
  dest="$RUNTIME_DIR/models/checkpoints/$MODEL"
  if [ -f "$dest" ]; then
    log "模型已存在: $MODEL"
  else
    log "下载模型 $MODEL -> $dest (需访问 huggingface.co)..."
    mkdir -p "$(dirname "$dest")"
    # 常见 SD1.5 的直达下载 URL
    url="https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors"
    case "$MODEL" in
      anythingV5.safetensors)  url="https://huggingface.co/Linaqruf/anything-v3.0/resolve/main/anything-v3-0.safetensors";;
      v1-5-pruned-emaonly.safetensors) url="https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5/resolve/main/v1-5-pruned-emaonly.safetensors";;
    esac
    curl -L --fail --retry 3 -o "$dest" "$url"
    log "模型下载完成: $MODEL"
  fi
else
  log "未指定 --model，跳过模型下载（真出图需 checkpoints 下有模型）"
fi

log "runtime 安装完成: $RUNTIME_DIR"
[ -f "$RUNTIME_DIR/main.py" ] || fail "runtime 缺少 main.py，安装失败"

# ---- 真出图验证 ------------------------------------------------------------------
if $VERIFY; then
  log "启动 ComfyUI 服务并做真出图验证 ..."
  exec bash "$ROOT/scripts/validate_comfyui_real_image.sh" "$HOST" "$PORT"
else
  log "跳过真出图验证 (--no-verify)"
fi
