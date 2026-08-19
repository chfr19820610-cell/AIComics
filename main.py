"""ASGI entrypoint for `hermes verify` and container runtime.

Single source of truth for serving the AIComics web API.
Delegates to the real app in web.backend.app.

Works regardless of cwd or PYTHONPATH: ensures the project root
(this file's parent directory) is on sys.path before importing.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable even when cwd != project root
# (e.g. container started from /, gunicorn workers, CI runners).
_project_root = str(Path(__file__).resolve().parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from web.backend.app import app  # noqa: F401,E402
