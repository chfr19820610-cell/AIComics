from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class SpaRequestHandler(SimpleHTTPRequestHandler):
    def route_spa_request(self) -> None:
        requested_url_path = self.path.split("?", 1)[0]
        if requested_url_path == "/favicon.ico":
            return
        requested_path = Path(self.translate_path(requested_url_path))
        if not requested_path.exists() and not Path(requested_url_path).suffix:
            self.path = "/index.html"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        if self.path.split("?", 1)[0] == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.route_spa_request()
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        self.route_spa_request()
        super().do_HEAD()

    def send_head(self):  # type: ignore[override]
        requested_path = Path(self.translate_path(self.path))
        if not requested_path.exists():
            accept_header = self.headers.get("Accept", "")
            if "text/html" in accept_header or not requested_path.suffix:
                self.path = "/index.html"
        return super().send_head()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the built frontend as an SPA.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    directory = args.directory.resolve()
    if not directory.exists():
        raise SystemExit(f"frontend dist directory does not exist: {directory}")
    if not (directory / "index.html").exists():
        raise SystemExit(f"frontend dist index.html does not exist: {directory / 'index.html'}")

    handler = partial(SpaRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"serving frontend from {directory} on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
