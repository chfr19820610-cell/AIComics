from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_sidecar_local_path(raw_path: str) -> str:
    path = Path(raw_path).expanduser()
    if path.exists():
        return str(path)
    parts = path.parts
    marker = ("local_providers", "piper")
    marker_length = len(marker)
    for index in range(len(parts) - marker_length + 1):
        if parts[index : index + marker_length] == marker:
            candidate = PROJECT_ROOT / Path(*parts[index:])
            if candidate.exists():
                return str(candidate)
    return raw_path


def build_piper_command(payload: dict[str, Any], output_path: Path) -> list[str]:
    model_path = str(payload.get("model_path", "")).strip()
    if not model_path:
        raise ValueError("model_path is required")
    model_path = resolve_sidecar_local_path(model_path)
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_local_piper.py"),
        "--model",
        model_path,
        "--output_file",
        str(output_path),
    ]
    config_path = str(payload.get("config_path", "")).strip()
    if config_path:
        config_path = resolve_sidecar_local_path(config_path)
        command.extend(["--config", config_path])
    speaker_id = str(payload.get("speaker_id", "")).strip()
    if speaker_id:
        command.extend(["--speaker", speaker_id])
    extra_args = str(payload.get("extra_args", "")).strip()
    if extra_args:
        command.extend(extra_args.split())
    return command


class PiperHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "AIComicsPiperHTTP/1.0"

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - BaseHTTPRequestHandler API.
        return

    def write_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        if self.path != "/health":
            self.write_json(404, {"error": "not_found", "path": self.path})
            return
        self.write_json(
            200,
            {
                "status": "ok",
                "mode": "http_service",
                "project_root": str(PROJECT_ROOT),
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        if self.path != "/synthesize":
            self.write_json(404, {"error": "not_found", "path": self.path})
            return
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.write_json(400, {"error": "invalid_json"})
            return
        text = str(payload.get("text", ""))
        timeout_seconds = int(payload.get("timeout_seconds", 120) or 120)
        with tempfile.TemporaryDirectory(prefix="aicomic_piper_http_") as temp_dir:
            output_path = Path(temp_dir) / "piper_output.wav"
            try:
                command = build_piper_command(payload, output_path)
                result = subprocess.run(
                    command,
                    cwd=str(PROJECT_ROOT),
                    input=text,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                self.write_json(504, {"error": "timeout", "timeout_seconds": timeout_seconds})
                return
            except ValueError as error:
                self.write_json(400, {"error": "invalid_request", "detail": str(error)})
                return
            if result.returncode != 0:
                self.write_json(
                    500,
                    {
                        "error": "piper_failed",
                        "return_code": result.returncode,
                        "stderr": (result.stderr or result.stdout or "").strip()[-2000:],
                    },
                )
                return
            if not output_path.exists():
                self.write_json(500, {"error": "missing_output"})
                return
            audio_bytes = output_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(audio_bytes)))
        self.end_headers()
        self.wfile.write(audio_bytes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIComics Piper HTTP sidecar")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5002)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PiperHTTPRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
