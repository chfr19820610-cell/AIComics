"""AIComics intelligence layer — Jev System One methodology, distilled locally.

Jev (TypeSafe AI's System One model) provides fast, typed, confidence-aware
decision primitives for software. AIComics is fully local, so we distill the
*methodology* — not the API — into 8 modules that run without external calls.

Modules:
  - calibrated_decision: Noul/Choice/Score primitives (Jev's 3 core types)
  - confidence_gate: confidence-gated action routing (pass/review/reject)
  - best_of_n: Best-of-N candidate arbitration (pick winner from N outputs)
  - loop_breaker: stuck-detection for retry loops (break early, save budget)
  - speculative_fanout: parallel multi-check evaluation (ask all at once)
  - model_cascade: difficulty-based provider routing (cheap for easy, premium for hard)
  - guardrail: input/output content screening (block banned content before API)
  - patch_verifier: diff verification against conventions (block risky changes)

Distilled from:
  - TypeSafe AI Jev System One (https://docs.typesafe.ai)
  - awesome-jev-by-typesafe use-case playbook
  - Jev coding-agent patterns (skill selection, command safety, cascade)
"""
from aicomic.intelligence.calibrated_decision import (
    DecisionEngine,
    Noul,
    Choice,
    Score,
)
from aicomic.intelligence.confidence_gate import (
    ConfidenceGate,
    GateAction,
    GateDecision,
)
from aicomic.intelligence.best_of_n import (
    BestOfNArbitrator,
    Candidate,
    ArbitrationResult,
)
from aicomic.intelligence.loop_breaker import (
    LoopBreaker,
    LoopSignal,
)
from aicomic.intelligence.speculative_fanout import (
    SpeculativeFanout,
    FanoutResult,
)
from aicomic.intelligence.model_cascade import (
    ModelCascade,
    CascadeRoute,
    Difficulty,
)
from aicomic.intelligence.guardrail import (
    Guardrail,
    GuardResult,
    GuardLevel,
)
from aicomic.intelligence.patch_verifier import (
    PatchVerifier,
    VerifyResult,
    VerifyAction,
)

__all__ = [
    # calibrated_decision
    "DecisionEngine",
    "Noul",
    "Choice",
    "Score",
    # confidence_gate
    "ConfidenceGate",
    "GateAction",
    "GateDecision",
    # best_of_n
    "BestOfNArbitrator",
    "Candidate",
    "ArbitrationResult",
    # loop_breaker
    "LoopBreaker",
    "LoopSignal",
    # speculative_fanout
    "SpeculativeFanout",
    "FanoutResult",
    # model_cascade
    "ModelCascade",
    "CascadeRoute",
    "Difficulty",
    # guardrail
    "Guardrail",
    "GuardResult",
    "GuardLevel",
    # patch_verifier
    "PatchVerifier",
    "VerifyResult",
    "VerifyAction",
]
