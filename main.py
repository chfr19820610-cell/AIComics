"""ASGI entrypoint for `hermes verify` and container runtime.
Delegates to the real app in web.backend.app.
"""
from web.backend.app import app  # noqa: F401
