from __future__ import annotations

import argparse
import signal
import time

from aicomic.security.production_rehearsal import run_mock_comfyui_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an AIComics mock ComfyUI server for local provider rehearsal.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18188)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    should_stop = False

    def stop(_signum, _frame) -> None:
        nonlocal should_stop
        should_stop = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with run_mock_comfyui_server(args.host, args.port) as server_info:
        print(f"mock_comfyui_base_url={server_info['base_url']}", flush=True)
        while not should_stop:
            time.sleep(0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
