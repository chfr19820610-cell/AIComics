from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_PIPER_PYTHON = PROJECT_ROOT / "local_providers" / "piper" / "python"


def load_piper_main():
    try:
        from piper.__main__ import main
    except ModuleNotFoundError:
        if LOCAL_PIPER_PYTHON.exists():
            sys.path.insert(0, str(LOCAL_PIPER_PYTHON))
            from piper.__main__ import main
        else:
            raise
    return main


if __name__ == "__main__":
    raise SystemExit(load_piper_main()())
