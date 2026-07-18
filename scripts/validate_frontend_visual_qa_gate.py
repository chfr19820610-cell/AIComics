from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:7861"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "frontend_visual_qa_gate_report.json"


def parse_args() -> dict[str, str]:
    frontend_base_url = os.environ.get("AICOMIC_FRONTEND_BASE_URL", DEFAULT_FRONTEND_BASE_URL)
    backend_base_url = os.environ.get("AICOMIC_BACKEND_BASE_URL", DEFAULT_BACKEND_BASE_URL)
    report_path = str(DEFAULT_REPORT_PATH)
    argv = sys.argv[1:]
    index = 0
    while index < len(argv):
      arg = argv[index]
      if arg == "--frontend-base-url" and index + 1 < len(argv):
          frontend_base_url = argv[index + 1]
          index += 2
          continue
      if arg == "--backend-base-url" and index + 1 < len(argv):
          backend_base_url = argv[index + 1]
          index += 2
          continue
      if arg == "--report-path" and index + 1 < len(argv):
          report_path = argv[index + 1]
          index += 2
          continue
      raise SystemExit(f"Unsupported arguments: {' '.join(argv[index:])}")
    return {
      "frontend_base_url": frontend_base_url,
      "backend_base_url": backend_base_url,
      "report_path": report_path,
    }


def load_password() -> str:
    env_password = os.environ.get("AICOMIC_NORMAL_USER_PASSWORD", "").strip()
    if env_password:
        return env_password
    env_file = PROJECT_ROOT / ".env.production.local"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            if raw_line.startswith("AICOMIC_NORMAL_USER_PASSWORD="):
                return raw_line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("Password is required. Set AICOMIC_NORMAL_USER_PASSWORD or .env.production.local.")


def request_access_token(backend_base_url: str, password: str) -> dict[str, Any]:
    payload = json.dumps({"username": "creator", "password": password}).encode("utf-8")
    request = urllib.request.Request(
        f"{backend_base_url}/api/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - integration path
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Frontend visual QA login failed: {exc.code} {detail}") from exc


def run_visual_qa(frontend_base_url: str, access_token: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["AICOMIC_FRONTEND_BASE_URL"] = frontend_base_url
    env["AICOMIC_QA_ACCESS_TOKEN"] = access_token
    result = subprocess.run(
        ["node", "scripts/run_frontend_visual_qa_chrome.mjs"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Frontend visual QA run failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    summary = json.loads(result.stdout)
    report_path = Path(summary["reportPath"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        "summary": summary,
        "report_path": str(report_path),
        "report": report,
        "stdout_tail": result.stdout.strip()[-4000:],
        "stderr_tail": result.stderr.strip()[-4000:],
    }


def main() -> int:
    args = parse_args()
    password = load_password()
    auth_payload = request_access_token(args["backend_base_url"], password)
    access_token = str(auth_payload.get("access_token", "")).strip()
    if not access_token:
        raise SystemExit("Frontend visual QA login succeeded but access_token is missing.")

    visual_qa = run_visual_qa(args["frontend_base_url"], access_token)
    pages = visual_qa["report"].get("pages", [])
    failing_pages = [
        {
            "route": page.get("route", ""),
            "pathname": page.get("pathname", ""),
            "issue_hints": page.get("issueHints", []),
            "event_count": page.get("eventCount", 0),
            "raw_event_count": page.get("rawEventCount", 0),
            "screenshot_path": page.get("screenshotPath", ""),
        }
        for page in pages
        if page.get("issueHints")
    ]
    event_pages = [
        {
            "route": page.get("route", ""),
            "pathname": page.get("pathname", ""),
            "event_count": page.get("eventCount", 0),
            "raw_event_count": page.get("rawEventCount", 0),
        }
        for page in pages
        if int(page.get("eventCount", 0) or 0) > 0
    ]
    passed = not failing_pages

    report_payload = {
        "run_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "passed": passed,
        "frontend_base_url": args["frontend_base_url"],
        "backend_base_url": args["backend_base_url"],
        "visual_qa_report_path": visual_qa["report_path"],
        "page_count": len(pages),
        "failing_pages": failing_pages,
        "event_pages": event_pages,
        "routes": [
            {
                "route": page.get("route", ""),
                "pathname": page.get("pathname", ""),
                "issue_hints": page.get("issueHints", []),
                "event_count": page.get("eventCount", 0),
                "raw_event_count": page.get("rawEventCount", 0),
            }
            for page in pages
        ],
        "runner_stdout_tail": visual_qa["stdout_tail"],
        "runner_stderr_tail": visual_qa["stderr_tail"],
    }
    report_path = Path(args["report_path"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
