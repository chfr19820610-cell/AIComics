"""AIComics v3.0 Graph Engine — DAG orchestrator with retry + condition routing."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


# ── Enums ──────────────────────────────────────────────────────
class NodeType(str, Enum):
    SCRIPT_SPLITTER = "script_splitter"; TASK_ASSIGNER = "task_assigner"
    FRAME_GENERATOR = "frame_generator"; VIDEO_COMPOSER = "video_composer"
    AUDIO_ADDER = "audio_adder"; QUALITY_CHECKER = "quality_checker"
    ROUTE_DECISION = "route_decision"; VERIFIER = "verifier"
    PUBLISHER = "publisher"; SUBGRAPH = "subgraph"

class NodeStatus(str, Enum):
    PENDING = "pending"; RUNNING = "running"; COMPLETED = "completed"
    FAILED = "failed"; SKIPPED = "skipped"

class GraphStatus(str, Enum):
    PENDING = "pending"; RUNNING = "running"; COMPLETED = "completed"; FAILED = "failed"


# ── Models ─────────────────────────────────────────────────────
@dataclass
class GraphNode:
    id: str; type: NodeType; label: str
    config: dict = field(default_factory=dict)
    schema: dict = field(default_factory=lambda: {"input": None, "output": None})
    status: NodeStatus = NodeStatus.PENDING
    result_history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"id": self.id, "type": self.type.value, "label": self.label,
             "config": self.config, "schema": self.schema, "status": self.status.value}
        try:
            d["result_history"] = self.result_history; json.dumps(d)
        except (TypeError, ValueError):
            d["result_history"] = ["<non-serialisable>"] * len(self.result_history)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> GraphNode:
        return cls(id=data["id"], type=NodeType(data["type"]),
                   label=data.get("label", data["id"]),
                   config=data.get("config", {}),
                   schema=data.get("schema", {"input": None, "output": None}),
                   status=NodeStatus(data.get("status", "pending")),
                   result_history=data.get("result_history", []))


@dataclass
class GraphEdge:
    from_id: str; to_id: str
    schema_constraint: dict = field(default_factory=dict)
    condition: Optional[Callable[[dict], bool]] = None

    def to_dict(self) -> dict:
        return {"from_id": self.from_id, "to_id": self.to_id,
                "schema_constraint": self.schema_constraint}


@dataclass
class PipelineGraph:
    id: str; name: str
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    status: GraphStatus = GraphStatus.PENDING
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name,
                "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
                "edges": [e.to_dict() for e in self.edges],
                "status": self.status.value, "metadata": self.metadata}

    @classmethod
    def from_yaml(cls, data: dict) -> PipelineGraph:
        """Build from a dict with nodes as list and edges with 'from'/'to' keys."""
        g = cls(id=data["id"], name=data.get("name", data["id"]))
        for nd in data.get("nodes", []):
            node = GraphNode(id=nd["id"], type=NodeType(nd["type"]),
                             label=nd.get("label", nd["id"]),
                             config=nd.get("config", {}),
                             schema=nd.get("schema", {"input": None, "output": None}))
            g.nodes[node.id] = node
        for ed in data.get("edges", []):
            g.edges.append(GraphEdge(from_id=ed.get("from", ed.get("from_id")),
                                     to_id=ed.get("to", ed.get("to_id")),
                                     schema_constraint=ed.get("schema_constraint", {})))
        g.metadata = data.get("metadata", {})
        return g

    @classmethod
    def from_dict(cls, data: dict) -> PipelineGraph:
        g = cls(id=data["id"], name=data.get("name", data["id"]))
        for nd in data.get("nodes", {}).values():
            node = GraphNode(id=nd["id"], type=NodeType(nd["type"]),
                             label=nd.get("label", nd["id"]),
                             config=nd.get("config", {}),
                             schema=nd.get("schema", {"input": None, "output": None}))
            g.nodes[node.id] = node
        for ed in data.get("edges", []):
            g.edges.append(GraphEdge(from_id=ed["from_id"], to_id=ed["to_id"],
                                     schema_constraint=ed.get("schema_constraint", {})))
        g.metadata = data.get("metadata", {})
        return g

    def upstream_node_ids(self, node_id: str) -> set:
        return {e.from_id for e in self.edges if e.to_id == node_id}

    def downstream_node_ids(self, node_id: str) -> set:
        return {e.to_id for e in self.edges if e.from_id == node_id}

    def get_incoming_edges(self, node_id: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.to_id == node_id]


# ── RunRecord ──────────────────────────────────────────────────
@dataclass
class NodeRecord:
    node_id: str; status: NodeStatus = NodeStatus.PENDING
    started_at: Optional[str] = None; completed_at: Optional[str] = None
    result: Any = None; error: Optional[str] = None; retry_count: int = 0

    def to_dict(self) -> dict:
        d = {"node_id": self.node_id, "status": self.status.value,
             "started_at": self.started_at, "completed_at": self.completed_at,
             "error": self.error, "retry_count": self.retry_count}
        try:
            d["result"] = self.result; json.dumps(d)
        except (TypeError, ValueError):
            d["result"] = "<non-serialisable>"
        return d


@dataclass
class RunRecord:
    id: str; graph_id: str; status: GraphStatus
    nodes: dict = field(default_factory=dict)
    started_at: str = ""; completed_at: Optional[str] = None

    def duration_ms(self) -> Optional[float]:
        if not self.started_at or not self.completed_at:
            return None
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at)
        return (end - start).total_seconds() * 1000

    def to_dict(self) -> dict:
        return {"id": self.id, "graph_id": self.graph_id,
                "status": self.status.value,
                "nodes": {nid: nr.to_dict() for nid, nr in self.nodes.items()},
                "started_at": self.started_at, "completed_at": self.completed_at}


# ── ExecutionEngine ────────────────────────────────────────────
class ExecutionEngine:
    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries
        self._executors: dict[NodeType, Callable] = {
            NodeType.SCRIPT_SPLITTER: _exec_script_splitter,
            NodeType.TASK_ASSIGNER: _exec_task_assigner,
            NodeType.FRAME_GENERATOR: _exec_frame_generator,
            NodeType.VIDEO_COMPOSER: _exec_video_composer,
            NodeType.AUDIO_ADDER: _exec_audio_adder,
            NodeType.QUALITY_CHECKER: _exec_quality_checker,
            NodeType.ROUTE_DECISION: _exec_route_decision,
            NodeType.VERIFIER: _exec_verifier,
            NodeType.PUBLISHER: _exec_publisher,
            NodeType.SUBGRAPH: _exec_subgraph,
        }

    async def execute(self, graph: PipelineGraph) -> RunRecord:
        now = datetime.now(timezone.utc).isoformat()
        run = RunRecord(id=str(uuid.uuid4()), graph_id=graph.id,
                        status=GraphStatus.RUNNING, started_at=now)
        run.nodes = {nid: NodeRecord(node_id=nid) for nid in graph.nodes}
        completed: set[str] = set()

        while len(completed) < len(graph.nodes):
            ready_ids = self._find_ready_nodes(graph, run, completed)
            if not ready_ids:
                remaining = set(graph.nodes) - completed
                if not remaining:
                    break
                run.status = GraphStatus.FAILED
                for nid in remaining:
                    run.nodes[nid].status = NodeStatus.FAILED
                    run.nodes[nid].error = "deadlock"
                break

            batch = [asyncio.create_task(self._run_single(nid, graph))
                     for nid in ready_ids]
            results = await asyncio.gather(*batch, return_exceptions=True)

            for nid, outcome in zip(ready_ids, results):
                rec = run.nodes[nid]
                if isinstance(outcome, Exception):
                    rec.error = f"{type(outcome).__name__}: {outcome}"
                    rec.retry_count += 1
                    if rec.retry_count <= self.max_retries:
                        rec.status = NodeStatus.PENDING
                        rec.result = rec.completed_at = None
                        for pred_id in graph.upstream_node_ids(nid):
                            pred_rec = run.nodes.get(pred_id)
                            if pred_rec and pred_rec.status in (NodeStatus.COMPLETED, NodeStatus.FAILED):
                                pred_rec.status = NodeStatus.PENDING
                                pred_rec.result = pred_rec.completed_at = pred_rec.error = None
                                completed.discard(pred_id)
                                graph.nodes[pred_id].result_history = graph.nodes[pred_id].result_history[:-1]
                    else:
                        rec.status = NodeStatus.FAILED
                        rec.completed_at = datetime.now(timezone.utc).isoformat()
                        run.status = GraphStatus.FAILED
                        completed.add(nid)
                else:
                    graph.nodes[nid].result_history.append(outcome)
                    rec.status = NodeStatus.COMPLETED
                    rec.result = outcome
                    rec.completed_at = datetime.now(timezone.utc).isoformat()
                    completed.add(nid)
            if run.status == GraphStatus.FAILED:
                break

        if run.status != GraphStatus.FAILED:
            run.status = GraphStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc).isoformat()
        return run

    def _find_ready_nodes(self, graph: PipelineGraph, run: RunRecord,
                          completed: set[str]) -> list[str]:
        ready: list[str] = []
        for nid, node in graph.nodes.items():
            if nid in completed:
                continue
            rec = run.nodes.get(nid)
            if rec is None or rec.status in (NodeStatus.RUNNING, NodeStatus.FAILED):
                continue
            incoming = graph.get_incoming_edges(nid)
            if not incoming:
                ready.append(nid)
                continue
            satisfied = True
            for edge in incoming:
                src_rec = run.nodes.get(edge.from_id)
                if src_rec is None or src_rec.status != NodeStatus.COMPLETED:
                    satisfied = False; break
                src_result = src_rec.result or {}
                if edge.schema_constraint:
                    for field in edge.schema_constraint:
                        if field not in src_result:
                            satisfied = False; break
                if satisfied and edge.condition is not None:
                    if not edge.condition(src_result):
                        satisfied = False
                if not satisfied:
                    break
            if satisfied:
                ready.append(nid)
        return ready

    async def _run_single(self, nid: str, graph: PipelineGraph) -> dict:
        node = graph.nodes[nid]
        inputs: dict[str, Any] = {}
        for edge in graph.get_incoming_edges(nid):
            src_rec = graph.nodes[edge.from_id].result_history
            if src_rec:
                inputs.update(src_rec[-1])
        in_schema = node.schema.get("input")
        if in_schema is not None:
            missing = [k for k in in_schema if k not in inputs]
            if missing:
                raise ValueError(f"Node {nid} missing inputs: {missing}")
        executor = self._executors.get(node.type)
        if executor is None:
            raise ValueError(f"Unknown node type: {node.type}")
        result = await executor(node, inputs)
        out_schema = node.schema.get("output")
        if out_schema is not None:
            missing = [k for k in out_schema if k not in result]
            if missing:
                raise ValueError(f"Node {nid} missing outputs: {missing}")
        return result


# ── Mock Executors ─────────────────────────────────────────────
async def _exec_script_splitter(node: GraphNode, inputs: dict) -> dict:
    scenes = [s.strip() for s in inputs.get("text", "").split("\n\n") if s.strip()]
    if not scenes:
        scenes = [f"scene_{i}" for i in range(node.config.get("num_scenes", 3))]
    await asyncio.sleep(0.01)
    return {"scenes": scenes, "count": len(scenes)}

async def _exec_task_assigner(node: GraphNode, inputs: dict) -> dict:
    scenes = inputs.get("scenes", [])
    assignments = [{"agent": f"worker_{i % 2}", "scene": s} for i, s in enumerate(scenes)]
    await asyncio.sleep(0.01)
    return {"assignments": assignments}

async def _exec_frame_generator(node: GraphNode, inputs: dict) -> dict:
    assignments = inputs.get("assignments", [])
    frames = [{"scene": a["scene"], "frame_url": f"frames/{a['scene']}.png"} for a in assignments]
    await asyncio.sleep(0.01)
    return {"frames": frames, "count": len(frames)}

async def _exec_video_composer(node: GraphNode, inputs: dict) -> dict:
    await asyncio.sleep(0.01)
    return {"video_url": f"output/{node.id}.mp4", "frame_count": len(inputs.get("frames", []))}

async def _exec_audio_adder(node: GraphNode, inputs: dict) -> dict:
    await asyncio.sleep(0.01)
    return {"video_url": inputs.get("video_url", ""), "audio_url": f"output/{node.id}_audio.mp4"}

async def _exec_quality_checker(node: GraphNode, inputs: dict) -> dict:
    if node.config.get("force_fail"):
        raise RuntimeError("quality check failed")
    await asyncio.sleep(0.01)
    return {"passed": True, "score": 0.95}

async def _exec_route_decision(node: GraphNode, inputs: dict) -> dict:
    expression = node.config.get("expression", "True")
    try:
        route = bool(eval(expression, {"__builtins__": {}}, inputs))
    except Exception:
        route = False
    return {"route": "pass" if route else "fail"}

async def _exec_verifier(node: GraphNode, inputs: dict) -> dict:
    verified = node.config.get("force_verified", True) is True
    await asyncio.sleep(0.01)
    return {"verified": verified, "issues": [] if verified else ["verification failed"]}

async def _exec_publisher(node: GraphNode, inputs: dict) -> dict:
    await asyncio.sleep(0.01)
    return {"published_url": f"output/{node.id}_final.mp4"}

async def _exec_subgraph(node: GraphNode, inputs: dict) -> dict:
    inner = node.config.get("subgraph")
    if not isinstance(inner, PipelineGraph):
        raise ValueError("invalid subgraph config")
    run = await ExecutionEngine(max_retries=node.config.get("max_retries", 1)).execute(inner)
    if run.status != GraphStatus.COMPLETED:
        raise RuntimeError(f"subgraph {inner.id} failed")
    return {"subgraph_run_id": run.id}


# ── __all__ ────────────────────────────────────────────────────
__all__ = [
    "NodeType", "NodeStatus", "GraphStatus",
    "GraphNode", "GraphEdge", "PipelineGraph",
    "NodeRecord", "RunRecord", "ExecutionEngine",
]
