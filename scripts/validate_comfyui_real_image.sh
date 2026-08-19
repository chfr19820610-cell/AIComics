#!/usr/bin/env bash
# =============================================================================
# AIComics ComfyUI 真出图验证
# -----------------------------------------------------------------------------
# 对 local_providers/comfyui_runtime/ComfyUI 做「真实出图」验证：
#   1) 若端口无服务则启动 ComfyUI server
#   2) 调用真实 ComfyUI API 生成一张 txt2img 图片
#   3) 校验 PNG 文件存在且可解码，输出报告到 reports/
#
# 用法：
#   bash scripts/validate_comfyui_real_image.sh [host] [port]
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${1:-127.0.0.1}"
PORT="${2:-8188}"
BASE_URL="http://$HOST:$PORT"
RUNTIME_DIR="$ROOT/local_providers/comfyui_runtime/ComfyUI"
OUT_DIR="$ROOT/state/comfyui_real_output"
REPORT_DIR="$ROOT/reports"
TS="$(date +%Y%m%d%H%M%S)"
REPORT="$REPORT_DIR/comfyui_real_image_$TS.json"

mkdir -p "$OUT_DIR" "$REPORT_DIR"

log() { printf '[comfyui-real] %s\n' "$*"; }
fail() { printf '[comfyui-real] ✗ %s\n' "$*" >&2; exit 1; }

# ---- 1. 启动服务（若未在跑）---------------------------------------------------
if ! curl -s -m 3 "$BASE_URL/system_stats" >/dev/null 2>&1; then
  log "端口 $PORT 无服务，尝试启动 $RUNTIME_DIR ..."
  [ -f "$RUNTIME_DIR/main.py" ] || fail "runtime 缺 main.py（请先运行 install_comfyui_runtime.sh）"
  VENV_PY="$RUNTIME_DIR/.venv/bin/python"
  [ -x "$VENV_PY" ] || VENV_PY="$(command -v python3 || command -v python)"
  ( cd "$RUNTIME_DIR" && nohup "$VENV_PY" main.py --listen "$HOST" --port "$PORT" --cpu >"$REPORT_DIR/comfyui_server_$TS.log" 2>&1 & )
  # 等待就绪（最多 180s）
  ready=0
  for i in $(seq 1 180); do
    if curl -s -m 3 "$BASE_URL/system_stats" >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
  done
  [ "$ready" = "1" ] || fail "ComfyUI 服务启动超时，日志见 $REPORT_DIR/comfyui_server_$TS.log"
fi

log "ComfyUI 服务已就绪: $BASE_URL"

# ---- 2. 真出图 ------------------------------------------------------------------
log "调用真实 ComfyUI API 生成图片 ..."
result="$("$ROOT/.venv/bin/python" "$ROOT/scripts/validate_comfyui_real_image.py" "$HOST" "$PORT" "$OUT_DIR" 2>&1)" || fail "$result"
echo "$result"
# 从 JSON 行提取保存路径
SAVED="$(echo "$result" | python3 -c "import sys,json; 
for line in sys.stdin:
    line=line.strip()
    if line.startswith('{'):
        try: print(json.loads(line)['saved']); break
        except Exception: pass" 2>/dev/null || true)"
[ -n "$SAVED" ] && [ -f "$SAVED" ] || fail "未找到出图产物"

# ---- 3. 校验 PNG -----------------------------------------------------------------
"$ROOT/.venv/bin/python" - "$SAVED" "$REPORT" <<'PYEOF'
import json, struct, sys
path, report = sys.argv[1], sys.argv[2]
data = open(path, "rb").read()
sig_ok = data[:8] == b"\x89PNG\r\n\x1a\n"
w = h = 0
if sig_ok:
    w, h = struct.unpack(">II", data[16:24])
ok = sig_ok and w > 0 and h > 0
payload = {
    "real_image_generation": True if ok else False,
    "output_path": path,
    "png_signature_ok": sig_ok,
    "width": w, "height": h,
    "bytes": len(data),
    "validated_at": __import__("datetime").datetime.now().astimezone().isoformat(),
}
open(report, "w").write(json.dumps(payload, ensure_ascii=False, indent=2))
print(json.dumps(payload, ensure_ascii=False))
sys.exit(0 if ok else 1)
PYEOF

log "✓ 真出图验证通过: $SAVED"
log "  报告: $REPORT"
