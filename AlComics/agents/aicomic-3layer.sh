#!/bin/bash
# AIComics 三层Agent编排器
# 用法: aicomic-3layer.sh <script-path> [--max-rounds N] [--output DIR]
# 通过 sandbox-run.sh L2 运行各层Agent
set -euo pipefail

# === 路径 ===
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SANDBOX="$(cd "$BASE_DIR/.." && pwd)/sandbox-run.sh"

# === 参数 ===
SCRIPT_PATH=""
MAX_ROUNDS=3
OUTPUT_DIR="$BASE_DIR/output"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-rounds) MAX_ROUNDS="$2"; shift 2 ;;
    --output)     OUTPUT_DIR="$2"; shift 2 ;;
    -h|--help)    echo "用法: $0 <script-path> [--max-rounds N] [--output DIR]"; exit 0 ;;
    *)            SCRIPT_PATH="$1"; shift ;;
  esac
done
[ -n "$SCRIPT_PATH" ] || { echo "❌ 必须指定剧本路径"; exit 1; }

# === 准备 ===
mkdir -p "$OUTPUT_DIR"/{tasks,artifacts}
echo "╔════════════════════════════════════════╗"
echo "║  AIComics 三层Agent编排器              ║"
echo "╠════════════════════════════════════════╣"
echo "║  剧本: $SCRIPT_PATH"
echo "║  最大轮数: $MAX_ROUNDS"
echo "║  输出: $OUTPUT_DIR"
echo "╚════════════════════════════════════════╝"

# === 辅助函数 ===
run_agent() {
  local name="$1" script="$2" args="$3" tag="$4"
  local log="$OUTPUT_DIR/${name}-${tag}.log"
  printf "  [%-3s] %-12s ... " "$tag" "$name"
  if bash "$SANDBOX" L2 "cd /hermes/AlComics && python3 agents/$script $args" > "$log" 2>&1; then
    echo "✓"
    return 0
  else
    echo "✗ (exit $?)"
    tail -3 "$log" | sed 's/^/         /'
    return 1
  fi
}

read_verdict() {
  local file="$1"
  python3 -c "
import json
try:
    v = json.load(open('$file'))
    print(v.get('l2',{}).get('grade', '?'))
except: print('?')
" 2>/dev/null || echo "?"
}

clean_layer() {
  local layer="$1"
  case "$layer" in
    execution) rm -f "$OUTPUT_DIR/artifacts/"* "$OUTPUT_DIR/execution-log.json" ;;
    decision)  rm -f "$OUTPUT_DIR/tasks/"*.json "$OUTPUT_DIR/artifacts/"* "$OUTPUT_DIR/execution-log.json" "$OUTPUT_DIR/verdict-"*.json ;;
    supervision) rm -f "$OUTPUT_DIR/verdict-"*.json ;;
  esac
}

# === 编排循环 ===
FINAL_VERDICT="?"
NEXT_PHASE="decision"

for ROUND in $(seq 1 "$MAX_ROUNDS"); do
  echo ""
  echo "── Round $ROUND ──────────────────────────"

  # 决策层
  if [ "$NEXT_PHASE" = "decision" ]; then
    run_agent "decision" "decision_agent.py" "--script \"$SCRIPT_PATH\" --output \"$OUTPUT_DIR/tasks/tasklist.json\"" "r${ROUND}d" || { NEXT_PHASE="decision"; continue; }
    NEXT_PHASE="execution"
  fi

  # 执行层
  if [ "$NEXT_PHASE" = "execution" ]; then
    run_agent "execution" "execution_agent.py" \
      "--tasks \"$OUTPUT_DIR/tasks/tasklist.json\" --output-dir \"$OUTPUT_DIR/artifacts\" --log \"$OUTPUT_DIR/execution-log.json\"" \
      "r${ROUND}e" || { NEXT_PHASE="execution"; continue; }
    NEXT_PHASE="supervision"
  fi

  # 监督层
  if [ "$NEXT_PHASE" = "supervision" ]; then
    VERDICT_FILE="$OUTPUT_DIR/verdict-r${ROUND}.json"
    run_agent "supervision" "supervision_agent.py" \
      "\"$OUTPUT_DIR/artifacts\" --assets \"$OUTPUT_DIR/tasks\" --verdict \"$VERDICT_FILE\"" \
      "r${ROUND}s" || { NEXT_PHASE="supervision"; continue; }

    FINAL_VERDICT=$(read_verdict "$VERDICT_FILE")
    echo "  裁决: $FINAL_VERDICT"

    case "$FINAL_VERDICT" in
      A) echo "  ✅ 第 $ROUND 轮通过"; break ;;
      B) echo "  ↻ B-修复后继续 → 重跑执行层"
         clean_layer "execution"
         NEXT_PHASE="execution"
         ;;
      C) echo "  ⤴ C-退回执行层重做"
         clean_layer "execution"
         NEXT_PHASE="execution"
         ;;
      D) echo "  ⤵ D-退回决策层重规划"
         clean_layer "decision"
         NEXT_PHASE="decision"
         ;;
      *) echo "  ⚠ 未知裁决 $FINAL_VERDICT, 继续下一轮"
         clean_layer "decision"
         NEXT_PHASE="decision"
         ;;
    esac
  fi
done

# === 报告 ===
REPORT="$OUTPUT_DIR/report.json"
PASSED=false
[ "$FINAL_VERDICT" = "A" ] && PASSED=true
cat > "$REPORT" <<REPORTEOF
{
  "script": "$SCRIPT_PATH",
  "rounds": $ROUND,
  "max_rounds": $MAX_ROUNDS,
  "final_verdict": "$FINAL_VERDICT",
  "passed": $PASSED
}
REPORTEOF

echo ""
echo "╔════════════════════════════════════════╗"
if $PASSED; then
  echo "║  ✅ 最终裁决: 通过 ($ROUND/$MAX_ROUNDS 轮)   ║"
else
  echo "║  ❌ 最终裁决: 不通过 ($ROUND/$MAX_ROUNDS 轮) ║"
fi
echo "║  报告: $REPORT"
echo "╚════════════════════════════════════════╝"
