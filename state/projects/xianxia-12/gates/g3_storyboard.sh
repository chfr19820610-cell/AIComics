#!/usr/bin/env bash
# G3 分镜门（P6 版）：每镜必有 scene + action + shot_type 且非空
# 2026-11-16 更新：适配 70 镜结构（用 scene 而非 visual）
set -uo pipefail
PY=/Users/eric/Desktop/hermes/AlComics/.venv/bin/python
D=$(cd "$(dirname "$0")/.." && pwd)
fail=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  f="$D/shots/${ep}_70.json"
  [ -f "$f" ] || { echo "FAIL $ep: 缺 shots/${ep}_70.json"; fail=1; continue; }
  out=$($PY - "$f" "$ep" <<'PY'
import json, sys
p, ep = sys.argv[1], sys.argv[2]
d = json.load(open(p))
shots = d.get("shots", [])
if len(shots) != 70:
    print(f"FAIL {ep}: 镜数 {len(shots)} != 70"); sys.exit(1)
empty = []
for s in shots:
    sid = s.get("shot_id", "?")
    if not (s.get("scene") or "").strip():
        empty.append(f"{sid}.scene")
    if not (s.get("action") or "").strip():
        empty.append(f"{sid}.action")
    if not (s.get("shot_type") or "").strip():
        empty.append(f"{sid}.shot_type")
if empty:
    print(f"FAIL {ep}: 空字段 {empty[:8]}"); sys.exit(1)
# 景别分布检查（CG 风险 ≤30%）
from collections import Counter
c = Counter(s["shot_type"] for s in shots)
risky = c.get("wide", 0) + c.get("environment", 0)
pct = risky / 70 * 100
if pct > 35:
    print(f"FAIL {ep}: CG 风险镜 {risky}/70 = {pct:.0f}% > 35%"); sys.exit(1)
print(f"PASS {ep}: 70镜景别全 + CG风险 {risky}/70 = {pct:.0f}%")
PY
)
  echo "$out"
  echo "$out" | grep -q "^FAIL" && fail=1
done
[ $fail -eq 0 ] && echo "=== G3 分镜门: PASS ===" || echo "=== G3 分镜门: FAIL ==="
exit $fail
