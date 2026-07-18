from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from web.backend.services.creator_review_service import build_auto_review_decision


def main() -> int:
    run_id = f"creator_autopilot_policy_validation_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    pass_payload = {
        "release_video": {"exists": True, "used_placeholder_count": 0},
        "provider_summary": {"manual_required_count": 0, "queue_count": 0},
        "quality_summary": {"blocking_findings": 0, "review_required_findings": 1},
        "autopilot_state": {"repair_cycle_count": 1, "max_repair_cycles": 3},
    }
    repair_payload = {
        "release_video": {"exists": True, "used_placeholder_count": 2},
        "provider_summary": {"manual_required_count": 1, "queue_count": 3},
        "quality_summary": {"blocking_findings": 0, "review_required_findings": 2},
        "autopilot_state": {"repair_cycle_count": 1, "max_repair_cycles": 3},
    }
    human_hold_payload = {
        "release_video": {"exists": True, "used_placeholder_count": 1},
        "provider_summary": {"manual_required_count": 2, "queue_count": 4},
        "quality_summary": {"blocking_findings": 1, "review_required_findings": 3},
        "autopilot_state": {"repair_cycle_count": 3, "max_repair_cycles": 3},
    }

    pass_decision = build_auto_review_decision(pass_payload)
    repair_decision = build_auto_review_decision(repair_payload)
    human_hold_decision = build_auto_review_decision(human_hold_payload)

    checks = {
        "pass_routes_to_candidate": pass_decision["decision"] == "pass_to_candidate",
        "repair_routes_to_retry": repair_decision["decision"] == "repair_and_retry",
        "repair_has_reasons": bool(repair_decision["reasons"]),
        "human_hold_routes_to_escalation": human_hold_decision["decision"] == "escalate_to_human",
        "human_hold_mentions_blocking": any("阻塞" in str(item) for item in human_hold_decision["reasons"]),
    }
    payload = {
        "run_id": run_id,
        "checks": checks,
        "pass_decision": pass_decision,
        "repair_decision": repair_decision,
        "human_hold_decision": human_hold_decision,
        "passed": all(checks.values()),
    }
    report_path = PROJECT_ROOT / "reports" / "creator_autopilot_policy_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
