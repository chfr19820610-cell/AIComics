# AIComics 快速安全审计报告

> **审计日期**: 2026-07-19  
> **审计范围**: AIComics `/Users/eric/Desktop/herness/AIComics/10_System/`  
> **审计工具**: agent-security-guard (strix + security-penetration-tester)  
> **审计类型**: 快速安全扫描（静态分析）

---

## 审计清单

| # | 检查项 | 状态 | 风险等级 |
|---|--------|------|----------|
| 1 | 硬编码 API Key / 密码 / Token | ✅ 未发现 | — |
| 2 | .gitignore 保护敏感文件 | ⚠️ 缺失 | **中** |
| 3 | providers.yaml 暴露配置 | ⚠️ 部分风险 | **中** |
| 4 | Web 前端 XSS 风险 | ⚠️ 存在风险 | **高** |
| 5 | Python 依赖已知漏洞 | ✅ 版本较新 | — |
| 6 | 路径遍历防护 | ✅ 基本完善 | — |
| 7 | 命令注入防护 | ✅ 白名单安全 | — |
| 8 | CORS 配置 | ⚠️ 潜在风险 | **中** |
| 9 | 认证机制 | ⚠️ 中等风险 | **中** |

---

## 详细发现

### 1. 硬编码密钥 / Token / 密码 — ✅ 安全

- **JWT Secret**: 通过环境变量 `${AICOMIC_JWT_SECRET}` 注入，未硬编码 ✅
- **用户密码**: 通过环境变量 `${AICOMIC_NORMAL_USER_PASSWORD}` 注入，未硬编码 ✅
- **API Key**: Python 源码和前端源码中未发现硬编码的 API key、token 或密码
- **`.env` 文件**: 项目中不存在 `.env` 文件（但这也意味着环境变量需由外部提供）

### 2. .gitignore — ⚠️ 缺失（修复优先级：中）

| 问题 | 详情 |
|------|------|
| **未发现 .gitignore** | 项目根目录和 `10_System/` 目录下均无 `.gitignore` 文件 |
| **项目中无 Git 仓库** | 当前未初始化 Git，但一旦初始化，以下敏感文件会被跟踪： |
| **应忽略的文件** | `config/providers.yaml`、`config/web.yaml`、`state/`、`reports/`、`jobs/`、`local_providers/`、`__pycache__/`、`.env` |

**建议**: 在 `10_System/` 创建 `.gitignore`，至少包含：

```gitignore
# 敏感配置
config/providers.yaml
config/web.yaml
config/local_*.yaml

# 运行时状态
state/
jobs/

# 本地 Provider 资产
local_providers/

# 报告（可能包含内部路径信息）
reports/

# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/

# Node
node_modules/
dist/

# 环境变量
.env
.env.*
```

### 3. providers.yaml 暴露配置 — ⚠️ 部分风险（修复优先级：中）

| 文件 | `/Users/eric/Desktop/herness/AIComics/10_System/config/providers.yaml` |
|------|----------------------------------------------------------------------|
| **API Key** | ✅ 未包含任何 API Key 或密码 |
| **第三方端点** | ⚠️ 暴露了以下服务端点和基础设施信息： |
| | • `https://api.jieyouai.it.com/v1` — OpenAI 兼容 API 端点 |
| | • `https://ark.cn-beijing.volces.com` — 火山引擎端点 |
| | • `https://api.klingai.com` — Kling API 端点 |
| | • `http://127.0.0.1:8188` — 本地 ComfyUI 端点 |
| **本地路径** | ⚠️ 暴露了内部项目目录结构、模型路径和工作流 JSON 路径 |
| **Prompt 泄露** | ⚠️ negative_prompt 中包含了详细的文本过滤指令（可能暴露审核策略） |

**建议**: 
- 在 committed 版本中使用占位符 base_url，将实际端点注入为环境变量
- 生产部署时使用独立的 providers.production.yaml，不在版本控制中

### 4. Web 前端 XSS 风险 — ⚠️ 存在高危险度代码（修复优先级：高）

#### 静态预览前端 (static_preview/) — ⚠️ 高风险

文件 `login.js` 和 `main.js` 中大量使用 `innerHTML` 渲染 API 响应数据：

| 位置 | 代码片段 | 风险 |
|------|----------|------|
| `login.js:70` | `providerList.innerHTML = ... \`<li>${item.label}...</li>\`` | `${item.label}` 直接设为 innerHTML |
| `main.js:113-118` | `container.innerHTML = entries.map(...)` | `${label}`, `${value}` 直接渲染 |
| `main.js:123-125` | `container.innerHTML = items.map((item) => \`<li>${item}</li>\`)` | 任意 API 响应内容直接作为 HTML |
| `main.js:135-147` | `container.innerHTML = \`<table>...\`` | header 和值时通过模板字面量注入 |

**风险**: 如果 API 返回的数据中包含恶意 JS（如某个 shot 标题为 `<img src=x onerror=alert(1)>`），由于使用 `innerHTML` 而非 `textContent`/`innerText`，会直接执行恶意脚本。攻击者可窃取 localStorage 中的 JWT token。

#### React 前端 (frontend/) — ✅ 风险较低

使用 Ant Design 组件（无 `dangerouslySetInnerHTML` 或 `innerHTML` 用法），天然防御 XSS。

