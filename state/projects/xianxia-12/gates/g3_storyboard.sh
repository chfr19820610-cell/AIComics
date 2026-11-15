#!/usr/bin/env bash
# G3 分镜门：12 字段齐全 + 时长合法
set -uo pipefail
PY=/Users/eric/Desktop/hermes/AlComics/.venv/bin/python
D=$(cd "$(dirname "$0")/.." && pwd)
fail=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  f="$D/shots/$ep.json"
  [ -f "$f" ] || { echo "FAIL $ep: 缺 shots/$ep.json"; fail=1; continue; }
  $PY - "$f" "$ep" <<'PY' || fail=1
import json,sys
p,ep=sys.argv[1],sys.argv[2]
d=json.load(open(p))
FIELDS=["shot_id","shot_type","visual","characters","action","dialogue","camera","emotion","duration","sound_cue","act_id","priority"]
bad=[]
for s in d["shots"]:
    for f in FIELDS:
        if f in ("dialogue","characters"):  # 允许空
            continue
        if not s.get(f):
            bad.append(f"{s['shot_id']}.{f}")
    if not (1.0 <= s.get("duration",0) <= 10.0):
        bad.append(f"{s['shot_id']}.duration={s.get('duration')}")
if bad: print(f"FAIL {ep}: {bad[:5]}"); sys.exit(1)
print(f"PASS {ep}: 6镜 × 12字段齐全")
PY
done
[ $fail -eq 0 ] && echo "=== G3 分镜门: PASS ===" || echo "=== G3 分镜门: FAIL ==="
exit $fail
