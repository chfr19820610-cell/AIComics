#!/usr/bin/env bash
# G4 生成门：每集 6 镜视频存在 + 分辨率合法（ffmpeg banner 兜底）
set -uo pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
FFMPEG=$(command -v ffmpeg)
fail=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  n=$(ls "$D/assets/$ep/h3video"/*.mp4 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -ne 6 ]; then echo "FAIL $ep: 镜数 $n != 6"; fail=1; continue; fi
  info=$("$FFMPEG" -hide_banner -i "$D/assets/$ep/h3video/${ep}_S01_h3.mp4" 2>&1)
  # 从 "Video: ... yuv420p(progressive), 512x384," 抓分辨率
  res=$(echo "$info" | grep -oE 'yuv[0-9a-z]+\([a-z]+\), [0-9]+x[0-9]+' | head -1 | grep -oE '[0-9]+x[0-9]+$')
  dur=$(echo "$info" | grep -oE 'Duration: [0-9:.]+' | head -1 | sed 's/Duration: //')
  if [ "$res" != "512x384" ]; then echo "FAIL $ep: 分辨率 $res != 512x384"; fail=1; continue; fi
  echo "PASS $ep: 6镜/${res}/${dur}"
done
[ $fail -eq 0 ] && echo "=== G4 生成门: PASS ===" || echo "=== G4 生成门: FAIL ==="
exit $fail
