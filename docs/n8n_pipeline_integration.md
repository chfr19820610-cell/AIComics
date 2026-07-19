# n8n Pipeline Integration — vf_master_loop Phase B Auto-Publish Enhancement

> Generated: 2026-07-19
> Status: Assessment complete
> Next: Implementation

---

## 1. Current State Analysis

### 1.1 vf_master_loop Phase B (as-is)

**File:** `scripts/vf_master_loop.py` — `phase_publish()` (line 838–845)

```python
def phase_publish():
    """检查发布包"""
    publish_dir = Path("/Users/eric/Desktop/herness/AI漫剧发布包")
    if publish_dir.exists():
        files = list(publish_dir.rglob("*"))
        log.info(f"发布包: {len(files)}个文件")
    else:
        log.info("暂无发布包")
```

- **Minimal:** only counts files, no actual publishing logic
- **Frequency:** runs every 8 cycles = 4 hours (`if cycle%8==0: phase_publish()`)
- **No platform dispatch:** no integration with social-auto-upload, xurl, or any publishing API

### 1.2 Existing AIComics Publish Infrastructure

| Component | Path | Purpose |
|-----------|------|---------|
| `status.json` | `10_System/status.json` | Tracks per-episode asset counts, review status (PASS/FAIL), publish timestamps |
| `aicomic.publish.publish_pack` | `src/aicomic/publish/publish_pack.py` | Builds platform-specific publish payloads (title candidates, platform copy for douyin/kuaishou/xiaohongshu/bilibili) |
| `aicomic.publish.dashboard` | `src/aicomic/publish/dashboard.py` | Builds production dashboard from validation reports |
| `aicomic.publish.season_summary` | `src/aicomic/publish/season_summary.py` | Season-level summary from scan/render manifests |
| `aicomic.publish.navigator` | `src/aicomic/publish/navigator.py` | Episode output navigator HTML |
| CLI commands | `aicomic.cli.main` | `build-publish-pack`, `enhance-publish-pack` |
| Reports | `reports/publish_draft_douyin.md` etc. | Per-platform publish drafts |

### 1.3 n8n Deployment (n8n-stack)

- **Running on:** `localhost:5678`
- **Auth:** Email `chfr19820610@gmail.com` / Password in password manager
- **Data dir:** Docker volume (no `~/.n8n` on host — runs via OrbStack/docker-compose)
- **Shared state:** `/Users/eric/Desktop/herness/n8n-stack/shared/status.json` (older copy, cycle 1)

### 1.4 Relevant n8n Workflows (18 total, 2 active)

| ID | Name | Active | Nodes | Purpose |
|----|------|--------|-------|---------|
| `8x1L1dQXr9BTlmzH` | 🎬 视频工厂-质量门禁发布管线 | ✅ **Yes** | 2 | Webhook → Log. Simple trigger |
| `arjPOxbTBdMgmtcN` | 🎬 视频工厂-质量门禁发布管线 | ❌ No | **7** | Schedule → Read status → Quality gate check → Distribute |
| `56LOcg6B5kVSkeQ4` | 🔄 内容4平台分发 | ❌ No | **12** | Webhook → Validate → AI Analysis → Platform gen (TW/LI/IG/FB) |
| `ZeSJSbwXI593H1Qj` | 📢 AI社媒放大器 | ❌ No | 26 | HN crawl → AI content → Multi-platform posting |
| `3a3GfgsbJ0sWwRVG` | 🏭 峰哥专属·AI内容工厂 | ✅ **Yes** | 5 | Webhook → Ollama prompt → respond |
| Others | (various) | ❌ No | — | HackerNews, Ollama tests, web scraper, etc. |

---

## 2. n8n Workflow Deep-Dive

### 2.1 Active: 🎬 视频工厂-质量门禁发布管线 (2-node)

```
Webhook触发 → 记录发布日志
```
- **Trigger:** Webhook (any POST)
- **Node 2:** Code node that logs incoming data
- **Status:** Active but **incomplete** — no real logic, just placeholder

### 2.2 Inactive: 🎬 视频工厂-质量门禁发布管线 (7-node — THE KEY WORKFLOW)

```
每30分钟检查 (scheduleTrigger, cron */30 * * * *)
  → 读取状态文件 (executeCommand: cat /data/shared/status.json)
    → 检查PASS待发布集 (Code: parses status.json, finds episodes with review.status=="PASS" and !published)
      → 需要发布? (IF node: _noop != true)
        ├── True → 调用分发Webhook (httpRequest POST → http://localhost:5678/webhook/flowscribe-lite)
        │            └→ 记录发布日志 (executeCommand: echo to quality-gate.log)
        └── False → 跳过记录 (executeCommand: echo "SKIP" to quality-gate.log)
```

**Issues:**
1. `status.json` path is `/data/shared/status.json` (Docker internal) — needs mapping to AIComics' actual `status.json`
2. `flowscribe-lite` webhook endpoint doesn't exist yet (no registered webhook)
3. The `jsCode` in the quality-gate node expects specific JSON schema
4. The distribution call is minimal (just passes episode name)

