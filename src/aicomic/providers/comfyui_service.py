from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aicomic.utils.atomic_io import atomic_write_json
import signal
import subprocess
import time
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

from aicomic.core.config import ProjectPaths


NO_PROXY_OPENER = build_opener(ProxyHandler({}))


@dataclass(frozen=True, slots=True)
class ComfyUIServiceConfig:
    project_root: Path
    runtime_root: Path
    comfyui_root: Path
    python_executable: Path
    extra_model_paths_config: Path
    output_directory: Path
    input_directory: Path
    temp_directory: Path
    reports_directory: Path
    state_directory: Path
    metadata_path: Path
    pid_path: Path
    host: str
    port: int

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def command(self) -> list[str]:
        return [
            str(self.python_executable),
            "main.py",
            "--listen",
            self.host,
            "--port",
            str(self.port),
            "--disable-auto-launch",
            "--extra-model-paths-config",
            str(self.extra_model_paths_config),
            "--output-directory",
            str(self.output_directory),
            "--input-directory",
            str(self.input_directory),
            "--temp-directory",
            str(self.temp_directory),
            "--log-stdout",
        ]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def resolve_comfyui_service_config(
    project_root: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8188,
) -> ComfyUIServiceConfig:
    root = (project_root or ProjectPaths.project_root()).resolve()
    runtime_root = root / "local_providers" / "comfyui" / "runtime"
    state_directory = root / "state" / "comfyui_service"
    return ComfyUIServiceConfig(
        project_root=root,
        runtime_root=runtime_root,
        comfyui_root=runtime_root / "ComfyUI",
        python_executable=runtime_root / ".venv" / "bin" / "python",
        extra_model_paths_config=runtime_root / "aicomic_extra_model_paths.yaml",
        output_directory=root / "state" / "comfyui_real_output",
        input_directory=root / "state" / "comfyui_real_input",
        temp_directory=root / "state" / "comfyui_real_temp",
        reports_directory=root / "reports",
        state_directory=state_directory,
        metadata_path=state_directory / "runtime.json",
        pid_path=state_directory / "runtime.pid",
        host=host,
        port=port,
    )


def ensure_runtime_directories(config: ComfyUIServiceConfig) -> None:
    config.reports_directory.mkdir(parents=True, exist_ok=True)
    config.state_directory.mkdir(parents=True, exist_ok=True)
    config.output_directory.mkdir(parents=True, exist_ok=True)
    config.input_directory.mkdir(parents=True, exist_ok=True)
    config.temp_directory.mkdir(parents=True, exist_ok=True)


def load_metadata(config: ComfyUIServiceConfig) -> dict[str, Any]:
    if not config.metadata_path.exists():
        return {}
    return json.loads(config.metadata_path.read_text(encoding="utf-8"))


def write_metadata(config: ComfyUIServiceConfig, payload: dict[str, Any]) -> None:
    config.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(config.metadata_path, payload)


def write_pid(config: ComfyUIServiceConfig, pid: int) -> None:
    config.pid_path.parent.mkdir(parents=True, exist_ok=True)
    config.pid_path.write_text(str(pid), encoding="utf-8")


def clear_pid(config: ComfyUIServiceConfig) -> None:
    if config.pid_path.exists():
        config.pid_path.unlink()


