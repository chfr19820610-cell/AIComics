"""Production rehearsal — mock ComfyUI server fixture.

Only the FIXTURE_MODEL_MARKER constant is used in production code
(local_adapter.py). The mock server code was removed during v3.0
cleanup; this module is retained solely for the constant.
"""
from __future__ import annotations

FIXTURE_MODEL_MARKER = "AICOMIC_COMFYUI_FIXTURE_MODEL"