### 2.3 🔄 内容4平台分发 (12-node — Ideal Distribution Target)

```
Receive Content (webhook)
  → Validate Input (Code)
    → AI: Quick Analysis (OpenAI, JSON mode)
      → Merge Data (Code)
        → [Parallel] Generate: Twitter Thread (OpenAI)
        → [Parallel] Generate: LinkedIn Post (OpenAI)
        → [Parallel] Generate: Instagram Caption (OpenAI)
        → [Parallel] Generate: Facebook Post (OpenAI)
          → Collect Results (Code)
            → Save to Google Sheets
              → Respond: Success
```

**Status:** Inactive, needs OpenAI credential configured, could be reactivated as distribution target.

---

## 3. Integration Architecture

### 3.1 Proposed Pipeline

```
vf_master_loop Phase B
        │
        │ Python helper: build_publish_manifest.py
        │ Writes status.json, publish packs, triggers n8n webhook
        ▼
┌─────────────────────────────────────────────────┐
│  n8n: 🎬 视频工厂-质量门禁发布管线 (7-node)       │
│                                                   │
│  Schedule (every 30min)                           │
│    → Read AIComics status.json                    │
│    → Check episodes with review.status=="PASS"    │
│      AND published timestamp is old/new            │
│    → If ready: call distribution webhook           │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  n8n: flowscribe-lite webhook (NEW)             │
│                                                   │
│  Receives episode_code + publish_pack path        │
│    → Build platform-specific content              │
│    → Trigger social-auto-upload                   │
│    → Write publish_log.md                         │
│    → Update status.json (mark published)          │
└─────────────────────────────────────────────────┘
```

### 3.2 Option A: Enhance vf_master_loop Phase B (Recommended for MVP)

Replace the minimal `phase_publish()` with a Python helper that:

1. Reads `status.json` → finds episodes with `review.status == "PASS"` and not recently published
2. Runs `aicomic publish build-publish-pack` for each ready episode
3. Triggers n8n webhook with the publish pack payload
4. Optionally calls `social-auto-upload` directly for platform distribution

```python
def phase_publish():
    """验证完成的新资产 → 打包发布包 → 触发n8n发布管线"""
    status_path = BASE / "status.json"
    if not status_path.exists():
        log.info("暂无 status.json — 跳过发布")
        return

    import json
    status = json.loads(status_path.read_text())
    to_publish = []

    for ep_code, ep_data in status.get("episodes", {}).items():
        review = ep_data.get("review", {})
        if review.get("status") == "PASS":
            ts = ep_data.get("published")
            # Only publish if not yet published or >24h old
            if not ts:
                to_publish.append(ep_code)

    if not to_publish:
        log.info("没有待发布的剧集")
        return

    log.info(f"📦 待发布: {to_publish}")

    for ep in to_publish:
        # 1. Build publish pack
        manifest = BASE / "reports" / f"season_manifest.json"
        if manifest.exists():
            r = subprocess.run([
                str(VENV_PYTHON), "-m", "aicomic.cli.main",
                "build-publish-pack",
                "--episode-manifest", str(manifest),
                "--episode-code", ep,
            ], capture_output=True, text=True, timeout=60)

        # 2. Trigger n8n webhook with episode info
        pack_path = BASE / "reports" / f"publish_pack_{ep}.json"
        if pack_path.exists():
            try:
                import urllib.request
                payload = json.dumps({
                    "episode": ep,
                    "pack_path": str(pack_path),
                    "trigger": "vf_master_loop_phase_b",
                    "timestamp": datetime.now().isoformat(),
                }).encode()
                req = urllib.request.Request(
                    "http://localhost:5678/webhook/quality-gate-trigger",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
                log.info(f"  → n8n webhook triggered for {ep}")
            except Exception as e:
                log.warning(f"  ⚠ n8n webhook failed for {ep}: {e}")

        # 3. Update status.json with publish timestamp
        status["episodes"][ep]["published"] = datetime.now().isoformat()
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2))

    log.info(f"✅ 发布: {len(to_publish)} 集")
```

### 3.3 Option B: Fully n8n-Driven Pipeline (Recommended for Production)

**Step 1:** Fix the inactive 7-node quality-gate workflow

| Change | Details |
|--------|---------|
| `status.json` path | Mount `/Users/eric/Desktop/herness/AIComics/10_System/status.json` into Docker or use `executeCommand` with local path |
| `flowscribe-lite` webhook | Create a new n8n webhook workflow that receives episode data and dispatches to platforms |
| Schedule | Change from every 30min to every 4h (align with `phase_publish` cycle) |

**Step 2:** Create the `flowscribe-lite` distribution webhook

This webhook receives episode data and:
- Calls `social-auto-upload` for Douyin/Bilibili/Xiaohongshu
- Saves publish records to `publish_log.md`
- Sends Telegram notification

**Step 3:** Activate the 内容4平台分发 workflow for AI-generated social copy

