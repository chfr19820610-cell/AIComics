from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def index_import_root(import_root: Path) -> dict[str, Path]:
    indexed_files: dict[str, Path] = {}
    if not import_root.exists():
        return indexed_files

    for path in import_root.rglob("*"):
        if path.is_file():
            indexed_files[path.name.lower()] = path
    return indexed_files


def import_manual_outputs(
    provider_requests: dict[str, Any],
    import_root: Path,
    overwrite: bool = False,
) -> dict[str, object]:
    indexed_files = index_import_root(import_root)
    imported_items: list[dict[str, object]] = []
    missing_items: list[dict[str, object]] = []
    skipped_items: list[dict[str, object]] = []

    for request in provider_requests.get("requests", []):
        payload = request.get("payload", {})
        output_path = Path(str(payload.get("output_path", "")))
        filename = output_path.name.lower()
        source_path = indexed_files.get(filename)

        if source_path is None:
            missing_items.append(
                {
                    "request_id": str(request.get("request_id", "")),
                    "job_id": str(payload.get("job_id", "")),
                    "filename": output_path.name,
                    "output_path": str(output_path),
                    "reason": "source_not_found",
                }
            )
            continue

        if output_path.exists() and not overwrite:
            skipped_items.append(
                {
                    "request_id": str(request.get("request_id", "")),
                    "job_id": str(payload.get("job_id", "")),
                    "filename": output_path.name,
                    "output_path": str(output_path),
                    "reason": "target_exists",
                }
            )
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)
        imported_items.append(
            {
                "request_id": str(request.get("request_id", "")),
                "job_id": str(payload.get("job_id", "")),
                "filename": output_path.name,
                "source_path": str(source_path),
                "output_path": str(output_path),
                "size": output_path.stat().st_size,
            }
        )

    return {
        "import_root": str(import_root),
        "imported_count": len(imported_items),
        "missing_count": len(missing_items),
        "skipped_count": len(skipped_items),
        "imported_items": imported_items,
        "missing_items": missing_items,
        "skipped_items": skipped_items,
    }


def write_manual_import_report(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
