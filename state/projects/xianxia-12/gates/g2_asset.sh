#!/usr/bin/env bash
# G2 资产门：bible 完整 + 角色数/场景数达标
set -uo pipefail
PY=/Users/eric/Desktop/hermes/AlComics/.venv/bin/python
D=$(cd "$(dirname "$0")/.." && pwd)
f="$D/assets/bible.json"
[ -f "$f" ] || { echo "FAIL: 缺少 assets/bible.json"; exit 1; }
$PY - "$f" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
ok=True
for k,minn in [("characters",6),("scenes",8),("props",3),("effects",3)]:
    n=len(d.get(k,[]))
    if n<minn: print(f"FAIL: {k} 只有 {n} < {minn}"); ok=False
    else: print(f"PASS: {k} {n}")
# 角色必须有 visual_anchor
for c in d.get("characters",[]):
    if not c.get("visual_anchor"): print(f"FAIL: 角色 {c.get('name')} 缺 visual_anchor"); ok=False
sys.exit(0 if ok else 1)
PY
rc=$?
[ $rc -eq 0 ] && echo "=== G2 资产门: PASS ===" || echo "=== G2 资产门: FAIL ==="
exit $rc