The 12-node content distribution workflow can:
- Take episode metadata as input
- Generate platform-optimized copy (TW/LI/IG/FB) via OpenAI
- Save to Google Sheets for tracking

---

## 4. Implementation Roadmap

### Phase 1: Quick Wins (Day 1)
- [ ] Update `phase_publish()` in vf_master_loop.py to read `status.json` and trigger n8n webhook
- [ ] Create n8n webhook workflow `flowscribe-lite` that receives episode data and logs it
- [ ] Mount correct `status.json` path into n8n-stack Docker volume

### Phase 2: Quality Gate Pipeline (Day 2)
- [ ] Fix and activate the 7-node "质量门禁发布管线" workflow
- [ ] Fix the JS code in "检查PASS待发布集" to handle AIComics' `status.json` schema
- [ ] Wire the quality gate → distribution webhook flow
- [ ] Set up publish logging + Telegram notification

### Phase 3: Multi-Platform Distribution (Day 3)
- [ ] Activate "内容4平台分发" workflow with correct OpenAI credentials
- [ ] Integrate `social-auto-upload` CLI for Chinese platforms (Douyin/Bilibili/Xiaohongshu)
- [ ] Integrate `xurl` CLI for Twitter/X
- [ ] Add scheduled retry for failed platform posts

### Phase 4: Monitoring & Dashboard (Day 4+)
- [ ] Build n8n workflow dashboard with publish history
- [ ] Add dead letter queue for failed publishes
- [ ] Wire Telegram/WeChat notifications for publish events
- [ ] Metrics: publish success rate, platform reach

---

## 5. Key n8n API Endpoints for Automation

```bash
# Auth (get session cookie)
curl -c /tmp/n8n_cookies.txt \
  http://localhost:5678/rest/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"chfr19820610@gmail.com","password":"<password>"}'

# List all workflows
curl -b /tmp/n8n_cookies.txt http://localhost:5678/rest/workflows

# Get workflow detail (replace ID)
curl -b /tmp/n8n_cookies.txt http://localhost:5678/rest/workflows/{ID}

# Activate/deactivate workflow
curl -b /tmp/n8n_cookies.txt \
  http://localhost:5678/rest/workflows/{ID}/activate \
  -X POST

# Create webhook trigger (for flowscribe-lite)
# POST to /rest/workflows with workflow JSON

# Execute workflow via webhook
curl -X POST http://localhost:5678/webhook/{WEBHOOK_ID} \
  -H "Content-Type: application/json" \
  -d '{"episode":"E01"}'
```

---

## 6. n8n Template Assets Available

280+ templates available at `/Users/eric/Desktop/herness/n8n-templates/`, including:

| Category | Relevant Templates |
|----------|-------------------|
| **DevOps** | linux-update-via-webhook, docker-compose-controller |
| **WordPress** | Blog creation in brand voice, auto-tagging |
| **Discord** | AI-powered bot, YouTube summaries |
| **Social** | Multi-platform content distribution patterns |

---

## 7. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| status.json schema mismatch | Publishing skips episodes | Validate schema before activating workflow |
| n8n Docker volume can't read host paths | Can't read status.json | Use `executeCommand` with host binary, or bind-mount |
| social-auto-upload credentials expired | Platform publish fails | Check + refresh tokens before activating distribution |
| OpenAI API key not configured in n8n | AI content generation fails | Configure OpenAI credential in n8n settings |
| Workflow activation conflicts | Double-publish | Add dedup check in quality gate JS code |

---

## 8. Status.json Schema Reference

Current schema from `10_System/status.json`:

```json
{
  "cycle": 5,
  "time": "2026-07-19T15:12:54.403367",
  "episodes": {
    "E01": {
      "assets": {
        "images": 6, "audio": 6,
        "img_files": ["E01_S01_key.png", ...],
        "aud_files": ["E01_S01_tts.wav", ...],
        "img_total_kb": 6227,
        "aud_total_kb": 1479
      },
      "review": {
        "status": "PASS",          // PASS | FAIL | null
        "time": "...",
        "total_files": 12,
        "issues": []
      },
      "published": "2026-07-19T13:12:54.152865"  // null if not published
    }
  }
}
```

**Quality gate logic:** Episode qualifies for publishing when:
- `review.status == "PASS"`
- `published` is `null` OR older than 24 hours

---

## 9. Recommendations Summary

1. **Start with Phase 1** — Enhance `phase_publish()` in Python (Option A). It's the quickest path to value, requires no Docker volume changes, and keeps the logic with the codebase.

2. **Fix and activate** the 7-node quality-gate workflow as the secondary trigger path — it provides schedule-based publishing even when `vf_master_loop` isn't running.

3. **Create `flowscribe-lite`** webhook workflow as the distribution orchestrator, integrating with `social-auto-upload` and `xurl` CLIs.

4. **Reactivate "内容4平台分发"** once OpenAI credentials are confirmed in n8n settings.

5. **Dedup protection** — ensure the quality-gate JS code and `phase_publish()` both use the `published` timestamp to avoid double-publishing.
