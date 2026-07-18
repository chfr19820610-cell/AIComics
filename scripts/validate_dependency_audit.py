from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.security.dependency_audit import build_dependency_audit_report, write_dependency_audit_report


def main() -> int:
    report_path = PROJECT_ROOT / "reports" / "dependency_audit_report.json"
    dependency_report = build_dependency_audit_report(PROJECT_ROOT)
    write_dependency_audit_report(report_path, dependency_report)

    if not bool(dependency_report["direct_lock_enforced"]):
        raise RuntimeError(f"direct dependency lock is not enforced: {dependency_report}")
    if not bool(dependency_report["docker_constraint_enabled"]):
        raise RuntimeError("Dockerfile must install with --constraint requirements-lock.txt")
    if dependency_report["missing_direct_pins"]:
        raise RuntimeError(f"missing direct pins: {dependency_report['missing_direct_pins']}")
    if os.environ.get("AICOMIC_REQUIRE_FULL_DEPENDENCY_AUDIT", "").strip() == "1":
        if dependency_report["cve_audit_status"] != "completed":
            raise RuntimeError(f"CVE audit must complete in Docker/CI: {dependency_report['cve_audit_status']}")
        if int(dependency_report["known_vulnerability_count"]) != 0:
            raise RuntimeError(f"known vulnerabilities found: {dependency_report['known_vulnerability_count']}")
        if dependency_report["transitive_lock_status"] != "fully_locked":
            raise RuntimeError(f"transitive lock must be fully enforced in Docker/CI: {dependency_report['transitive_lock_status']}")

    validation_payload = {
        "run_id": f"dependency_audit_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": datetime.now().astimezone().isoformat(),
        "lock_status": dependency_report["lock_status"],
        "direct_lock_enforced": dependency_report["direct_lock_enforced"],
        "transitive_lock_status": dependency_report["transitive_lock_status"],
        "cve_audit_status": dependency_report["cve_audit_status"],
        "audit_tool_status": dependency_report["audit_tool_status"],
        "known_vulnerability_count": dependency_report["known_vulnerability_count"],
        "dependency_audit_report_path": str(report_path),
        "report_path": str(PROJECT_ROOT / "reports" / "dependency_audit_validation_report.json"),
    }
    output_path = PROJECT_ROOT / "reports" / "dependency_audit_validation_report.json"
    output_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