**建议**: 
- 将 `static_preview/` 中的 `innerHTML` 全部替换为 `textContent`
- 静态预览前端是遗留代码，建议尽快迁移到 React 前端，或增加 Content-Security-Policy header

### 5. Python 依赖已知漏洞 — ✅ 版本较新

文件 `requirements-lock.txt` 中所有依赖均已固定版本号，主要依赖版本较新：

| 依赖 | 版本 | 发布距今 | 备注 |
|------|------|----------|------|
| fastapi | 0.136.1 | 较新 | 主流版本 |
| starlette | 1.0.0 | 较新 | CVE 风险较低 |
| httpx | 0.28.1 | 较新 | ✅ |
| requests | 2.33.1 | 较新 | ✅ |
| pip-audit | 2.10.0 | 已包含审计工具 | ✅ |
| piper-tts | 1.4.2 | 较新 | ✅ |

**建议**: 定期运行 `pip-audit -r requirements-lock.txt` 检查已知 CVE。

### 6. 路径遍历防护 — ✅ 基本完善

`resolve_project_asset_path()` 在 `creator_review_service.py` 中使用了多层防护：

- `project_root.resolve()` + `candidate.relative_to(project_root.resolve())` 确保文件在项目根目录内
- 无效路径会触发 `ValueError("非法文件路径。")`
- 但参数来自 URL Query（`path`），虽经校验，仍需警惕

**建议**: 
- 在 URL 输入层增加路径字符黑名单（禁 `..`、`~`、绝对路径）
- 考虑使用 UUID 映射文件而非直接暴露路径

### 7. 命令注入防护 — ✅ 安全

`command_service.py` 使用严格的白名单机制：

- `settings.allowed_commands` — 白名单命令列表
- `settings.runnable_commands` — 可运行子集
- `command_execution_enabled` — 全局开关
- 使用 `subprocess.run([sys.executable, "-m", "aicomic.cli.main", command])`，**未使用 `shell=True`**，无 shell 注入风险
- 所有执行需 Web UI 显式确认

### 8. CORS 配置 — ⚠️ 潜在风险（修复优先级：中）

```python
# app.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins) if settings.cors_allow_origins != ("*",) else ["*"],
    allow_credentials=True,  # ⚠️ credentials + wildcard 不兼容
    allow_methods=["*"],
    allow_headers=["*"],
)
```

| 问题 | 风险 |
|------|------|
| `allow_credentials=True` | 当 origins=* 时，浏览器会忽略凭据（规范行为），但如果有具体 origin 则允许带凭据的跨域请求 |
| `settings.cors_allow_origins` 默认值来自 `server.cors_allow_origins`，未配置时回退为 `"*"` |
| `web.yaml` 中配置了具体域名 `https://aicomic.example.com`（placeholder） | 配置未验证 |

### 9. 认证机制 — ⚠️ 中等风险

| 发现 | 分析 |
|------|------|
| JWT 使用自签名 HS256 | 非标准库实现，但使用 `hmac.compare_digest` 防时序攻击 ✅ |
| 令牌存 localStorage | ❌ XSS 后可窃取。现代化实践应使用 httpOnly cookie |
| Refresh Token 7天有效期 | 合理 |
| 密码登录可暴力破解 | 无 rate limiting 或 account lockout 机制 |
| 审计日志 | ✅ 所有认证/操作均有 audit log |
| `/api/health` 泄露路径 | 返回 `project_root` 绝对路径，属于信息泄露 |

---

## 风险评级总结

| 风险等级 | 数量 | 关键项 |
|----------|------|--------|
| 🔴 **高** | 1 | 静态预览前端 innerHTML 导致的 XSS |
| 🟡 **中** | 4 | .gitignore 缺失、providers.yaml 配置文件暴露、CORS 配置、认证存储方式 |
| 🟢 **低** | 2 | 路径信息泄露、无 rate limiting |

## 紧急修复建议

### P0 — 立即修复

1. **修复 XSS 漏洞** — 将 `web/static_preview/main.js` 和 `web/static_preview/login.js` 中的所有 `innerHTML` 赋值为 `textContent`。具体：

   - `login.js:70`: 改为 `providerList.textContent = ...`
   - `login.js:71`: 改用 `createElement` + `textContent`
   - `main.js:113-118`, `main.js:123-125`, `main.js:135-147`: 同上

   或用 `insertAdjacentHTML` 配合显式转义（不推荐），最佳方案是使用 `textContent` 或 `createTextNode`。

### P1 — 一周内修复

2. **创建 .gitignore** — 在 `10_System/` 添加完整的 .gitignore（见上文）
3. **替换 providers.yaml 中的敏感值** — 将 base_url 等改为环境变量注入
4. **配置 CORS** — 确保 `cors_allow_origins` 在生产环境使用具体域名而非 `*`

### P2 — 规划修复

5. **将静态预览前端迁移至 React** — 或至少增加 CSP header
6. **添加 API rate limiting** — 登录端点应有限流
7. **health 端点去敏** — 不返回 `project_root` 绝对路径
8. **迁移令牌到 httpOnly cookie** — 避免 JavaScript 可读取

---

*本报告基于静态代码分析，未进行动态渗透测试。建议在部署前执行完整的安全评估（包括 SAST + DAST）。*
