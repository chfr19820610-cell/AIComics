from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from websocket import WebSocketTimeoutException, create_connection
except ImportError as exc:  # pragma: no cover - environment dependency
    raise SystemExit(
        "Missing dependency: websocket-client. Install with: python -m pip install websocket-client"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "reports" / "frontend_browser_login_validation_report.json"
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class CdpClient:
    def __init__(self, websocket_url: str, timeout_seconds: float) -> None:
        self.connection = create_connection(websocket_url, timeout=timeout_seconds)
        self.timeout_seconds = timeout_seconds
        self._next_id = 0
        self.events: list[dict[str, Any]] = []

    def close(self) -> None:
        self.connection.close()

    def _receive(self, timeout_seconds: float | None = None) -> dict[str, Any]:
        if timeout_seconds is not None:
            self.connection.settimeout(timeout_seconds)
        raw_message = self.connection.recv()
        return json.loads(raw_message)

    def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next_id += 1
        command_id = self._next_id
        payload: dict[str, Any] = {"id": command_id, "method": method}
        if params is not None:
            payload["params"] = params
        self.connection.send(json.dumps(payload))
        while True:
            message = self._receive(self.timeout_seconds)
            if message.get("id") == command_id:
                return message
            self.events.append(message)

    def drain_events(self, duration_seconds: float = 0.3) -> None:
        deadline = time.time() + duration_seconds
        self.connection.settimeout(0.2)
        while time.time() < deadline:
            try:
                message = self.connection.recv()
            except Exception as exc:
                if "timed out" in str(exc).lower():
                    break
                raise
            self.events.append(json.loads(message))

    def evaluate(self, expression: str, await_promise: bool = False) -> Any:
        response = self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
        )
        result = response.get("result", {}).get("result", {})
        if "value" not in result:
            raise RuntimeError(f"CDP evaluate returned no value: {response}")
        return result["value"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the frontend password login flow in a real browser.")
    parser.add_argument("--login-url", default="http://127.0.0.1:8000/login")
    parser.add_argument("--expected-path", default="/dashboard")
    parser.add_argument("--username", default=os.environ.get("AICOMIC_BROWSER_LOGIN_USERNAME", "creator"))
    parser.add_argument("--password", default=os.environ.get("AICOMIC_BROWSER_LOGIN_PASSWORD", ""))
    parser.add_argument("--cdp-port", type=int, default=9223)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    return parser.parse_args()


def request_json(url: str) -> Any:
    with NO_PROXY_OPENER.open(url, timeout=5) as response:
        return json.load(response)


def build_dashboard_url(login_url: str, expected_path: str) -> str:
    parsed = urlsplit(login_url)
    return f"{parsed.scheme}://{parsed.netloc}{expected_path}"


def clear_browser_auth_state(client: CdpClient, login_url: str) -> None:
    origin_parts = urlsplit(login_url)
    origin = f"{origin_parts.scheme}://{origin_parts.netloc}"
    try:
        client.send("Network.clearBrowserCookies")
        client.send(
            "Storage.clearDataForOrigin",
            {
                "origin": origin,
                "storageTypes": "local_storage,session_storage,cookies",
            },
        )
    except Exception:
        pass
    client.evaluate(
        """
        (() => {
          try {
            localStorage.removeItem('aicomic_access_token');
            localStorage.removeItem('aicomic_refresh_token');
            localStorage.removeItem('aicomic_current_user');
          } catch (error) {}
          try {
            sessionStorage.clear();
          } catch (error) {}
          try {
            document.cookie = 'aicomic_access_token=; Max-Age=0; path=/';
            document.cookie = 'aicomic_refresh_token=; Max-Age=0; path=/';
          } catch (error) {}
          return true;
        })()
        """
    )


def wait_for_cdp_server(port: int, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            request_json(f"http://127.0.0.1:{port}/json/version")
            return
        except Exception as exc:  # pragma: no cover - network wait
            last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(
        "CDP port "
        f"{port} did not become ready: {last_error}. "
        "Run powershell -ExecutionPolicy Bypass -File "
        f"{PROJECT_ROOT}\\scripts\\start_edge_cdp.ps1 -Port {port}"
    )


def first_page_target(port: int) -> dict[str, Any]:
    targets = request_json(f"http://127.0.0.1:{port}/json/list")
    for target in targets:
        if target.get("type") == "page":
            return target
    raise RuntimeError("No page target available on CDP endpoint.")


def wait_for_login_page(client: CdpClient, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        last_state = client.evaluate(
            """
            ({
              href: location.href,
              pathname: location.pathname,
              body_text: document.body.innerText.slice(0, 800),
              input_count: document.querySelectorAll('input').length,
              button_count: document.querySelectorAll('button').length,
              has_username_input: Boolean(
                document.querySelector('input#username') ||
                document.querySelector('input[name="username"]') ||
                [...document.querySelectorAll('input')].some((input) =>
                  ['用户名', '个人账号'].includes(input.placeholder)
                )
              ),
              has_password_input: Boolean(
                document.querySelector('input[type="password"]') ||
                document.querySelector('input#password') ||
                document.querySelector('input[name="password"]')
              )
            })
            """
        )
        if (
            last_state.get("pathname") == "/login"
            and bool(last_state.get("has_username_input"))
            and bool(last_state.get("has_password_input"))
        ):
            return last_state
        time.sleep(0.5)
    raise RuntimeError(f"Login page did not render expected form controls: {last_state}")


def execute_browser_login(
    client: CdpClient,
    username: str,
    password: str,
) -> dict[str, Any]:
    login_script = f"""
    (async () => {{
      const inputs = [...document.querySelectorAll('input')];
      const usernameInput =
        document.querySelector('input#username') ||
        document.querySelector('input[name="username"]') ||
        inputs.find((input) => ['用户名', '个人账号'].includes(input.placeholder));
      const passwordInput =
        document.querySelector('input[type="password"]') ||
        document.querySelector('input#password') ||
        document.querySelector('input[name="password"]');
      const setNativeValue = (element, value) => {{
        const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set;
        const prototype = Object.getPrototypeOf(element);
        const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
        if (prototypeValueSetter && valueSetter !== prototypeValueSetter) {{
          prototypeValueSetter.call(element, value);
        }} else if (valueSetter) {{
          valueSetter.call(element, value);
        }} else {{
          element.value = value;
        }}
        element.dispatchEvent(new Event('input', {{ bubbles: true }}));
        element.dispatchEvent(new Event('change', {{ bubbles: true }}));
      }};
      if (!usernameInput || !passwordInput) {{
        return {{
          ok: false,
          stage: 'find-inputs',
          input_count: inputs.length,
          body_text: document.body.innerText.slice(0, 800)
        }};
      }}
      usernameInput.focus();
      setNativeValue(usernameInput, {json.dumps(username, ensure_ascii=False)});
      passwordInput.focus();
      setNativeValue(passwordInput, {json.dumps(password, ensure_ascii=False)});

      const normalizeText = (value) => (value || '').replace(/\\s+/g, '').trim();
      const loginButton =
        [...document.querySelectorAll('form button')].find((button) => {{
          const text = normalizeText(button.innerText || button.textContent || '');
          return text === '登录' && !button.disabled;
        }}) ||
        [...document.querySelectorAll('button')].find((button) => {{
          const text = normalizeText(button.innerText || button.textContent || '');
          return text === '登录' && !button.disabled;
        }});
      if (!loginButton) {{
        return {{
          ok: false,
          stage: 'find-submit',
          button_texts: [...document.querySelectorAll('button')].map((button) => ({{
            text: (button.innerText || button.textContent || '').trim(),
            type: button.type,
            disabled: button.disabled
          }}))
        }};
      }}
      loginButton.click();
      await new Promise((resolve) => setTimeout(resolve, 1800));
      return {{
        ok: Boolean(localStorage.getItem('aicomic_access_token')) || location.pathname !== '/login',
        stage: 'submitted',
        pathname: location.pathname,
        has_access_token: Boolean(localStorage.getItem('aicomic_access_token')),
        stored_user: localStorage.getItem('aicomic_current_user')
      }};
    }})()
    """
    return client.evaluate(login_script, await_promise=True)


def wait_for_dashboard(client: CdpClient, expected_path: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_state: dict[str, Any] = {}
    while time.time() < deadline:
        last_state = client.evaluate(
            """
            ({
              href: location.href,
              pathname: location.pathname,
              body_text: document.body ? document.body.innerText.slice(0, 1200) : '',
              card_count: document.querySelectorAll('.ant-card').length,
              has_dashboard_content: document.body ? document.body.innerText.includes('生产总览') : false,
              stored_user: localStorage.getItem('aicomic_current_user'),
              has_access_token: Boolean(localStorage.getItem('aicomic_access_token'))
            })
            """
        )
        if (
            last_state.get("pathname") == expected_path
            and bool(last_state.get("stored_user"))
            and bool(last_state.get("has_access_token"))
            and (
                bool(last_state.get("has_dashboard_content"))
                or int(last_state.get("card_count", 0)) > 0
            )
        ):
            return last_state
        time.sleep(0.5)
    raise RuntimeError(f"Dashboard did not become ready after login: {last_state}")


def collect_error_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for event in events:
        method = str(event.get("method", ""))
        params = event.get("params", {})
        if method == "Runtime.exceptionThrown":
            filtered.append(event)
            continue
        if method == "Runtime.consoleAPICalled" and str(params.get("type", "")) in {"error", "warning"}:
            filtered.append(event)
            continue
        if method == "Log.entryAdded":
            entry = params.get("entry", {})
            if str(entry.get("level", "")) in {"error", "warning"}:
                filtered.append(event)
    return filtered


def main() -> int:
    args = parse_args()
    if not args.password:
        raise SystemExit("Password is required. Pass --password or set AICOMIC_BROWSER_LOGIN_PASSWORD.")
    report_path = Path(args.report_path)
    client: CdpClient | None = None
    status = "failed"
    error_message = ""
    login_state: dict[str, Any] = {}
    submit_state: dict[str, Any] = {}
    dashboard_state: dict[str, Any] = {}
    page_target: dict[str, Any] = {}
    start_time = time.time()

    try:
        wait_for_cdp_server(args.cdp_port, args.timeout_seconds)
        page_target = first_page_target(args.cdp_port)
        client = CdpClient(page_target["webSocketDebuggerUrl"], timeout_seconds=10)
        for method in ("Page.enable", "Runtime.enable", "Log.enable", "Network.enable"):
            client.send(method)
        clear_browser_auth_state(client, args.login_url)
        client.send("Page.navigate", {"url": args.login_url})
        time.sleep(1)
        current_state = client.evaluate(
            """
            ({
              href: location.href,
              pathname: location.pathname
            })
            """
        )
        if current_state.get("pathname") == args.expected_path:
            clear_browser_auth_state(client, args.login_url)
            client.send("Page.navigate", {"url": args.login_url})
        login_state = wait_for_login_page(client, args.timeout_seconds)
        try:
            submit_state = execute_browser_login(
                client,
                username=args.username,
                password=args.password,
            )
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
        client.send("Page.navigate", {"url": build_dashboard_url(args.login_url, args.expected_path)})
        dashboard_state = wait_for_dashboard(client, args.expected_path, args.timeout_seconds)
        status = "passed"
    except Exception as exc:  # pragma: no cover - integration script
        error_message = str(exc)
    finally:
        error_events: list[dict[str, Any]] = collect_error_events(client.events if client else [])
        report = {
            "status": status,
            "error": error_message,
            "login_url": args.login_url,
            "expected_path": args.expected_path,
            "username": args.username,
            "password_supplied": bool(args.password),
            "browser_launched_by_script": False,
            "browser_pid": None,
            "cdp_port": args.cdp_port,
            "page_target": {
                "id": page_target.get("id", ""),
                "title": page_target.get("title", ""),
                "url": page_target.get("url", ""),
            },
            "login_state": login_state,
            "submit_state": submit_state,
            "dashboard_state": dashboard_state,
            "captured_error_event_count": len(error_events),
            "captured_error_events": error_events[:20],
            "duration_ms": int((time.time() - start_time) * 1000),
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if client is not None:
            client.close()

    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
