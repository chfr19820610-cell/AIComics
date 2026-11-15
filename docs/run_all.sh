#!/usr/bin/env bash
# 一次跑全部 7 gate，输出总报告
set -uo pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
REPORT="$D/reports/GATE_REPORT.md"
mkdir -p "$D/reports"
{
echo "# Gate 验收报告"
echo ""
echo "> 生成时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "> 项目: xianxia-12（12 集 × 6 镜）"
echo ""
echo "| Gate | 结果 | 详情 |"
echo "|---|---|---|"
} > "$REPORT"
all_pass=1
for g in g1_script g2_asset g3_storyboard g4_generation g5_audio g6_export g7_compliance; do
  out=$(bash "$D/gates/$g.sh" 2>&1)
  rc=$?
  last=$(echo "$out" | grep -E "^=== G" | head -1)
  if [ $rc -eq 0 ]; then
    status="✅ PASS"
    if echo "$last" | grep -q "CONDITIONAL"; then status="⚠️ CONDITIONAL"; fi
  else
    status="❌ FAIL"; all_pass=0
  fi
  fails=$(echo "$out" | grep -c "^FAIL" || true)
  warns=$(echo "$out" | grep -c "^WARN" || true)
  echo "| $g | $status | FAIL=$fails WARN=$warns |" >> "$REPORT"
  printf "%-16s %s\n" "$g" "$status"
done
{
echo ""
echo "## 总结"
echo ""
if [ $all_pass -eq 1 ]; then
  echo "**7/7 gate 通过**（含 G7 的备案号软警告，需人工填 filing_no）"
else
  echo "**存在失败 gate，见上表**"
fi
echo ""
echo "## 已知软警告"
echo ""
echo "- G7 R7_filing_no：12 集备案号未填（如平台要求）"
echo "- 风格漂移：人像特写/群像镜仍会 Q 版化（模型能力边界，非 gate 问题）"
} >> "$REPORT"
cat "$REPORT"
[ $all_pass -eq 1 ] && exit 0 || exit 1
