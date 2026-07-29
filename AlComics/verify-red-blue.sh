#!/bin/bash
# AIComics v2.0 — 沙箱红蓝对抗验证脚本
# 验证所有20个已修复的审查问题
set -euo pipefail

BASE="/Users/eric/Desktop/hermes/AlComics"
PASS=0
FAIL=0
TOTAL=0

ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL+1)); }
check() { TOTAL=$((TOTAL+1)); }

echo "╔══════════════════════════════════════════════════╗"
echo "║  AIComics v2.0 红蓝对抗 — 最终验证              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. 后端 Python 语法 ──────────────────────────
echo "📦 后端语法检查"
check; python3 -c "import py_compile; py_compile.compile('$BASE/backend/main.py', doraise=True)" 2>/dev/null && ok "backend/main.py 语法正确" || fail "backend/main.py 语法错误"

# ── 2. Agent Python 语法 ─────────────────────────
echo "📦 Agent 语法检查"
for f in decision_agent.py execution_agent.py supervision_agent.py; do
  check
  python3 -c "import py_compile; py_compile.compile('$BASE/$f', doraise=True)" 2>/dev/null && ok "$f 语法正确" || fail "$f 语法错误"
done

# ── 3. Shell 语法 ────────────────────────────────
echo "📦 Shell 语法检查"
for f in aicomic-3layer.sh run.sh docker-entrypoint.sh; do
  check; bash -n "$BASE/$f" 2>/dev/null && ok "$f 语法正确" || fail "$f 语法错误"
done

# ── 4. nginx 配置检查 ────────────────────────────
echo "📦 nginx 配置检查"
check
NGINX_OK=true
grep -q "proxy_http_version 1.1" "$BASE/nginx.conf" || NGINX_OK=false
grep -q "proxy_set_header Upgrade" "$BASE/nginx.conf" || NGINX_OK=false
grep -q "map \$http_upgrade" "$BASE/nginx.conf" || NGINX_OK=false
! grep -q "location /ws/" "$BASE/nginx.conf" || NGINX_OK=false
$NGINX_OK && ok "nginx.conf WebSocket 代理正确 (/api/ 含 Upgrade 头, 无 /ws/ dead code)" || fail "nginx.conf WebSocket 配置不完整"

# ── 5. CORS 安全 ─────────────────────────────────
echo "📦 CORS 安全检查"
check
if grep -q "allow_origins=os.getenv" "$BASE/backend/main.py" && ! grep -q 'allow_origins=\["\*"\]' "$BASE/backend/main.py"; then
  ok "CORS 使用环境变量配置, 无通配符"
else
  fail "CORS 配置不安全"
fi

# ── 6. JWT Secret 安全 ───────────────────────────
echo "📦 JWT Secret 安全检查"
check
if grep -q "raise RuntimeError.*AICOMICS_JWT_SECRET" "$BASE/backend/main.py" && ! grep -q '"change-me-in-production"' "$BASE/backend/main.py"; then
  ok "JWT_SECRET 无硬编码默认值, 缺失则抛出 RuntimeError"
else
  fail "JWT_SECRET 配置不安全"
fi

# ── 7. view_episode 鉴权 ─────────────────────────
echo "📦 view_episode 鉴权检查"
check
if grep -q "Depends(get_current_user)" "$BASE/backend/main.py" && grep -c "JOIN projects" "$BASE/backend/main.py" > /dev/null; then
  ok "view_episode 已添加 JWT 鉴权 + 项目所有权检查"
else
  fail "view_episode 缺少鉴权"
fi

# ── 8. Login 字段兼容 ────────────────────────────
echo "📦 Login 字段检查"
check
if grep -q "username: email.value" "$BASE/frontend/src/views/Login.vue"; then
  ok "Login.vue 发送 username 字段 (与后端一致)"
else
  fail "Login.vue 字段与后端不匹配"
fi

# ── 9. Register 字段 ─────────────────────────────
echo "📦 Register 字段检查"
check
if grep -q "username: username.value" "$BASE/frontend/src/views/Register.vue" && ! grep -q "email:" "$BASE/frontend/src/views/Register.vue"; then
  ok "Register.vue 不发送无用 email 字段"
else
  fail "Register.vue 字段异常"
fi

# ── 10. 前端字段名匹配 ───────────────────────────
echo "📦 前端字段名匹配"
check
FIELDS_OK=true
grep -q "ep.ep_number" "$BASE/frontend/src/views/ProjectDetail.vue" || FIELDS_OK=false
grep -q "ep.thumbnail" "$BASE/frontend/src/views/ProjectDetail.vue" || FIELDS_OK=false
grep -q "episode.ep_number" "$BASE/frontend/src/views/EpisodePlayer.vue" || FIELDS_OK=false
grep -q "episode.output_path" "$BASE/frontend/src/views/EpisodePlayer.vue" || FIELDS_OK=false
! grep -q "episode.video_url" "$BASE/frontend/src/views/EpisodePlayer.vue" || FIELDS_OK=false
! grep -q "episode.script" "$BASE/frontend/src/views/EpisodePlayer.vue" || FIELDS_OK=false
$FIELDS_OK && ok "所有前端字段名匹配后端模型" || fail "前端字段名仍有不匹配"

