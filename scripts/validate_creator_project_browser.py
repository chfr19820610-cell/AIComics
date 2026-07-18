from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from verify_frontend_browser_login import (
    CdpClient,
    PROJECT_ROOT,
    clear_browser_auth_state,
    collect_error_events,
    execute_browser_login,
    first_page_target,
    request_json,
    wait_for_cdp_server,
    wait_for_dashboard,
    wait_for_login_page,
)


DEFAULT_PROJECT_ID = "horror_real_sample_20260513015958"
DEFAULT_FRONTEND_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:7861"
DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_MANAGE_SCRIPT = PROJECT_ROOT / "scripts" / "manage_local_web_stack.sh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the local Creator web stack, perform real password login, and verify a target Creator project page.",
    )
    parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--frontend-base-url", default=os.environ.get("AICOMIC_FRONTEND_BASE_URL", DEFAULT_FRONTEND_BASE_URL))
    parser.add_argument("--backend-base-url", default=os.environ.get("AICOMIC_BACKEND_BASE_URL", DEFAULT_BACKEND_BASE_URL))
    parser.add_argument("--username", default=os.environ.get("AICOMIC_BROWSER_LOGIN_USERNAME", "creator"))
    parser.add_argument("--password", default=os.environ.get("AICOMIC_BROWSER_LOGIN_PASSWORD", ""))
    parser.add_argument("--chrome-path", default=os.environ.get("CHROME_PATH", DEFAULT_CHROME_PATH))
    parser.add_argument("--cdp-port", type=int, default=9300 + random.randint(20, 280))
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--skip-stack-start", action="store_true")
    parser.add_argument("--keep-browser", action="store_true")
    parser.add_argument(
        "--report-path",
        default="",
        help="Optional JSON report path. Default: reports/creator_project_browser_<project_id>.json",
    )
    return parser.parse_args()


def load_password(cli_password: str) -> str:
    if cli_password:
        return cli_password
    env_password = os.environ.get("AICOMIC_NORMAL_USER_PASSWORD", "").strip()
    if env_password:
        return env_password
    env_file = PROJECT_ROOT / ".env.production.local"
    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            if raw_line.startswith("AICOMIC_NORMAL_USER_PASSWORD="):
                return raw_line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("Password is required. Set --password, AICOMIC_BROWSER_LOGIN_PASSWORD, or AICOMIC_NORMAL_USER_PASSWORD.")


