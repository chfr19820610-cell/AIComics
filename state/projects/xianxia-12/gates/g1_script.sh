#!/usr/bin/env bash
# G1 剧本门：四表一纲齐全 + 钩子存在 + 时长合法
set -uo pipefail
PY=/Users/eric/Desktop/hermes/AlComics/.venv/bin/python
D=$(cd "$(dirname "$0")/.." && pwd)
fail=0
for ep in E01 E02 E03 E04 E05 E06 E07 E08 E09 E10 E11 E12; do
  f="$D/scripts/$ep.json"
  [ -f "$f" ] || { echo "FAIL $ep: 缺少 scripts/$ep.json"; fail=1; continue; }
  $PY - "$f" "$ep" <<'PY' || fail=1
import json,sys
p,ep=sys.argv[1],sys.argv[2]
d=json.load(open(p))
req=["outline","act_table","scene_table","character_table","hook_table","dialogue_table"]
miss=[k for k in req if k not in d]
if miss: print(f"FAIL {ep}: 缺四表一纲 {miss}"); sys.exit(1)
if not d["hook_table"]["opening_hook"]["description"]:
    print(f"FAIL {ep}: 开头钩子为空"); sys.exit(1)
if not d["hook_table"]["ending_hook"]["description"]:
    print(f"FAIL {ep}: 结尾钩子为空"); sys.exit(1)
if d["outline"]["shot_count"] != 6:
    print(f"FAIL {ep}: 镜数 {d['outline']['shot_count']} != 6"); sys.exit(1)
print(f"PASS {ep}: 6镜/{len(d['dialogue_table'])}台词/钩子OK")
PY
done
[ $fail -eq 0 ] && echo "=== G1 剧本门: PASS ===" || echo "=== G1 剧本门: FAIL ==="
exit $fail
