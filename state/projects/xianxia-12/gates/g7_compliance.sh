#!/usr/bin/env bash
# G7 合规门：compliance.json 存在 + AI 标识 + 备案号状态
set -uo pipefail
PY=/Users/eric/Desktop/hermes/AlComics/.venv/bin/python
D=$(cd "$(dirname "$0")/.." && pwd)
fail=0
warn=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  f="$D/runs/$ep/compliance.json"
  [ -f "$f" ] || { echo "FAIL $ep: 缺 compliance.json"; fail=1; continue; }
  out=$($PY - "$f" "$ep" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); ep=sys.argv[2]
r=d.get("rules",{})
hard=[k for k in ["R1_ai_label","R2_no_real_person","R4_no_sensitive","R6_bgm_license"] if not r.get(k,{}).get("pass")]
if hard: print(f"FAIL {ep}: 硬红线未过 {hard}"); sys.exit(1)
soft=[k for k,v in r.items() if not v.get("pass")]
if soft: print(f"WARN {ep}: 待补 {soft}"); sys.exit(2)
print(f"PASS {ep}: 全部红线通过")
PY
)
  rc=$?
  echo "$out"
  [ $rc -eq 1 ] && fail=1
  [ $rc -eq 2 ] && warn=1
done
if [ $fail -eq 1 ]; then echo "=== G7 合规门: FAIL ==="; exit 1
elif [ $warn -eq 1 ]; then echo "=== G7 合规门: CONDITIONAL PASS（有软警告）==="; exit 0
else echo "=== G7 合规门: PASS ==="; exit 0; fi