def run_manage_stack_up(script_path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(script_path), "up"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "manage_local_web_stack.sh up failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    try:
        start = result.stdout.rfind("{")
        if start >= 0:
            return json.loads(result.stdout[start:])
    except json.JSONDecodeError:
        pass
    return {"raw_stdout": result.stdout}


def wait_for_backend_health(backend_base_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            request_json(f"{backend_base_url}/api/health")
            return
        except Exception as exc:  # pragma: no cover - integration script
            last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(f"Backend health check did not become ready: {last_error}")


def wait_for_frontend_login(frontend_base_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        for candidate_url in (f"{frontend_base_url}/login", f"{frontend_base_url}/"):
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    candidate_url,
                    timeout=5,
                ) as response:
                    if response.status == 200:
                        return
            except Exception as exc:  # pragma: no cover - integration script
                last_error = f"{candidate_url}: {exc}"
        time.sleep(0.5)
    raise RuntimeError(f"Frontend /login did not become ready: {last_error}")


def build_creator_url(frontend_base_url: str, project_id: str) -> str:
    return f"{frontend_base_url}/creator?project_id={urllib.parse.quote(project_id)}"


def launch_chrome(chrome_path: str, cdp_port: int) -> tuple[subprocess.Popen[bytes], Path]:
    profile_dir = Path("/tmp") / f"aicomic-creator-browser-qa-{os.getpid()}-{cdp_port}"
    process = subprocess.Popen(
        [
            chrome_path,
            "--headless=new",
            f"--remote-debugging-port={cdp_port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1440,2200",
            "about:blank",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process, profile_dir


def wait_for_creator_project_page(
    client: CdpClient,
    project_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        last_state = client.evaluate(
            f"""
            (() => {{
              const bodyText = document.body ? document.body.innerText : '';
              const visibleText = bodyText.slice(0, 5000);
              const actionLabels = [...document.querySelectorAll('button, span, div')]
                .map((element) => (element.innerText || '').trim())
                .filter(Boolean)
                .filter((text, index, all) => all.indexOf(text) === index)
                .filter((text) =>
                  text.includes('启动自动驾驶') ||
                  text.includes('确认发布') ||
                  text.includes('过审后一键导出') ||
                  text.includes('候选片状态') ||
                  text.includes('自动审片结论')
                )
                .slice(0, 30);
              return {{
                href: location.href,
                pathname: location.pathname,
                title: document.title,
                project_id_present: location.href.includes({json.dumps(project_id)}),
                has_creator_heading: bodyText.includes('项目驾驶舱') || bodyText.includes('Creator 控制台'),
                has_autopilot_panel: bodyText.includes('候选片状态'),
                has_project_id: bodyText.includes({json.dumps(project_id)}),
                has_action_buttons: bodyText.includes('启动自动驾驶') && bodyText.includes('确认发布'),
                body_preview: visibleText,
                action_labels: actionLabels,
              }};
            }})()
            """
        )
        if (
            last_state.get("pathname") == "/creator"
            and bool(last_state.get("project_id_present"))
            and bool(last_state.get("has_creator_heading"))
            and bool(last_state.get("has_autopilot_panel"))
            and bool(last_state.get("has_action_buttons"))
        ):
            return last_state
        time.sleep(0.5)
    raise RuntimeError(f"Creator project page did not become ready: {last_state}")


def capture_screenshot(client: CdpClient, screenshot_path: Path) -> None:
    response = client.send(
        "Page.captureScreenshot",
        {
            "format": "png",
            "captureBeyondViewport": True,
            "fromSurface": True,
        },
    )
    payload = response.get("result", {})
    screenshot_data = str(payload.get("data", ""))
    if not screenshot_data:
        raise RuntimeError(f"Screenshot payload missing data: {response}")
    screenshot_path.write_bytes(__import__("base64").b64decode(screenshot_data))


def classify_error_event(event: dict[str, Any]) -> tuple[str, str]:
    method = str(event.get("method", ""))
    params = event.get("params", {})
    if method == "Log.entryAdded":
        entry = params.get("entry", {})
        url = str(entry.get("url", ""))
        text = str(entry.get("text", ""))
        if "/api/creator/assets?" in url:
            return "blocking", url or text
        return "warning", url or text

    if method == "Runtime.consoleAPICalled":
        values = [str(arg.get("value", "")) for arg in params.get("args", []) if isinstance(arg, dict)]
        text = " ".join(item for item in values if item).strip()
        if "useForm" in text:
            return "business_warning", text
        if "findDOMNode" in text:
            return "dependency_warning", text
        return "warning", text

    if method == "Runtime.exceptionThrown":
        details = params.get("exceptionDetails", {})
        return "blocking", str(details.get("text", "") or details.get("exception", {}).get("description", ""))

    return "warning", method


def main() -> int:
    args = parse_args()
    password = load_password(args.password)
    report_path = (
        Path(args.report_path)
        if args.report_path
        else PROJECT_ROOT / "reports" / f"creator_project_browser_{args.project_id}.json"
    )
    screenshot_path = report_path.with_suffix(".png")

    manage_result: dict[str, Any] = {}
    login_state: dict[str, Any] = {}
    submit_state: dict[str, Any] = {}
    dashboard_state: dict[str, Any] = {}
    creator_page_state: dict[str, Any] = {}
    error_message = ""
    status = "failed"
    start_time = time.time()
    client: CdpClient | None = None
    browser_process: subprocess.Popen[bytes] | None = None
    browser_profile_dir: Path | None = None
    page_target: dict[str, Any] = {}
    asset_request_errors: list[str] = []
    blocking_errors: list[str] = []
    business_warnings: list[str] = []
    dependency_warnings: list[str] = []

    try:
        if not args.skip_stack_start:
            manage_result = run_manage_stack_up(DEFAULT_MANAGE_SCRIPT)
        wait_for_backend_health(args.backend_base_url, args.timeout_seconds)
        wait_for_frontend_login(args.frontend_base_url, args.timeout_seconds)

        browser_process, browser_profile_dir = launch_chrome(args.chrome_path, args.cdp_port)
        wait_for_cdp_server(args.cdp_port, args.timeout_seconds)
        page_target = first_page_target(args.cdp_port)
        client = CdpClient(page_target["webSocketDebuggerUrl"], timeout_seconds=10)
        for method in ("Page.enable", "Runtime.enable", "Log.enable", "Network.enable"):
            client.send(method)

        login_url = f"{args.frontend_base_url}/login"
        clear_browser_auth_state(client, login_url)
        client.send("Page.navigate", {"url": login_url})
        time.sleep(1)
        login_state = wait_for_login_page(client, args.timeout_seconds)
        try:
            submit_state = execute_browser_login(client, username=args.username, password=password)
        except RuntimeError as exc:
            if "Inspected target navigated or closed" not in str(exc):
                raise
            submit_state = {
                "ok": True,
                "stage": "submitted-navigation",
                "detail": "Page navigated while the login submit evaluation was still awaiting.",
            }
        if not bool(submit_state.get("ok")):
            raise RuntimeError(f"Login form submit failed: {submit_state}")

        dashboard_url = f"{args.frontend_base_url}/dashboard"
        client.send("Page.navigate", {"url": dashboard_url})
        dashboard_state = wait_for_dashboard(client, "/dashboard", args.timeout_seconds)

        creator_url = build_creator_url(args.frontend_base_url, args.project_id)
        client.send("Page.navigate", {"url": creator_url})
        creator_page_state = wait_for_creator_project_page(client, args.project_id, args.timeout_seconds)
        capture_screenshot(client, screenshot_path)
        status = "passed"
    except Exception as exc:  # pragma: no cover - integration script
        error_message = str(exc)
    finally:
        error_events = collect_error_events(client.events if client else [])
        for event in error_events:
            classification, detail = classify_error_event(event)
            if classification == "blocking":
                blocking_errors.append(detail)
                if "/api/creator/assets?" in detail:
                    asset_request_errors.append(detail)
            elif classification == "business_warning":
                business_warnings.append(detail)
            elif classification == "dependency_warning":
                dependency_warnings.append(detail)
        if status == "passed" and (asset_request_errors or business_warnings):
            status = "failed"
            if asset_request_errors:
                error_message = f"Detected {len(asset_request_errors)} creator asset request errors."
            else:
                error_message = f"Detected {len(business_warnings)} business warnings."
        report = {
            "status": status,
            "error": error_message,
            "project_id": args.project_id,
            "frontend_base_url": args.frontend_base_url,
            "backend_base_url": args.backend_base_url,
            "login_url": f"{args.frontend_base_url}/login",
            "creator_url": build_creator_url(args.frontend_base_url, args.project_id),
            "username": args.username,
            "password_supplied": bool(password),
            "cdp_port": args.cdp_port,
            "browser_pid": browser_process.pid if browser_process else None,
            "manage_stack_result": manage_result,
            "page_target": {
                "id": page_target.get("id", ""),
                "title": page_target.get("title", ""),
                "url": page_target.get("url", ""),
            },
            "login_state": login_state,
            "submit_state": submit_state,
            "dashboard_state": dashboard_state,
            "creator_page_state": creator_page_state,
            "screenshot_path": str(screenshot_path),
            "captured_error_event_count": len(error_events),
            "captured_error_events": error_events[:20],
            "blocking_error_count": len(blocking_errors),
            "blocking_errors": blocking_errors[:20],
            "business_warning_count": len(business_warnings),
            "business_warnings": business_warnings[:20],
            "dependency_warning_count": len(dependency_warnings),
            "known_dependency_warnings": dependency_warnings[:20],
            "asset_request_error_count": len(asset_request_errors),
            "asset_request_errors": asset_request_errors[:20],
            "duration_ms": int((time.time() - start_time) * 1000),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if client is not None:
            client.close()
        if browser_process is not None and not args.keep_browser:
            browser_process.terminate()
            try:
                browser_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser_process.kill()
        if browser_profile_dir is not None and browser_profile_dir.exists() and not args.keep_browser:
            shutil.rmtree(browser_profile_dir, ignore_errors=True)

    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
