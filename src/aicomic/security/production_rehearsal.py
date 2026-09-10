"""Production rehearsal — mock ComfyUI server fixture.

Only the FIXTURE_MODEL_MARKER constant is used in production code
(local_adapter.py). The mock server code below is retained for
integration testing but is not imported by any production module.
"""
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
