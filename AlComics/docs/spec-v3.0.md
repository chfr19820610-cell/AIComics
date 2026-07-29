# Spec: AIComics v3.0 — Graph Pipeline System

## Objective

Upgrade AIComics from v2.0's 3-layer linear Agent pipeline to a visible DAG-based Graph system where every node (Agent), edge (data dependency), and run is trackable in real-time through a web dashboard.

**User story:** A user opens the AIComics dashboard, sees a visual DAG of their pipeline — each node colored by status (waiting/running/done/failed), edges showing data flow, clickable for details (duration, token cost, output). They can re-run failed nodes, see run history, and watch the graph animate as the pipeline executes.

## Tech Stack

- Backend: Python 3.11+ / FastAPI (existing, extend)
- Frontend: Vue 3 + Vite + Tailwind (existing, extend)
- Graph Engine: Pure Python, no external deps (graph/engine.py)
- Database: SQLite (existing, extend schema)
- Docker: docker-compose (existing, extend)
- Visualization: Vue 3 + SVG (no heavy lib)

## Commands

```
Dev backend:  cd AlComics && python3 backend/main.py
Dev frontend: cd AlComics/frontend && npm run dev
Build:        cd AlComics/frontend && npm run build
Docker:       cd AlComics && docker compose up -d
Test:         pytest tests/
Verify:       cd AlComics && bash verify-red-blue.sh
```

## Project Structure

```
AlComics/
  graph/
    __init__.py          # Package init
    engine.py            # DAG Engine: GraphNode, PipelineGraph, ExecutionEngine, RunRecord (done ✓)
  backend/
    main.py              # FastAPI + Graph API endpoints (partial ✓)
  frontend/
    src/
      views/
        GraphDashboard.vue  # SVG DAG visualization (partial ✓)
      api.js              # Graph API client
      router/index.js     # Route for /graph and /graph/:gid (done ✓)
      App.vue             # Nav link to Pipeline (done ✓)
  docker-compose.yaml     # Extend as needed
  verify-red-blue.sh      # Red-blue review script
  run.sh                  # Entry point
```

## Code Style

```python
# Minimal, file-per-responsibility, <400 lines per file
# Each node type = one executor function, each API endpoint = one route
# No unnecessary OOP — use dataclasses + functions where possible

# Good:
async def run_graph_pipeline(gid: str) -> dict:
    graph = await load_graph(gid)
    engine = ExecutionEngine()
    record = await engine.execute(graph)
    return {"run_id": record.id, "status": record.status.value}

# Avoid:
class GraphRunner(AbstractRunner):
    def __init__(self, config: RunnerConfig):
        self.config = config
        ...
```

## Testing Strategy

- Graph Engine: Unit tests for topological sort, fan-out/fan-in, retry, condition routing
- Backend API: Integration tests for graph CRUD + run endpoints
- Frontend: Build verification (no syntax errors, no npm audit warnings)
- Red-blue: All code must pass sandbox red-blue review (verify-red-blue.sh)

## Boundaries

- **Always:** Run verify before commit, follow minimal style, keep files <400 lines
- **Ask first:** Adding external visualization libs, changing DB schema, adding new deps
- **Never:** Duplicate engine logic in API layer, skip red-blue review, commit untested code

## Success Criteria

1. [ ] Graph Engine: Create a graph with 10+ nodes, run it, observe correct topological execution and retry behavior
2. [ ] Graph API: Create graph via POST /api/graph, run via POST /api/graph/{id}/run, query status via GET /api/graph/{id}
3. [ ] Graph Dashboard: Navigate to /graph, see list of graphs, click one to see SVG DAG with colored nodes
4. [ ] Red-blue review: All code passes sandbox red-blue review with 0 errors
5. [ ] Minimal code: Graph Engine ≤400 lines, Graph API additions ≤200 lines, Graph Dashboard ≤400 lines
6. [ ] Loop to 100/100: Every spec passes, every review gate passes, no open issues

## Sub-specs (Parallel Execution Plan)

### Sub-spec A: Graph Engine Fixes & Verification
Review and fix graph/engine.py to match spec: ensure GraphEdge uses from_id/to_id, RunRecord.nodes dict is correct, executor functions work, topological sort handles loops and conditions. Write unit tests. Target: ≤400 lines.

### Sub-spec B: Backend Graph API Completion  
Fix backend/main.py to match engine's actual API: verify imports, fix run endpoint, add node status query, add run history. Extend Dockerfile/docker-compose as needed. Target: ≤200 new lines.

### Sub-spec C: Frontend Graph Dashboard Completion
Fix GraphDashboard.vue to work with real API: handle all states (loading/error/empty), verify SVG rendering, add node detail panel, add run history list, poll for live updates. Target: ≤400 lines.

### Sub-spec D: Integration & Red-Blue Review
Wire the 3 existing agent nodes into a default graph, create AICOMICS_PIPELINE graph definition, verify end-to-end: create project → generate → see graph update. Run full red-blue review in sandbox. Target: all passing.

## Open Questions

- Should graph edges support condition-based routing in v3.0 MVP? (Yes, condition fields exist but initial executors are simple)
- Should the frontend show live animation of graph execution? (Yes, basic status color animation + polling)
