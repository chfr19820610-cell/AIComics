#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
CACHE_DIR = STATE_DIR / "docker_image_cache"
IMAGE_NAME = "aicomic-comfyui-sidecar:local"
CACHE_TAR = CACHE_DIR / "aicomic-comfyui-sidecar-local.tar"
CACHE_MANIFEST = CACHE_DIR / "aicomic-comfyui-sidecar-local.json"
DOCKER_BIN = os.environ.get("DOCKER_BIN") or shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"


def run_docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [DOCKER_BIN, *args],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"docker {' '.join(args)} failed").strip())
    return result


def image_info(image: str) -> dict[str, Any] | None:
    result = run_docker("image", "inspect", image, "--format", "{{json .}}", check=False)
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def load_cache_manifest() -> dict[str, Any]:
    if not CACHE_MANIFEST.exists():
        return {}
    try:
        payload = json.loads(CACHE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_cache_manifest(payload: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_MANIFEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_cache(image: str = IMAGE_NAME) -> dict[str, Any]:
    info = image_info(image)
    if info is None:
        raise RuntimeError(f"Image not found: {image}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_TAR.exists():
        CACHE_TAR.unlink()
    run_docker("save", "-o", str(CACHE_TAR), image)
    size_bytes = CACHE_TAR.stat().st_size if CACHE_TAR.exists() else 0
    manifest = {
        "image": image,
        "image_id": str(info.get("Id", "")),
        "created_at": str(info.get("Created", "")),
        "cache_tar": str(CACHE_TAR),
        "size_bytes": size_bytes,
        "exported_at": datetime_now(),
    }
    write_cache_manifest(manifest)
    return manifest


def import_cache() -> dict[str, Any]:
    if not CACHE_TAR.exists():
        raise RuntimeError(f"Missing cached image tar: {CACHE_TAR}")
    result = run_docker("load", "-i", str(CACHE_TAR))
    manifest = load_cache_manifest()
    manifest.update(
        {
            "imported_at": datetime_now(),
            "load_stdout": result.stdout.strip(),
            "load_stderr": result.stderr.strip(),
        }
    )
    write_cache_manifest(manifest)
    return manifest


def ensure_cache(image: str = IMAGE_NAME) -> dict[str, Any]:
    info = image_info(image)
    manifest = load_cache_manifest()
    if info is not None:
        if not CACHE_TAR.exists():
            return export_cache(image)
        manifest.update(
            {
                "image": image,
                "image_id": str(info.get("Id", "")),
                "created_at": str(info.get("Created", "")),
                "cache_tar": str(CACHE_TAR),
                "size_bytes": CACHE_TAR.stat().st_size,
                "verified_at": datetime_now(),
            }
        )
        write_cache_manifest(manifest)
        return manifest
    return import_cache()


def status(image: str = IMAGE_NAME) -> dict[str, Any]:
    info = image_info(image)
    manifest = load_cache_manifest()
    return {
        "image": image,
        "image_present": info is not None,
        "image_id": str(info.get("Id", "")) if info else "",
        "cache_tar": str(CACHE_TAR),
        "cache_tar_exists": CACHE_TAR.exists(),
        "cache_tar_size_bytes": CACHE_TAR.stat().st_size if CACHE_TAR.exists() else 0,
        "manifest": manifest,
    }


def datetime_now() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat()


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    command = args[0] if args else "status"
    image = args[1] if len(args) > 1 else IMAGE_NAME
    if command == "status":
        payload = status(image)
    elif command == "export":
        payload = export_cache(image)
    elif command == "import":
        payload = import_cache()
    elif command == "ensure":
        payload = ensure_cache(image)
    else:
        raise SystemExit(f"Unsupported command: {command}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
