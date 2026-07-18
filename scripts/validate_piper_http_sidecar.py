from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from aicomic.providers.live_smoke import run_local_provider_live_smoke
from aicomic.security.production_rehearsal import find_free_port, temporary_environment


def wait_for_health(base_url: str, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url}/health", timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"Piper HTTP sidecar did not become healthy: {base_url}")


def main() -> int:
    host = "127.0.0.1"
    port = find_free_port(host)
    base_url = f"http://{host}:{port}"
    process = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "run_piper_http_server.py"), "--host", host, "--port", str(port)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_health(base_url)
        with temporary_environment({"AICOMIC_PIPER_BASE_URL": base_url}):
            report = run_local_provider_live_smoke(
                providers_config_path=ProjectPaths.providers_config_path(),
                selected_providers={"local_piper_tts"},
                output_root=ProjectPaths.state_dir() / "piper_http_sidecar_validation",
                skip_comfyui_start=True,
            )
        if report["status"] != "passed":
            raise RuntimeError(f"Piper HTTP sidecar smoke failed: {report}")
        final_results = report.get("final_results", [])
        if len(final_results) != 1:
            raise RuntimeError(f"unexpected Piper HTTP smoke results: {final_results}")
        response_meta = final_results[0].get("execution_output", {}).get("response_meta", {})
        if response_meta.get("execution_transport") != "http_service":
            raise RuntimeError(f"Piper HTTP sidecar transport mismatch: {response_meta}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    validation_payload = {
        "run_id": f"piper_http_sidecar_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": datetime.now().astimezone().isoformat(),
        "base_url": base_url,
        "status": report["status"],
        "success_count": report["final_summary"]["success_count"],
        "output_path": report["output_summaries"][0]["path"],
        "report_path": str(ProjectPaths.reports_dir() / "piper_http_sidecar_validation_report.json"),
    }
    report_path = ProjectPaths.reports_dir() / "piper_http_sidecar_validation_report.json"
    report_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
