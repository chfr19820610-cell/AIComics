#!/usr/bin/env bash
# G1 剧本门（P6 版）：70 镜分镜表齐全 + 四幕结构 + 有台词 + 时长合法
# 2026-11-16 更新：适配 70 镜结构（旧版检查 scripts/$ep.json 的 6 镜四表一纲）
set -uo pipefail
PY=/Users/eric/Desktop/hermes/AlComics/.venv/bin/python
D=$(cd "$(dirname "$0")/.." && pwd)
fail=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  f="$D/shots/${ep}_70.json"
  [ -f "$f" ] || { echo "FAIL $ep: 缺少 shots/${ep}_70.json"; fail=1; continue; }
  $PY - "$f" "$ep" <<'PY' || fail=1
import json, sys
from collections import Counter
p, ep = sys.argv[1], sys.argv[2]
d = json.load(open(p))
shots = d.get("shots", [])

# 1) 镜数必须 70
if len(shots) != 70:
    print(f"FAIL {ep}: 镜数 {len(shots)} != 70"); sys.exit(1)

# 2) 必需字段齐全
req = ["shot_id", "shot_type", "scene", "action", "dialogue", "camera", "emotion", "duration", "act_id"]
miss = [k for k in req if any(k not in s for s in shots)]
if miss:
    print(f"FAIL {ep}: 缺字段 {miss}"); sys.exit(1)

# 3) 四幕结构（至少 3 种 act_id，理想 4 种）
acts = Counter(s["act_id"] for s in shots)
if len(acts) < 3:
    print(f"FAIL {ep}: 只有 {len(acts)} 幕（至少 3）：{dict(acts)}"); sys.exit(1)

# 4) 有台词（至少 8 句，P6 实测 5-23 句）
n_dial = sum(1 for s in shots if (s.get("dialogue") or "").strip())
if n_dial < 8:
    print(f"FAIL {ep}: 台词只有 {n_dial} 句 < 8"); sys.exit(1)

# 5) 时长合法（总时长 150-280 秒，允许 2.5-4.7 分钟）
total = sum(float(s.get("duration") or 0) for s in shots)
if not (150 <= total <= 280):
    print(f"FAIL {ep}: 总时长 {total:.1f}s 不在 150-280s"); sys.exit(1)

print(f"PASS {ep}: 70镜/{n_dial}台词/{len(acts)}幕/{total:.0f}s")
PY
done
[ $fail -eq 0 ] && echo "=== G1 剧本门: PASS ===" || echo "=== G1 剧本门: FAIL ==="
exit $fail
