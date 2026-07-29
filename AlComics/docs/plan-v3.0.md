# AIComics v3.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Upgrade AIComics to a visible DAG Graph system with real-time dashboard

**Architecture:** Pure Python DAG engine + extended FastAPI backend + SVG-based Vue3 graph dashboard. All state is JSON-serializable. No external graph visualization libs.

**Tech Stack:** Python 3.11+ / FastAPI / Vue3+Vite+Tailwind / SQLite / SVG

## Global Constraints

- Files ≤400 lines each. No exceptions.
- All state JSON-serializable (no pickle)
- No new external dependencies (no vis libs, no heavy npm packages)
- Every file must pass red-blue review in sandbox
- Use `docker exec -w /workspace hermes-sandbox` for sandbox commands
- Verify all changes with `bash verify-red-blue.sh` before commit

---

### Task A: Graph Engine Fixes & Unit Tests

**Files:**
- Modify: `graph/engine.py`
- Create: `tests/test_graph_engine.py`
- Create: `tests/__init__.py`

**Interfaces:**
- Consumes: Existing graph/engine.py (~652 lines, needs trimming to ≤400)
- Produces: Trimmed engine + unit tests covering: topological sort, fan-out, fan-in, retry, condition routing, serialization

- [ ] **Step 1: Read current engine.py** — understand what to keep and trim
- [ ] **Step 2: Rewrite graph/engine.py** — keep GraphNode, GraphEdge, PipelineGraph, ExecutionEngine, RunRecord, NodeRecord. Remove non-essential. Each executor function simplified. Target: 380-400 lines.
- [ ] **Step 3: Write unit tests** — Topological order: linear chain, fan-out/fan-in, diamond, cycle detection. Node retry: success after N-1 failures, exhaust retries. Edge condition: conditional routing True/False. Serialization: to_dict/from_dict round-trip.
- [ ] **Step 4: Run tests in sandbox** — `docker exec -w /workspace hermes-sandbox python3 -m pytest tests/test_graph_engine.py -v`
- [ ] **Step 5: Commit** — `git add graph/engine.py tests/ && git commit -m "fix: graph engine trimmed to 400 lines + unit tests"`

---

### Task B: Backend Graph API Completion

**Files:**
- Modify: `backend/main.py` (add ~150 lines of graph endpoints)

**Interfaces:**
- Consumes: graph/engine.py (Task A's output)
- Produces: Working Graph API endpoints

- [ ] **Step 1: Read current backend/main.py** — find the graph API section (lines ~440-510)
- [ ] **Step 2: Fix GraphNode import and GRAPH_ENGINE_AVAILABLE guard**
- [ ] **Step 3: Fix /api/graph/{gid}/run endpoint** — match engine's actual Execute API
- [ ] **Step 4: Add /api/graph/{gid}/nodes/status** — return all node statuses for polling
- [ ] **Step 5: Add /api/graph/{gid}/runs** — return run history
- [ ] **Step 6: Test in sandbox** — `docker exec -w /workspace hermes-sandbox python3 -c "from backend.main import app; print('OK')"`
- [ ] **Step 7: Commit**

---

### Task C: Frontend Graph Dashboard Completion

**Files:**
- Modify: `frontend/src/views/GraphDashboard.vue` (~400 lines max)

**Interfaces:**
- Consumes: GET /api/graph, GET /api/graph/{gid}, GET /api/graph/{gid}/nodes/status
- Produces: Working SVG graph dashboard

- [ ] **Step 1: Read current GraphDashboard.vue** — understand what's written
- [ ] **Step 2: Verify/rewrite to handle all API states** — loading, error, empty, partial data
- [ ] **Step 3: Fix SVG layout** — ensure nodes space properly, edges avoid overlap
- [ ] **Step 4: Add node detail panel** — click node → show config, result, timing
- [ ] **Step 5: Add auto-poll** — poll /nodes/status every 5s for live updates
- [ ] **Step 6: Verify build** — `npm run build` passes with 0 errors
- [ ] **Step 7: Commit**

---

### Task D: Integration & Red-Blue Review

**Files:**
- All modified files
- `verify-red-blue.sh` — may need updates for new graph tests

**Interfaces:**
- Consumes: All Task A, B, C outputs
- Produces: 100/100 passing red-blue review

- [ ] **Step 1: Create default AICOMICS_PIPELINE graph** — wire existing 3 agents as graph nodes
- [ ] **Step 2: Update verify-red-blue.sh** — add graph engine tests, graph API tests
- [ ] **Step 3: Run full red-blue review in sandbox** — red team finds issues, blue team fixes, red team re-verifies
- [ ] **Step 4: Loop to 100/100** — no open issues, no critical findings
- [ ] **Step 5: Commit + tag v3.0**
