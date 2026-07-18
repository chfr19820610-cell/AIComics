from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.security.dependency_audit import build_dependency_audit_report, write_dependency_audit_report


def main() -> int:
    report_path = PROJECT_ROOT / "reports" / "dependency_audit_report.json"
    payload = build_dependency_audit_report(PROJECT_ROOT)
    write_dependency_audit_report(report_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
