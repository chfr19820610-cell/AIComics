from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.cli.main import main as cli_main


def main() -> int:
    sys.argv = [sys.argv[0], "local-provider-live-smoke", *sys.argv[1:]]
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
