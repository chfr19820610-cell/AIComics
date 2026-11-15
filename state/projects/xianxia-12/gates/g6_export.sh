#!/usr/bin/env bash
# G6 导出门：成片存在 + 有视频轨 + 有音频轨
set -uo pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
FFMPEG=$(command -v ffmpeg)
fail=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  f="$D/assets/$ep/${ep}_H3_REAL.mp4"
  [ -s "$f" ] || { echo "FAIL $ep: 成片缺失"; fail=1; continue; }
  info=$("$FFMPEG" -hide_banner -i "$f" 2>&1)
  has_v=$(echo "$info" | grep -c "Stream.*Video:")
  has_a=$(echo "$info" | grep -c "Stream.*Audio:")
  res=$(echo "$info" | grep -oE 'yuv[0-9a-z]+\([a-z]+\), [0-9]+x[0-9]+' | head -1 | grep -oE '[0-9]+x[0-9]+$')
  dur=$(echo "$info" | grep -oE 'Duration: [0-9:.]+' | head -1 | sed 's/Duration: //')
  [ "$has_v" -lt 1 ] && { echo "FAIL $ep: 无视频轨"; fail=1; continue; }
  [ "$has_a" -lt 1 ] && { echo "FAIL $ep: 无音频轨"; fail=1; continue; }
  sz=$(ls -lh "$f" | awk '{print $5}')
  echo "PASS $ep: $sz / $res / $dur / v+a"
done
[ $fail -eq 0 ] && echo "=== G6 导出门: PASS ===" || echo "=== G6 导出门: FAIL ==="
exit $fail
