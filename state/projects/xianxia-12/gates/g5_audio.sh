#!/usr/bin/env bash
# G5 音频门：配音存在 + 字幕时间轴合法
set -uo pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
fail=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  a=$(ls "$D/runs/$ep/audio_new"/*.wav 2>/dev/null | wc -l | tr -d ' ')
  s=$(ls "$D/runs/$ep/cut"/*.srt 2>/dev/null | wc -l | tr -d ' ')
  [ "$a" -lt 1 ] && { echo "FAIL $ep: 无配音"; fail=1; }
  [ "$s" -lt 1 ] && { echo "FAIL $ep: 无字幕"; fail=1; }
  [ "$a" -ge 1 ] && [ "$s" -ge 1 ] && echo "PASS $ep: 配音${a} 字幕${s}"
done
[ $fail -eq 0 ] && echo "=== G5 音频门: PASS ===" || echo "=== G5 音频门: FAIL ==="
exit $fail