def read_known_pid(config: ComfyUIServiceConfig, metadata: dict[str, Any] | None = None) -> int | None:
    active_metadata = metadata if metadata is not None else load_metadata(config)
    raw_pid = active_metadata.get("pid")
    if raw_pid is None and config.pid_path.exists():
        raw_pid = config.pid_path.read_text(encoding="utf-8").strip()
    try:
        pid = int(str(raw_pid).strip())
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def pid_is_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def probe_comfyui_service(config: ComfyUIServiceConfig, timeout_seconds: float = 3.0) -> dict[str, Any]:
    try:
        with NO_PROXY_OPENER.open(f"{config.base_url}/system_stats", timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return {
            "reachable": False,
            "error": f"HTTPError {error.code}: {body}",
            "payload_keys": [],
            "device_types": [],
        }
    except URLError as error:
        return {
            "reachable": False,
            "error": f"URLError: {error.reason}",
            "payload_keys": [],
            "device_types": [],
        }
    except Exception as error:  # noqa: BLE001 - runtime probe should capture environment failures.
        return {
            "reachable": False,
            "error": str(error),
            "payload_keys": [],
            "device_types": [],
        }
    devices = payload.get("devices", []) if isinstance(payload, dict) else []
    device_types = []
    for item in devices:
        if isinstance(item, dict) and item.get("type"):
            device_types.append(str(item["type"]))
    return {
        "reachable": True,
        "error": "",
        "payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "device_types": device_types,
        "system": payload.get("system", {}) if isinstance(payload, dict) else {},
    }


def discover_running_pid(config: ComfyUIServiceConfig) -> int | None:
    if os.name != "posix":
        return None
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    matches: list[tuple[int, int]] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        raw_pid, command = parts
        if " main.py " not in f" {command} ":
            continue
        if f"--listen {config.host}" not in command or f"--port {config.port}" not in command:
            continue
        if (
            str(config.comfyui_root) not in command
            and str(config.python_executable) not in command
            and str(config.extra_model_paths_config) not in command
        ):
            continue
        try:
            pid = int(raw_pid)
        except ValueError:
            continue
        score = 0
        if str(config.python_executable) in command:
            score += 3
        if str(config.extra_model_paths_config) in command:
            score += 2
        if str(config.comfyui_root) in command:
            score += 1
        if "bash -lc" not in command and "zsh -lc" not in command:
            score += 1
        matches.append((score, pid))
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return matches[0][1]


def adopt_running_service(config: ComfyUIServiceConfig) -> dict[str, Any]:
    discovered_pid = discover_running_pid(config)
    if discovered_pid is None or not pid_is_alive(discovered_pid):
        return {}
    metadata = {
        "pid": discovered_pid,
        "host": config.host,
        "port": config.port,
        "base_url": config.base_url,
        "comfyui_root": str(config.comfyui_root),
        "python_executable": str(config.python_executable),
        "command": [],
        "log_path": "",
        "started_at": "",
        "adopted_at": now_iso(),
        "management_mode": "adopted",
    }
    write_metadata(config, metadata)
    write_pid(config, discovered_pid)
    return metadata


def inspect_comfyui_service(config: ComfyUIServiceConfig) -> dict[str, Any]:
    metadata = load_metadata(config)
    known_pid = read_known_pid(config, metadata)
    discovered_pid = discover_running_pid(config)
    health = probe_comfyui_service(config)
    pid = known_pid if pid_is_alive(known_pid) else discovered_pid if pid_is_alive(discovered_pid) else None
    if pid_is_alive(known_pid):
        management_mode = str(metadata.get("management_mode", "managed") or "managed")
    elif pid_is_alive(discovered_pid):
        management_mode = "unmanaged"
    else:
        management_mode = "stopped"
    return {
        "status": "ready" if health["reachable"] else "stopped",
        "management_mode": management_mode,
        "pid": pid,
        "known_pid": known_pid,
        "discovered_pid": discovered_pid,
        "pid_alive": pid_is_alive(pid),
        "base_url": config.base_url,
        "host": config.host,
        "port": config.port,
        "metadata_path": str(config.metadata_path),
        "pid_path": str(config.pid_path),
        "log_path": str(metadata.get("log_path", "")).strip(),
        "started_at": str(metadata.get("started_at", "")).strip(),
        "adopted_at": str(metadata.get("adopted_at", "")).strip(),
        "command": metadata.get("command", []),
        "health": health,
    }


def validate_runtime_files(config: ComfyUIServiceConfig) -> list[str]:
    errors: list[str] = []
    if not config.comfyui_root.exists():
        errors.append(f"ComfyUI root missing: {config.comfyui_root}")
    if not config.python_executable.exists():
        errors.append(f"ComfyUI python missing: {config.python_executable}")
    if not config.extra_model_paths_config.exists():
        errors.append(f"extra_model_paths config missing: {config.extra_model_paths_config}")
    return errors


def build_start_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def stop_process(pid: int, force: bool = False) -> None:
    if not pid_is_alive(pid):
        return
    if os.name == "posix":
        try:
            process_group = os.getpgid(pid)
        except OSError:
            process_group = None
        if process_group is not None:
            os.killpg(process_group, signal.SIGKILL if force else signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
        return
    os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)


def wait_for_pid_exit(pid: int, timeout_seconds: float, poll_interval_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not pid_is_alive(pid):
            return True
        time.sleep(poll_interval_seconds)
    return not pid_is_alive(pid)


def run_comfyui_service_action(
    action: str,
    project_root: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8188,
    wait_timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
    force: bool = False,
) -> dict[str, Any]:
    config = resolve_comfyui_service_config(project_root, host=host, port=port)
    ensure_runtime_directories(config)
    status_before = inspect_comfyui_service(config)
    runtime_errors = validate_runtime_files(config)
    result: dict[str, Any] = {
        "action": action,
        "run_at": now_iso(),
        "base_url": config.base_url,
        "runtime_errors": runtime_errors,
        "status_before": status_before,
        "status_after": status_before,
        "report_path": "",
    }

    if action == "status":
        if status_before["management_mode"] == "unmanaged" and status_before["health"]["reachable"]:
            adopt_running_service(config)
            result["status_after"] = inspect_comfyui_service(config)
        return result

    if action not in {"start", "stop", "restart"}:
        raise ValueError(f"Unsupported action: {action}")

    if runtime_errors and action in {"start", "restart"}:
        result["status_after"] = inspect_comfyui_service(config)
        return result

    if status_before["management_mode"] == "unmanaged" and status_before["health"]["reachable"]:
        adopt_running_service(config)
        status_before = inspect_comfyui_service(config)
        result["status_before"] = status_before

    if action in {"stop", "restart"}:
        pid = status_before["pid"]
        exited = True
        if pid is not None:
            stop_process(pid, force=False)
            exited = wait_for_pid_exit(pid, wait_timeout_seconds, min(poll_interval_seconds, 1.0))
            if not exited and force:
                stop_process(pid, force=True)
                exited = wait_for_pid_exit(pid, min(wait_timeout_seconds, 10.0), min(poll_interval_seconds, 1.0))
            metadata = load_metadata(config)
            if metadata:
                metadata["last_stop_attempt_at"] = now_iso()
                metadata["last_stop_force"] = force
                metadata["last_stop_exited"] = exited
                metadata["pid"] = None if exited else pid
                if exited:
                    metadata["stopped_at"] = now_iso()
                write_metadata(config, metadata)
            if exited:
                clear_pid(config)
            else:
                write_pid(config, pid)
        result["stop_attempted"] = pid is not None
        result["stop_exited"] = exited
        result["status_after"] = inspect_comfyui_service(config)
        if action == "stop":
            return result

    status_after_stop = inspect_comfyui_service(config)
    if status_after_stop["health"]["reachable"]:
        result["status_after"] = status_after_stop
        return result

    log_path = config.reports_directory / f"comfyui_service_{timestamp_slug()}.log"
    with log_path.open("ab") as log_file:
        if os.name == "nt":
            process = subprocess.Popen(  # noqa: S603
                config.command,
                cwd=config.comfyui_root,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=build_start_environment(),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            process = subprocess.Popen(  # noqa: S603
                config.command,
                cwd=config.comfyui_root,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=build_start_environment(),
                start_new_session=True,
            )

    metadata = {
        "pid": process.pid,
        "host": config.host,
        "port": config.port,
        "base_url": config.base_url,
        "comfyui_root": str(config.comfyui_root),
        "python_executable": str(config.python_executable),
        "command": config.command,
        "log_path": str(log_path),
        "started_at": now_iso(),
        "management_mode": "managed",
    }
    write_metadata(config, metadata)
    write_pid(config, process.pid)

    deadline = time.time() + wait_timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            break
        status_after = inspect_comfyui_service(config)
        if status_after["health"]["reachable"]:
            result["status_after"] = status_after
            return result
        time.sleep(poll_interval_seconds)

    result["status_after"] = inspect_comfyui_service(config)
    return result


def write_comfyui_service_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = dict(payload)
    serializable["report_path"] = str(path)
    atomic_write_json(path, serializable)
