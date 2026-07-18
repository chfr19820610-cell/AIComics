from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "web" / "frontend"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
DEFAULT_PROJECT_ID = "horror_real_sample_20260513015958"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "creator_main_chain_gate_report.json"


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    start = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    duration_ms = int((time.perf_counter() - start) * 1000)
    return {
        "command": command,
        "cwd": str(cwd),
        "return_code": result.returncode,
        "duration_ms": duration_ms,
        "stdout_tail": (result.stdout or "").strip()[-4000:],
        "stderr_tail": (result.stderr or "").strip()[-4000:],
        "passed": result.returncode == 0,
    }


def parse_args() -> dict[str, str]:
    project_id = DEFAULT_PROJECT_ID
    report_path = str(DEFAULT_REPORT_PATH)
    argv = sys.argv[1:]
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--project-id" and index + 1 < len(argv):
            project_id = argv[index + 1]
            index += 2
            continue
        if arg == "--report-path" and index + 1 < len(argv):
            report_path = argv[index + 1]
            index += 2
            continue
        raise SystemExit(f"Unsupported arguments: {' '.join(argv[index:])}")
    return {
        "project_id": project_id,
        "report_path": report_path,
    }


def main() -> int:
    args = parse_args()
    child_env = os.environ.copy()
    child_env["PYTHONPATH"] = f"{PROJECT_ROOT / 'src'}:{PROJECT_ROOT}"

    run_items: list[dict[str, Any]] = []

    run_items.append(
        run_command(
            [sys.executable, "-m", "compileall", "scripts"],
            cwd=PROJECT_ROOT,
            env=child_env,
        )
    )

    run_items.append(
        run_command(
            ["npm", "run", "typecheck"],
            cwd=FRONTEND_ROOT,
        )
    )

    run_items.append(
        run_command(
            ["npm", "run", "build"],
            cwd=FRONTEND_ROOT,
        )
    )

    run_items.append(
        run_command(
            ["./scripts/manage_local_web_stack.sh", "restart"],
            cwd=PROJECT_ROOT,
        )
    )

    browser_report_path = PROJECT_ROOT / "reports" / f"creator_project_browser_{args['project_id']}.json"
    run_items.append(
        run_command(
            [
                str(VENV_PYTHON),
                "scripts/validate_creator_project_browser.py",
                "--project-id",
                args["project_id"],
            ],
            cwd=PROJECT_ROOT,
            env=child_env,
        )
    )

    visual_qa_report_path = PROJECT_ROOT / "reports" / "frontend_visual_qa_gate_report.json"
    run_items.append(
        run_command(
            [
                str(VENV_PYTHON),
                "scripts/validate_frontend_visual_qa_gate.py",
            ],
            cwd=PROJECT_ROOT,
            env=child_env,
        )
    )

    browser_report: dict[str, Any] = {}
    if browser_report_path.exists():
        browser_report = json.loads(browser_report_path.read_text(encoding="utf-8"))
    visual_qa_report: dict[str, Any] = {}
    if visual_qa_report_path.exists():
        visual_qa_report = json.loads(visual_qa_report_path.read_text(encoding="utf-8"))

    blocking_error_count = int(browser_report.get("blocking_error_count", 0) or 0)
    business_warning_count = int(browser_report.get("business_warning_count", 0) or 0)
    dependency_warning_count = int(browser_report.get("dependency_warning_count", 0) or 0)
    asset_request_error_count = int(browser_report.get("asset_request_error_count", 0) or 0)
    browser_passed = str(browser_report.get("status", "")) == "passed"

    visual_qa_passed = bool(visual_qa_report.get("passed", False))
    passed = all(item["passed"] for item in run_items) and browser_passed and visual_qa_passed and blocking_error_count == 0 and business_warning_count == 0 and asset_request_error_count == 0
    report_payload = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "project_id": args["project_id"],
        "passed": passed,
        "checks": {
            "compile_scripts": run_items[0]["passed"],
            "frontend_typecheck": run_items[1]["passed"],
            "frontend_build": run_items[2]["passed"],
            "local_web_stack_restart": run_items[3]["passed"],
            "creator_browser_gate": run_items[4]["passed"] and browser_passed,
            "frontend_visual_qa_gate": run_items[5]["passed"] and visual_qa_passed,
        },
        "browser_gate": {
            "status": browser_report.get("status", ""),
            "blocking_error_count": blocking_error_count,
            "business_warning_count": business_warning_count,
            "dependency_warning_count": dependency_warning_count,
            "asset_request_error_count": asset_request_error_count,
            "report_path": str(browser_report_path),
            "screenshot_path": browser_report.get("screenshot_path", ""),
        },
        "frontend_visual_qa_gate": {
            "passed": visual_qa_passed,
            "report_path": str(visual_qa_report_path),
            "failing_pages": visual_qa_report.get("failing_pages", []),
            "event_pages": visual_qa_report.get("event_pages", []),
            "visual_qa_report_path": visual_qa_report.get("visual_qa_report_path", ""),
        },
        "items": run_items,
    }

    report_path = Path(args["report_path"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