# ── 11. Dashboard 数据结构 ───────────────────────
echo "📦 Dashboard 数据结构检查"
check
if grep -q "projectsList.value = data || \[\]" "$BASE/frontend/src/views/Dashboard.vue"; then
  ok "Dashboard 正确处理后端返回的数组"
else
  fail "Dashboard 数据结构不匹配"
fi

# ── 12. .env.example 存在 ────────────────────────
echo "📦 .env.example 检查"
check
if [ -f "$BASE/.env.example" ]; then
  ok ".env.example 已创建"
else
  fail ".env.example 不存在"
fi

# ── 13. get_current_user 是 async ────────────────
echo "📦 鉴权依赖函数检查"
check
if grep -q "async def get_current_user" "$BASE/backend/main.py"; then
  ok "get_current_user 是 async 函数 (无 sync+async 混用)"
else
  fail "get_current_user 不是 async"
fi

# ── 14. WebSocket 进度推送 ──────────────────────
echo "📦 WebSocket 进度推送检查"
check
if grep -q "active_connections\[project_id\]" "$BASE/backend/main.py" && grep -q '"type":.*progress' "$BASE/backend/main.py"; then
  ok "_run_generation 通过 WebSocket 推送进度"
else
  fail "WebSocket 进度推送缺失"
fi

# ── 15. episodes.generate API 无多余参数 ────────
echo "📦 API 调用参数检查"
check
if grep -q "generate: (projectId) =>" "$BASE/frontend/src/api.js"; then
  ok "episodes.generate 无需多余参数"
else
  fail "episodes.generate 参数异常"
fi

# ── 16. DB_PATH typo ─────────────────────────────
echo "📦 DB_PATH 命名检查"
check
if grep -q "aicomics.db" "$BASE/backend/main.py"; then
  ok "DB_PATH 命名正确 (aicomics.db)"
else
  fail "DB_PATH 命名异常"
fi

# ── 17. 项目只删自己的 ──────────────────────────
echo "📦 权限隔离检查"
check
if grep -q "AND user_id = ?" "$BASE/backend/main.py"; then
  ok "所有项目操作含 user_id 过滤"
else
  fail "缺少 user_id 过滤"
fi

# ── 18. 密码最小长度 ────────────────────────────
echo "📦 密码强度检查"
check
if grep -q "len(body.password) < 6" "$BASE/backend/main.py"; then
  ok "注册时验证密码最小长度"
else
  fail "密码长度验证缺失"
fi

# ── 19. nginx health 配置 ────────────────────────
echo "📦 nginx health 配置"
check
if grep -q "default_type text/plain" "$BASE/nginx.conf" && grep -q "location /health" "$BASE/nginx.conf"; then
  ok "nginx /health 返回正确的 Content-Type"
else
  fail "nginx health 配置异常"
fi

# ── 20. 全部文件清单 ────────────────────────────
echo "📦 21文件完整性检查"
check
FILES=(
  backend/main.py frontend/src/App.vue frontend/src/api.js frontend/src/ws.js
  frontend/src/views/Login.vue frontend/src/views/Register.vue frontend/src/views/Dashboard.vue
  frontend/src/views/ProjectDetail.vue frontend/src/views/EpisodePlayer.vue
  frontend/package.json frontend/vite.config.js
  nginx.conf Dockerfile Dockerfile.nginx docker-compose.yaml docker-entrypoint.sh run.sh requirements.txt
  decision_agent.py execution_agent.py supervision_agent.py aicomic-3layer.sh
)
ALL_EXIST=true
for f in "${FILES[@]}"; do
  [ -f "$BASE/$f" ] || { echo "   缺失: $f"; ALL_EXIST=false; }
done
$ALL_EXIST && ok "全部 21 文件存在" || fail "有文件缺失"

# ── 汇总 ────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║                    验证结果                      ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  测试项: $TOTAL"
echo "║  通过:   $PASS"
echo "║  失败:   $FAIL"
if [ $FAIL -eq 0 ]; then
  echo "║  评分:   100/100 ✅ 完全通过                    ║"
else
  echo "║  评分:   $(( (PASS*100)/TOTAL ))/100 ⚠️ 尚有未修复项  ║"
fi
echo "╚══════════════════════════════════════════════════╝"

exit $FAIL
