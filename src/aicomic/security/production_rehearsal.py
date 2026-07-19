from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import threading
from typing import Any, Iterator
from urllib.parse import parse_qs, urlparse
import uuid


FIXTURE_MODEL_MARKER = "AICOMIC_COMFYUI_FIXTURE_MODEL"
MOCK_IMAGE_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00"
    b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)
MOCK_VIDEO_BYTES = b"AICOMIC_MOCK_COMFYUI_VIDEO_BYTES"


def find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def load_model_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def prepare_comfyui_fixture_models(
    model_root: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = load_model_manifest(manifest_path)
    providers = manifest.get("providers", {}) if isinstance(manifest, dict) else {}
    created_paths: list[str] = []
    for requirements in providers.values():
        if not isinstance(requirements, list):
            continue
        for item in requirements:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename", "")).strip()
            if not filename:
                continue
            subdir = str(item.get("subdir", "")).strip().strip("/")
            target_path = model_root / subdir / filename if subdir else model_root / filename
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_path.exists():
                target_path.write_text(
                    f"{FIXTURE_MODEL_MARKER}\nfilename={filename}\nsubdir={subdir}\n",
                    encoding="utf-8",
                )
            created_paths.append(str(target_path))
    return {
        "model_root": str(model_root),
        "manifest_path": str(manifest_path),
        "fixture_model_count": len(created_paths),
        "fixture_model_paths": created_paths,
    }


class MockComfyUIState:
    def __init__(self) -> None:
        self.prompts: dict[str, dict[str, Any]] = {}


class MockComfyUIHandler(BaseHTTPRequestHandler):
    server_version = "AIComicsMockComfyUI/1.0"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - BaseHTTPRequestHandler API.
        return

    @property
    def state(self) -> MockComfyUIState:
        return self.server.mock_state  # type: ignore[attr-defined]

    def write_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        parsed = urlparse(self.path)
        if parsed.path == "/system_stats":
            self.write_json(
                200,
                {
                    "aicomic_mock_comfyui": True,
                    "system": {"os": "mock", "python_version": "mock"},
                    "devices": [],
                },
            )
            return
        if parsed.path.startswith("/history/"):
            prompt_id = parsed.path.rsplit("/", 1)[-1]
            prompt_meta = self.state.prompts.get(prompt_id, {"artifact_kind": "image"})
            artifact_kind = str(prompt_meta.get("artifact_kind", "image"))
            collection_name = "videos" if artifact_kind == "video" else "images"
            filename = f"{prompt_id}.mp4" if artifact_kind == "video" else f"{prompt_id}.png"
            self.write_json(
                200,
                {
                    prompt_id: {
                        "outputs": {
                            "mock_output": {
                                collection_name: [
                                    {
                                        "filename": filename,
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        }
                    }
                },
            )
            return
        if parsed.path == "/view":
            query = parse_qs(parsed.query)
            filename = str((query.get("filename") or ["mock.png"])[0])
            body = MOCK_VIDEO_BYTES if filename.endswith(".mp4") else MOCK_IMAGE_BYTES
            content_type = "video/mp4" if filename.endswith(".mp4") else "image/png"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.write_json(404, {"error": "not_found", "path": parsed.path})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        parsed = urlparse(self.path)
        if parsed.path != "/prompt":
            self.write_json(404, {"error": "not_found", "path": parsed.path})
            return
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        prompt = payload.get("prompt", {}) if isinstance(payload, dict) else {}
        artifact_kind = "image"
        if isinstance(prompt, dict):
            for node in prompt.values():
                if isinstance(node, dict) and str(node.get("class_type", "")).lower() in {"savevideo", "createvideo"}:
                    artifact_kind = "video"
                    break
        prompt_id = f"mock_{uuid.uuid4().hex}"
        self.state.prompts[prompt_id] = {"artifact_kind": artifact_kind}
        self.write_json(200, {"prompt_id": prompt_id, "number": len(self.state.prompts), "node_errors": {}})


class MockComfyUIServer(ThreadingHTTPServer):
    mock_state: MockComfyUIState


@contextmanager
def run_mock_comfyui_server(host: str = "127.0.0.1", port: int | None = None) -> Iterator[dict[str, Any]]:
    selected_port = port or find_free_port(host)
    server = MockComfyUIServer((host, selected_port), MockComfyUIHandler)
    server.mock_state = MockComfyUIState()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {
            "host": host,
            "port": selected_port,
            "base_url": f"http://{host}:{selected_port}",
            "server_mode": "mock",
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@contextmanager
def temporary_environment(values: dict[str, str]) -> Iterator[None]:
    previous_values = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, previous_value in previous_values.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value


def build_rehearsal_environment(
    project_root: Path,
    comfyui_base_url: str,
    model_root: Path,
) -> dict[str, str]:
    return {
        "AICOMIC_WEB_CONFIG_PATH": str(project_root / "config" / "web.production.example.yaml"),
        "AICOMIC_EDITION_CONFIG_PATH": str(project_root / "config" / "edition.production.yaml"),
        "AICOMIC_JWT_SECRET": secrets.token_urlsafe(48),
        "AICOMIC_NORMAL_USER_PASSWORD": "creator-rehearsal-password",
        "AICOMIC_COMFYUI_BASE_URL": comfyui_base_url,
        "AICOMIC_COMFYUI_MODEL_ROOT": str(model_root),
    }
