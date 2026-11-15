#!/bin/bash
# P6 音画对齐批量生成：按 alignment.json 的精确 frames 生成
# 特性：先 TTS 定时长 → 按帧生成 → 字幕天然对齐 → 逐集合成
set -u

H3=/Users/eric/Desktop/hermes/tools/minimax-h3-stream-mac
D=/Users/eric/Desktop/hermes/AlComics/state/projects/xianxia-12
B=/Users/eric/Desktop/hermes/AlComics
PY=$B/.venv/bin/python
LOG=/tmp/p6_align.log

STYLE="2d anime, flat cel shading, bold black outlines, hand-drawn animation, Japanese anime style, xianxia wuxia, animation frames"
ANTI="serious tone, dramatic, not chibi, realistic proportional anatomy, mature anime proportions"

log() { echo "[$(date '+%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

main() {
  log "========== P6 音画对齐批量开始 =========="
  local done=0 fail=0

  for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
    log ""
    log "===== $ep 对齐准备 ====="
    local align="$D/runs/$ep/alignment.json"
    # 1) 生成对齐计划（已有则跳过，避免重复加载 TTS 模型 2m53s）
    if [ -f "$align" ]; then
      log "  ⏭ 对齐计划已存在，跳过 TTS 重算"
    else
      $PY "$B/scripts/align_episode.py" "$ep" --tts >> "$LOG" 2>&1
    fi
    if [ ! -f "$align" ]; then log "  ❌ $ep 对齐失败"; fail=$((fail+1)); continue; fi

    mkdir -p "$D/assets/$ep/h3video"
    local count=$($PY -c "import json;print(len(json.load(open('$align'))['plan']))")
    log "  $ep: $count 镜待生成"

    # 2) 按 alignment 的 frames 逐镜生成
    for i in $(seq 0 $((count-1))); do
      local row=$($PY -c "
import json
p=json.load(open('$align'))['plan'][$i]
pr=json.load(open('$D/prompts/${ep}_70_en.json'))
print(f\"{p['shot_id']}\t{p['frames']}\t{pr.get(p['shot_id'],'')}\")
" 2>/dev/null)
      local sid=$(echo "$row" | cut -f1)
      local frames=$(echo "$row" | cut -f2)
      local en=$(echo "$row" | cut -f3-)
      [ -z "$sid" ] && continue
      [ -z "$en" ] && { log "  ⚠️ $sid 无 prompt"; continue; }

      local out="$D/assets/$ep/h3video/${ep}_${sid}_h3.mp4"
      [ -s "$out" ] && { log "  ⏭ $sid 已有"; continue; }

      log "🎬 $ep/$sid frames=$frames ($((i+1))/$count)"
      cd "$H3" && .venv/bin/h3stream generate --model-dir models \
        --width 512 --height 384 --frames "$frames" --steps 8 \
        --i-understand-experimental \
        --prompt "$STYLE, $ANTI, $en" \
        --output "$out" --run-dir "runs/p6_${ep}_${sid}" >> "$LOG" 2>&1
      if [ -s "$out" ]; then
        done=$((done+1)); log "  ✅ $(du -h "$out" | cut -f1)"
      else
        fail=$((fail+1)); log "  ❌ 失败"
      fi
    done

    # 3) 合成
    log "===== $ep 合成 ====="
    $PY "$B/scripts/rebuild_episode.py" "$ep" >> "$LOG" 2>&1
    if [ -f "$D/runs/$ep/cut/final_r2.mp4" ]; then
      cp "$D/runs/$ep/cut/final_r2.mp4" "$D/assets/$ep/${ep}_H3_REAL.mp4"
      log "  ✅ 成片: assets/$ep/${ep}_H3_REAL.mp4"
    fi
  done

  log ""
  log "========== P6 结束: 成功 $done 失败 $fail =========="
}

main
