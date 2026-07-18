from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid

from aicomic.providers.provider_planner import load_provider_settings
from aicomic.security.production_rehearsal import FIXTURE_MODEL_MARKER


LOCAL_COMFYUI_PROVIDER = "local_comfyui_image"
LOCAL_COMFYUI_VIDEO_PROVIDER = "local_comfyui_video"
LOCAL_PIPER_PROVIDER = "local_piper_tts"
LOCAL_COMFYUI_PROVIDERS = {LOCAL_COMFYUI_PROVIDER, LOCAL_COMFYUI_VIDEO_PROVIDER}
LOCAL_EXECUTION_PROVIDERS = LOCAL_COMFYUI_PROVIDERS | {LOCAL_PIPER_PROVIDER}
NO_PROXY_OPENER = build_opener(ProxyHandler({}))
COMFYUI_MODEL_LOADER_CLASS_TYPES = {
    "CLIPLoader",
    "DualCLIPLoader",
    "TripleCLIPLoader",
    "VAELoader",
    "UNETLoader",
    "CheckpointLoader",
    "CheckpointLoaderSimple",
    "LoraLoader",
    "ControlNetLoader",
}


def resolve_config_path(raw_path: str, base_dir: Path) -> Path | None:
    value = raw_path.strip().strip("\"'")
    if value.lower() in {"null", "none", "~"}:
        value = ""
    if not value:
        return None
    expanded = os.path.expandvars(os.path.expanduser(value))
    path = Path(expanded)
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def parse_int(raw_value: object, default: int) -> int:
    value = str(raw_value).strip()
    if value.isdigit():
        return int(value)
    return default


def parse_float(raw_value: object, default: float) -> float:
    try:
        return float(str(raw_value).strip())
    except ValueError:
        return default


def optional_string(raw_value: object) -> str:
    value = str(raw_value).strip().strip("\"'")
    if value.lower() in {"null", "none", "~"}:
        return ""
    return value


def command_parts(command: str) -> list[str]:
    parts = shlex.split(command)
    return parts if parts else ["piper"]


def command_executable(command: str) -> str:
    parts = command_parts(command)
    executable = parts[0]
    if Path(executable).name == "env":
        for part in parts[1:]:
            if "=" in part and not part.startswith("-"):
                continue
            if part.startswith("-"):
                continue
            executable = part
            break
    return executable


def command_available(command: str) -> bool:
    executable = command_executable(command)
    if Path(executable).is_absolute():
        return Path(executable).exists()
    return shutil.which(executable) is not None


def substitute_placeholders(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, str):
        if value in replacements:
            return replacements[value]
        updated = value
        for key, replacement in replacements.items():
            updated = updated.replace(key, str(replacement))
        return updated
    if isinstance(value, list):
        return [substitute_placeholders(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: substitute_placeholders(item, replacements) for key, item in value.items()}
    return value


def inspect_comfyui_workflow_path(workflow_path: Path | None) -> dict[str, Any]:
    workflow_configured = workflow_path is not None
    workflow_exists = bool(workflow_path and workflow_path.exists())
    workflow_is_file = bool(workflow_path and workflow_path.is_file())
    workflow_valid_json = False
    workflow_api_format = False
    workflow_node_count = 0
    workflow_error = ""

    if workflow_is_file and workflow_path is not None:
        try:
            workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            workflow_error = f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        except OSError as error:
            workflow_error = f"Cannot read workflow file: {error}"
        else:
            if isinstance(workflow, dict) and workflow:
                workflow_valid_json = True
                api_nodes = {
                    key: value
                    for key, value in workflow.items()
                    if isinstance(value, dict) and key != "_meta"
                }
                workflow_node_count = len(api_nodes)
                workflow_api_format = bool(api_nodes) and all(
                    isinstance(value.get("class_type"), str)
                    and bool(value.get("class_type", "").strip())
                    and isinstance(value.get("inputs", {}), dict)
                    for value in api_nodes.values()
                )
                if not workflow_api_format:
                    workflow_error = "Workflow JSON must be ComfyUI API prompt format with class_type and inputs per node."
            elif isinstance(workflow, dict):
                workflow_error = "Workflow JSON must be a non-empty object."
            else:
                workflow_error = "Workflow JSON must be an object exported in ComfyUI API format."
    elif workflow_exists:
        workflow_error = "workflow_path points to a directory; configure a JSON file inside the workflow folder."
    elif workflow_configured:
        workflow_error = "Configured workflow_path does not exist yet."

    return {
        "workflow_configured": workflow_configured,
        "workflow_exists": workflow_exists,
        "workflow_is_file": workflow_is_file,
        "workflow_valid_json": workflow_valid_json,
        "workflow_api_format": workflow_api_format,
        "workflow_node_count": workflow_node_count,
        "workflow_error": workflow_error,
    }


def inspect_comfyui_workflow_model_usage(workflow_path: Path | None) -> dict[str, Any]:
    loader_nodes: list[dict[str, str]] = []
    if workflow_path is None or not workflow_path.exists() or not workflow_path.is_file():
        return {
            "workflow_requires_model_files": True,
            "workflow_model_loader_count": 0,
            "workflow_model_loader_nodes": loader_nodes,
            "workflow_model_usage_note": "Workflow is unavailable; model requirements remain enforced.",
        }

    try:
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "workflow_requires_model_files": True,
            "workflow_model_loader_count": 0,
            "workflow_model_loader_nodes": loader_nodes,
            "workflow_model_usage_note": "Workflow cannot be inspected; model requirements remain enforced.",
        }

    if not isinstance(workflow, dict):
        return {
            "workflow_requires_model_files": True,
            "workflow_model_loader_count": 0,
            "workflow_model_loader_nodes": loader_nodes,
            "workflow_model_usage_note": "Workflow is not API prompt JSON; model requirements remain enforced.",
        }

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", "")).strip()
        normalized_class_type = class_type.lower()
        if class_type in COMFYUI_MODEL_LOADER_CLASS_TYPES or "loader" in normalized_class_type:
            loader_nodes.append({"node_id": str(node_id), "class_type": class_type})

    requires_model_files = bool(loader_nodes)
    note = (
        "Workflow includes ComfyUI model loader nodes; configured model requirements are enforced."
        if requires_model_files
        else "Workflow has no model loader nodes; this smoke tier validates ComfyUI API/output writeback without loading model weights."
    )
    return {
        "workflow_requires_model_files": requires_model_files,
        "workflow_model_loader_count": len(loader_nodes),
        "workflow_model_loader_nodes": loader_nodes,
        "workflow_model_usage_note": note,
    }


def inspect_comfyui_model_requirements(
    provider: str,
    model_root: Path | None,
    model_manifest_path: Path | None,
) -> dict[str, Any]:
    manifest_configured = model_manifest_path is not None
    manifest_exists = bool(model_manifest_path and model_manifest_path.exists())
    manifest_is_file = bool(model_manifest_path and model_manifest_path.is_file())
    model_root_configured = model_root is not None
    model_root_exists = bool(model_root and model_root.exists())
    model_root_is_dir = bool(model_root and model_root.is_dir())
    manifest_error = ""
    model_error = ""
    required_models: list[dict[str, Any]] = []

    if not manifest_configured:
        manifest_error = "ComfyUI model manifest is not configured."
    elif not manifest_exists:
        manifest_error = "Configured ComfyUI model manifest does not exist yet."
    elif not manifest_is_file:
        manifest_error = "ComfyUI model manifest path points to a directory."
    else:
        try:
            manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            manifest_error = f"Invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        except OSError as error:
            manifest_error = f"Cannot read ComfyUI model manifest: {error}"
        else:
            providers = manifest.get("providers", {}) if isinstance(manifest, dict) else {}
            provider_requirements = providers.get(provider, []) if isinstance(providers, dict) else []
            if isinstance(provider_requirements, list):
                required_models = [
                    item
                    for item in provider_requirements
                    if isinstance(item, dict) and bool(str(item.get("filename", "")).strip())
                ]
            if not required_models:
                manifest_error = f"No model requirements registered for provider: {provider}"

    if not model_root_configured:
        model_error = "ComfyUI model_root is not configured."
    elif not model_root_exists:
        model_error = "Configured ComfyUI model_root does not exist yet."
    elif not model_root_is_dir:
        model_error = "ComfyUI model_root must be a directory."

    present_required_models: list[dict[str, str]] = []
    missing_required_models: list[dict[str, str]] = []
    fixture_required_models: list[dict[str, str]] = []
    if model_root is not None and model_root_is_dir:
        for item in required_models:
            filename = str(item.get("filename", "")).strip()
            subdir = str(item.get("subdir", "")).strip().strip("/")
            relative_path = Path(subdir) / filename if subdir else Path(filename)
            model_path = model_root / relative_path
            model_item = {
                "filename": filename,
                "subdir": subdir,
                "relative_path": str(relative_path),
                "path": str(model_path),
                "source": str(item.get("source", "")),
            }
            if model_path.exists() and model_path.is_file():
                present_required_models.append(model_item)
                if is_comfyui_fixture_model(model_path):
                    fixture_required_models.append(model_item)
            else:
                missing_required_models.append(model_item)
    elif required_models:
        for item in required_models:
            filename = str(item.get("filename", "")).strip()
            subdir = str(item.get("subdir", "")).strip().strip("/")
            relative_path = Path(subdir) / filename if subdir else Path(filename)
            missing_required_models.append(
                {
                    "filename": filename,
                    "subdir": subdir,
                    "relative_path": str(relative_path),
                    "path": str((model_root / relative_path) if model_root else relative_path),
                    "source": str(item.get("source", "")),
                }
            )

    required_model_count = len(required_models)
    required_models_ready = (
        manifest_configured
        and manifest_exists
        and manifest_is_file
        and model_root_configured
        and model_root_exists
        and model_root_is_dir
        and required_model_count > 0
        and not missing_required_models
    )
    return {
        "model_manifest_configured": manifest_configured,
        "model_manifest_exists": manifest_exists,
        "model_manifest_is_file": manifest_is_file,
        "model_manifest_path": str(model_manifest_path) if model_manifest_path else "",
        "model_manifest_error": manifest_error,
        "model_root_configured": model_root_configured,
        "model_root_exists": model_root_exists,
        "model_root_is_dir": model_root_is_dir,
        "model_root": str(model_root) if model_root else "",
        "model_root_error": model_error,
        "required_model_count": required_model_count,
        "present_required_model_count": len(present_required_models),
        "missing_required_model_count": len(missing_required_models),
        "fixture_required_model_count": len(fixture_required_models),
        "present_required_models": present_required_models,
        "missing_required_models": missing_required_models,
        "fixture_required_models": fixture_required_models,
        "required_models_ready": required_models_ready,
    }


def is_comfyui_fixture_model(model_path: Path) -> bool:
    try:
        with model_path.open("rb") as file:
            marker = file.read(len(FIXTURE_MODEL_MARKER) + 8)
    except OSError:
        return False
    return FIXTURE_MODEL_MARKER.encode("utf-8") in marker


def comfyui_server_available(base_url: str, timeout_seconds: float = 1.0) -> tuple[bool, str]:
    try:
        get_json(f"{base_url}/system_stats", timeout_seconds)
    except Exception as error:  # noqa: BLE001 - this is a readiness probe, not execution.
        return False, str(error)
    return True, ""


def probe_comfyui_server(base_url: str, timeout_seconds: float = 1.0) -> dict[str, Any]:
    try:
        payload = get_json(f"{base_url}/system_stats", timeout_seconds)
    except Exception as error:  # noqa: BLE001 - this is a readiness probe, not execution.
        return {
            "comfyui_server_available": False,
            "comfyui_server_error": str(error),
            "comfyui_server_mode": "unavailable",
            "comfyui_server_payload_keys": [],
        }
    return {
        "comfyui_server_available": True,
        "comfyui_server_error": "",
        "comfyui_server_mode": "mock" if bool(payload.get("aicomic_mock_comfyui", False)) else "live",
        "comfyui_server_payload_keys": sorted(str(key) for key in payload.keys()),
    }


def probe_piper_service(base_url: str, timeout_seconds: float = 1.0) -> dict[str, Any]:
    normalized_url = base_url.rstrip("/")
    try:
        payload = get_json(f"{normalized_url}/health", timeout_seconds)
    except Exception as error:  # noqa: BLE001 - readiness probe should return diagnostics instead of raising.
        return {
            "piper_service_configured": True,
            "piper_service_available": False,
            "piper_service_error": str(error),
            "piper_service_mode": "unavailable",
            "piper_service_payload_keys": [],
        }
    return {
        "piper_service_configured": True,
        "piper_service_available": True,
        "piper_service_error": "",
        "piper_service_mode": str(payload.get("mode", "http_service") or "http_service"),
        "piper_service_payload_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
    }


def inspect_piper_paths(model_path: Path | None, config_path: Path | None) -> dict[str, Any]:
    model_configured = model_path is not None
    model_exists = bool(model_path and model_path.exists())
    model_is_file = bool(model_path and model_path.is_file())
    config_configured = config_path is not None
    config_exists = bool(config_path and config_path.exists())
    config_is_file = bool(config_path and config_path.is_file())
    model_error = ""
    config_error = ""

    if model_exists and not model_is_file:
        model_error = "model_path points to a directory; configure a Piper .onnx model file."
    elif model_configured and not model_exists:
        model_error = "Configured model_path does not exist yet."
    elif not model_configured:
        model_error = "Piper model_path is not configured."

    if config_configured and config_exists and not config_is_file:
        config_error = "config_path points to a directory; configure a Piper JSON config file."
    elif config_configured and not config_exists:
        config_error = "Configured config_path does not exist yet."

    return {
        "model_configured": model_configured,
        "model_exists": model_exists,
        "model_is_file": model_is_file,
        "model_extension": model_path.suffix.lower() if model_path else "",
        "model_error": model_error,
        "config_configured": config_configured,
        "config_exists": config_exists,
        "config_is_file": config_is_file,
        "config_error": config_error,
        "config_ready": (not config_configured) or (config_exists and config_is_file),
    }


def inspect_piper_license(model_card_path: Path | None) -> dict[str, Any]:
    card_configured = model_card_path is not None
    card_exists = bool(model_card_path and model_card_path.exists())
    card_is_file = bool(model_card_path and model_card_path.is_file())
    license_value = "Unknown"
    license_status = "review_required"
    card_error = ""

    if card_is_file and model_card_path is not None:
        try:
            for raw_line in model_card_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if line.lower().startswith("* license:") or line.lower().startswith("license:"):
                    license_value = line.split(":", 1)[1].strip() or "Unknown"
                    break
        except OSError as error:
            card_error = f"Cannot read Piper MODEL_CARD: {error}"
    elif card_configured and card_exists:
        card_error = "Piper model_card_path points to a directory."
    elif card_configured:
        card_error = "Configured Piper MODEL_CARD does not exist yet."
    else:
        card_error = "Piper MODEL_CARD path is not configured."

    normalized_license = license_value.strip().lower()
    if normalized_license and normalized_license not in {"unknown", "n/a", "none", "tbd", "review required"}:
        license_status = "known"

    return {
        "model_card_configured": card_configured,
        "model_card_exists": card_exists,
        "model_card_is_file": card_is_file,
        "model_card_path": str(model_card_path) if model_card_path else "",
        "model_card_error": card_error,
        "license": license_value,
        "license_status": license_status,
        "production_license_ready": license_status == "known",
    }


def inspect_piper_license_policy(model_card_path: Path | None) -> dict[str, Any]:
    if model_card_path is None:
        return {
            "license_policy_path": "",
            "license_policy_exists": False,
            "license_policy_approved": False,
            "license_policy": {},
        }
    policy_path = model_card_path.with_name("LICENSE_REVIEW.json")
    if not policy_path.exists():
        return {
            "license_policy_path": str(policy_path),
            "license_policy_exists": False,
            "license_policy_approved": False,
            "license_policy": {},
        }
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        policy = {}
    repository_license = str(policy.get("repository_license", "")).strip()
    approved = bool(policy.get("production_use_approved", False)) and bool(repository_license)
    return {
        "license_policy_path": str(policy_path),
        "license_policy_exists": True,
        "license_policy_approved": approved,
        "license_policy": policy,
        "license_policy_repository_license": repository_license,
        "license_policy_dataset_license": str(policy.get("dataset_license", "")).strip(),
    }


def get_comfyui_settings(
    settings: dict[str, dict[str, object]],
    providers_config_path: Path,
    payload: dict[str, Any],
    provider: str,
) -> dict[str, Any]:
    section = settings.get(provider, {})
    base_url = str(os.environ.get("AICOMIC_COMFYUI_BASE_URL", section.get("base_url", "http://127.0.0.1:8188"))).rstrip("/")
    workflow_env = "AICOMIC_COMFYUI_VIDEO_WORKFLOW_PATH" if provider == LOCAL_COMFYUI_VIDEO_PROVIDER else "AICOMIC_COMFYUI_WORKFLOW_PATH"
    workflow_path = resolve_config_path(
        str(os.environ.get(workflow_env, os.environ.get("AICOMIC_COMFYUI_WORKFLOW_PATH", section.get("workflow_path", "")))),
        providers_config_path.parent,
    )
    model_root = resolve_config_path(
        str(os.environ.get("AICOMIC_COMFYUI_MODEL_ROOT", section.get("model_root", "../local_providers/comfyui/models"))),
        providers_config_path.parent,
    )
    model_manifest_path = resolve_config_path(
        str(
            os.environ.get(
                "AICOMIC_COMFYUI_MODEL_MANIFEST_PATH",
                section.get("model_manifest_path", "../local_providers/comfyui/model_requirements.json"),
            )
        ),
        providers_config_path.parent,
    )
    output_path = Path(str(payload.get("output_path", "")))
    seed = str(section.get("seed", "123456789")).strip() or "123456789"
    width = str(section.get("width", "1024")).strip() or "1024"
    height = str(section.get("height", "1536")).strip() or "1536"
    steps = str(section.get("steps", "4")).strip() or "4"
    cfg = str(section.get("cfg", "1")).strip() or "1"
    video_length = str(section.get("video_length", "9")).strip() or "9"
    fps = str(section.get("fps", "8")).strip() or "8"
    output_prefix = str(section.get("output_prefix", "aicomic")).strip() or "aicomic"
    return {
        "base_url": base_url,
        "provider": provider,
        "timeout_seconds": parse_int(
            os.environ.get("AICOMIC_COMFYUI_TIMEOUT_SECONDS", section.get("timeout_seconds", 30)),
            30,
        ),
        "poll_timeout_seconds": parse_int(
            os.environ.get("AICOMIC_COMFYUI_POLL_TIMEOUT_SECONDS", section.get("poll_timeout_seconds", 180)),
            180,
        ),
        "poll_interval_seconds": parse_float(
            os.environ.get("AICOMIC_COMFYUI_POLL_INTERVAL_SECONDS", section.get("poll_interval_seconds", 2.0)),
            2.0,
        ),
        "workflow_path": workflow_path,
        "model_root": model_root,
        "model_manifest_path": model_manifest_path,
        "seed": seed,
        "width": width,
        "height": height,
        "output_prefix": output_prefix,
        "replacements": {
            "{{prompt}}": str(payload.get("prompt", "")),
            "{{negative_prompt}}": str(section.get("negative_prompt", "")),
            "{{seed}}": parse_int(seed, 123456789),
            "{{width}}": parse_int(width, 1024),
            "{{height}}": parse_int(height, 1536),
            "{{steps}}": parse_int(steps, 4),
            "{{cfg}}": parse_float(cfg, 1.0),
            "{{video_length}}": parse_int(video_length, 9),
            "{{fps}}": parse_float(fps, 8.0),
            "{{output_prefix}}": f"{output_prefix}_{payload.get('episode_code', '')}_{payload.get('shot_id', '')}",
            "{{episode_code}}": str(payload.get("episode_code", "")),
            "{{shot_id}}": str(payload.get("shot_id", "")),
            "{{job_id}}": str(payload.get("job_id", "")),
            "{{output_path}}": str(output_path),
        },
    }


def load_comfyui_workflow(local_settings: dict[str, Any]) -> dict[str, Any]:
    workflow_path = local_settings["workflow_path"]
    workflow_status = inspect_comfyui_workflow_path(workflow_path)
    if not workflow_status["workflow_configured"]:
        raise RuntimeError("ComfyUI workflow_path is not configured")
    if not workflow_status["workflow_exists"]:
        raise RuntimeError(f"ComfyUI workflow_path does not exist: {workflow_path}")
    if not workflow_status["workflow_is_file"]:
        raise RuntimeError(f"ComfyUI workflow_path must be a JSON file, not a directory: {workflow_path}")
    if not workflow_status["workflow_valid_json"] or not workflow_status["workflow_api_format"]:
        raise RuntimeError(f"ComfyUI workflow_path is not a valid workflow JSON: {workflow_status['workflow_error']}")
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    return substitute_placeholders(deepcopy(workflow), local_settings["replacements"])


def build_comfyui_preflight(local_settings: dict[str, Any]) -> dict[str, Any]:
    workflow_path = local_settings["workflow_path"]
    provider = str(local_settings.get("provider", LOCAL_COMFYUI_PROVIDER))
    workflow_env = "AICOMIC_COMFYUI_VIDEO_WORKFLOW_PATH" if provider == LOCAL_COMFYUI_VIDEO_PROVIDER else "AICOMIC_COMFYUI_WORKFLOW_PATH"
    workflow_status = inspect_comfyui_workflow_path(workflow_path)
    model_usage = inspect_comfyui_workflow_model_usage(workflow_path)
    model_status = inspect_comfyui_model_requirements(
        provider,
        local_settings.get("model_root"),
        local_settings.get("model_manifest_path"),
    )
    server_status = probe_comfyui_server(local_settings["base_url"])
    model_requirements_enforced = bool(model_usage["workflow_requires_model_files"])
    effective_required_models_ready = (
        bool(model_status["required_models_ready"])
        if model_requirements_enforced
        else True
    )
    model_notes = (
        "place required model weights under model_root before live execution."
        if model_requirements_enforced
        else "this smoke workflow does not load model weights; run full mode before validating image quality."
    )
    return {
        "ready": bool(workflow_status["workflow_api_format"])
        and bool(effective_required_models_ready)
        and bool(server_status["comfyui_server_available"]),
        "base_url": local_settings["base_url"],
        **server_status,
        **workflow_status,
        **model_status,
        **model_usage,
        "model_requirements_enforced": model_requirements_enforced,
        "configured_required_models_ready": bool(model_status["required_models_ready"]),
        "required_models_ready": effective_required_models_ready,
        "workflow_path": str(workflow_path) if workflow_path else "",
        "notes": (
            f"Place a ComfyUI API workflow JSON at {workflow_path} or override with {workflow_env}; "
            f"{model_notes}"
        ),
    }


def build_comfyui_request_preview(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", LOCAL_COMFYUI_PROVIDER))
    local_settings = get_comfyui_settings(settings, providers_config_path, payload, provider)
    preflight = build_comfyui_preflight(local_settings)
    body: dict[str, Any] = {
        "prompt": {},
        "client_id": "aicomic-dry-run",
    }
    if preflight["workflow_api_format"]:
        body["prompt"] = load_comfyui_workflow(local_settings)
    return {
        "method": "POST",
        "url": f"{local_settings['base_url']}/prompt",
        "headers": {"Content-Type": "application/json"},
        "body": body,
        "preflight": preflight,
    }


def get_piper_settings(settings: dict[str, dict[str, object]], providers_config_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    section = settings.get(LOCAL_PIPER_PROVIDER, {})
    project_root = providers_config_path.parent.parent.resolve()
    command = str(os.environ.get("AICOMIC_PIPER_COMMAND", section.get("command", "piper"))).strip() or "piper"
    command = command.replace("{{python_executable}}", sys.executable)
    command = command.replace("{{project_root}}", str(project_root))
    command = command.strip().strip("\"'")
    base_url = optional_string(os.environ.get("AICOMIC_PIPER_BASE_URL", section.get("base_url", ""))).rstrip("/")
    model_path = resolve_config_path(
        str(os.environ.get("AICOMIC_PIPER_MODEL_PATH", section.get("model_path", ""))),
        providers_config_path.parent,
    )
    config_path = resolve_config_path(
        str(os.environ.get("AICOMIC_PIPER_CONFIG_PATH", section.get("config_path", ""))),
        providers_config_path.parent,
    )
    model_card_path = resolve_config_path(
        str(os.environ.get("AICOMIC_PIPER_MODEL_CARD_PATH", section.get("model_card_path", "../local_providers/piper/models/MODEL_CARD"))),
        providers_config_path.parent,
    )
    return {
        "base_url": base_url,
        "command": command,
        "model_path": model_path,
        "config_path": config_path,
        "model_card_path": model_card_path,
        "speaker_id": optional_string(section.get("speaker_id", "")),
        "timeout_seconds": parse_int(section.get("timeout_seconds", 120), 120),
        "extra_args": optional_string(section.get("extra_args", "")),
        "input_text": str(payload.get("prompt", "")),
        "output_path": Path(str(payload.get("output_path", ""))),
    }


def build_piper_preflight(local_settings: dict[str, Any]) -> dict[str, Any]:
    model_path = local_settings["model_path"]
    config_path = local_settings["config_path"]
    base_url = str(local_settings.get("base_url", "")).strip()
    service_status = (
        probe_piper_service(base_url, timeout_seconds=1.0)
        if base_url
        else {
            "piper_service_configured": False,
            "piper_service_available": False,
            "piper_service_error": "",
            "piper_service_mode": "local_process",
            "piper_service_payload_keys": [],
        }
    )
    command_is_available = command_available(str(local_settings["command"]))
    path_status = inspect_piper_paths(model_path, config_path)
    license_status = inspect_piper_license(local_settings.get("model_card_path"))
    license_policy = inspect_piper_license_policy(local_settings.get("model_card_path"))
    if license_status["license_status"] != "known" and bool(license_policy.get("license_policy_approved", False)):
        license_status["license_status"] = "approved_by_policy"
        license_status["production_license_ready"] = True
        license_status["license"] = str(license_policy.get("license_policy_repository_license", "approved"))
    return {
        "ready": (
            (bool(base_url) and bool(service_status["piper_service_available"]))
            or (not base_url and command_is_available)
        )
        and bool(path_status["model_configured"])
        and bool(path_status["model_exists"])
        and bool(path_status["model_is_file"])
        and bool(path_status["config_ready"]),
        "execution_transport": "http_service" if base_url else "local_process",
        "command_available": command_is_available,
        **service_status,
        **path_status,
        **license_status,
        **license_policy,
        "base_url": base_url,
        "model_path": str(model_path) if model_path else "",
        "config_path": str(config_path) if config_path else "",
        "notes": (
            "Piper sidecar HTTP service or local Piper command, plus local .onnx model and optional config JSON, "
            "must be available before live execution."
        ),
    }


def build_piper_command(local_settings: dict[str, Any]) -> list[str]:
    model_path = local_settings["model_path"]
    if model_path is None:
        raise RuntimeError("Piper model_path is not configured")
    args = [
        *command_parts(str(local_settings["command"])),
        "--model",
        str(model_path),
        "--output_file",
        str(local_settings["output_path"]),
    ]
    config_path = local_settings["config_path"]
    if config_path is not None:
        args.extend(["--config", str(config_path)])
    speaker_id = str(local_settings["speaker_id"]).strip()
    if speaker_id:
        args.extend(["--speaker", speaker_id])
    extra_args = str(local_settings["extra_args"]).strip()
    if extra_args:
        args.extend(shlex.split(extra_args))
    return args


def build_piper_request_preview(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    local_settings = get_piper_settings(settings, providers_config_path, payload)
    preflight = build_piper_preflight(local_settings)
    if str(local_settings.get("base_url", "")).strip():
        return {
            "method": "POST",
            "url": f"{str(local_settings['base_url']).rstrip('/')}/synthesize",
            "headers": {"Content-Type": "application/json"},
            "body": {
                "text": local_settings["input_text"],
                "model_path": str(local_settings["model_path"]) if local_settings["model_path"] else "",
                "config_path": str(local_settings["config_path"]) if local_settings["config_path"] else "",
                "speaker_id": str(local_settings["speaker_id"]).strip(),
                "extra_args": str(local_settings["extra_args"]).strip(),
                "timeout_seconds": int(local_settings["timeout_seconds"]),
            },
            "preflight": preflight,
        }
    command_preview: list[str] = []
    if local_settings["model_path"] is not None:
        command_preview = build_piper_command(local_settings)
    return {
        "method": "LOCAL_PROCESS",
        "url": "local:piper",
        "headers": {},
        "body": {
            "input_text": local_settings["input_text"],
            "output_path": str(local_settings["output_path"]),
            "command": command_preview,
        },
        "preflight": preflight,
    }


def build_local_request_preview(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", ""))
    if provider in LOCAL_COMFYUI_PROVIDERS:
        return build_comfyui_request_preview(request_item, providers_config_path)
    if provider == LOCAL_PIPER_PROVIDER:
        return build_piper_request_preview(request_item, providers_config_path)
    return {
        "method": "",
        "url": "",
        "headers": {},
        "body": {},
        "preflight": {"ready": False, "notes": f"Unsupported local provider: {provider}"},
    }


def post_json(url: str, body: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with NO_PROXY_OPENER.open(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local provider HTTPError {error.code}: {error_body}") from error
    except URLError as error:
        raise RuntimeError(f"Local provider URLError: {error.reason}") from error


def get_json(url: str, timeout_seconds: int) -> dict[str, Any]:
    try:
        with NO_PROXY_OPENER.open(url, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local provider HTTPError {error.code}: {error_body}") from error
    except URLError as error:
        raise RuntimeError(f"Local provider URLError: {error.reason}") from error


def get_bytes(url: str, timeout_seconds: int) -> tuple[bytes, str]:
    try:
        with NO_PROXY_OPENER.open(url, timeout=timeout_seconds) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local provider HTTPError {error.code}: {error_body}") from error
    except URLError as error:
        raise RuntimeError(f"Local provider URLError: {error.reason}") from error


def post_json_for_bytes(url: str, body: dict[str, Any], timeout_seconds: int) -> tuple[bytes, str]:
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with NO_PROXY_OPENER.open(request, timeout=timeout_seconds) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local provider HTTPError {error.code}: {error_body}") from error
    except URLError as error:
        raise RuntimeError(f"Local provider URLError: {error.reason}") from error


def extract_first_comfyui_artifact(history_payload: dict[str, Any], prompt_id: str) -> dict[str, str] | None:
    prompt_history = history_payload.get(prompt_id, {})
    outputs = prompt_history.get("outputs", {})
    if not isinstance(outputs, dict):
        return None
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        for collection_name, artifact_kind in (("images", "image"), ("videos", "video"), ("gifs", "video")):
            artifacts = output.get(collection_name, [])
            if not isinstance(artifacts, list) or not artifacts:
                continue
            artifact = artifacts[0]
            if isinstance(artifact, dict) and artifact.get("filename"):
                return {
                    "filename": str(artifact.get("filename", "")),
                    "subfolder": str(artifact.get("subfolder", "")),
                    "type": str(artifact.get("type", "output")),
                    "artifact_kind": artifact_kind,
                }
    return None


def extract_comfyui_execution_error(history_payload: dict[str, Any], prompt_id: str) -> str:
    prompt_history = history_payload.get(prompt_id, {})
    status = prompt_history.get("status", {})
    messages = status.get("messages", []) if isinstance(status, dict) else []
    for message in reversed(messages):
        if not isinstance(message, list) or len(message) != 2:
            continue
        if message[0] != "execution_error" or not isinstance(message[1], dict):
            continue
        details = message[1]
        node_type = str(details.get("node_type", "")).strip()
        node_id = str(details.get("node_id", "")).strip()
        exception_message = str(details.get("exception_message", "")).strip()
        location = f"{node_type}#{node_id}" if node_type and node_id else node_type or node_id or "unknown_node"
        if exception_message:
            return f"ComfyUI execution_error at {location}: {exception_message}"
        return f"ComfyUI execution_error at {location}"
    if isinstance(status, dict) and str(status.get("status_str", "")).strip().lower() == "error":
        return f"ComfyUI prompt failed before producing an output artifact: {prompt_id}"
    return ""


def perform_comfyui_request(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", LOCAL_COMFYUI_PROVIDER))
    local_settings = get_comfyui_settings(settings, providers_config_path, payload, provider)
    workflow = load_comfyui_workflow(local_settings)
    client_id = f"aicomic-{uuid.uuid4()}"
    submit_response = post_json(
        f"{local_settings['base_url']}/prompt",
        {"prompt": workflow, "client_id": client_id},
        int(local_settings["timeout_seconds"]),
    )
    prompt_id = str(submit_response.get("prompt_id", ""))
    if not prompt_id:
        raise RuntimeError("ComfyUI response did not include prompt_id")

    deadline = time.time() + int(local_settings["poll_timeout_seconds"])
    artifact_meta: dict[str, str] | None = None
    while time.time() < deadline:
        history = get_json(f"{local_settings['base_url']}/history/{prompt_id}", int(local_settings["timeout_seconds"]))
        artifact_meta = extract_first_comfyui_artifact(history, prompt_id)
        if artifact_meta is not None:
            break
        execution_error = extract_comfyui_execution_error(history, prompt_id)
        if execution_error:
            raise RuntimeError(execution_error)
        time.sleep(float(local_settings["poll_interval_seconds"]))
    if artifact_meta is None:
        raise RuntimeError(f"ComfyUI prompt timed out before output artifact: {prompt_id}")

    view_meta = {key: value for key, value in artifact_meta.items() if key != "artifact_kind"}
    query = urlencode(view_meta)
    artifact_bytes, content_type = get_bytes(f"{local_settings['base_url']}/view?{query}", int(local_settings["timeout_seconds"]))
    output_path = Path(str(payload["output_path"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(artifact_bytes)
    return {
        "provider": provider,
        "output_path": str(output_path),
        "content_type": content_type,
        "response_meta": {
            "prompt_id": prompt_id,
            "source_artifact": artifact_meta,
            "bytes": len(artifact_bytes),
        },
    }


def perform_piper_request(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    local_settings = get_piper_settings(settings, providers_config_path, payload)
    preflight = build_piper_preflight(local_settings)
    if not preflight["ready"]:
        raise RuntimeError(f"Piper is not ready: {preflight}")
    output_path = local_settings["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_url = str(local_settings.get("base_url", "")).strip()
    if base_url:
        audio_bytes, content_type = post_json_for_bytes(
            f"{base_url.rstrip('/')}/synthesize",
            {
                "text": str(local_settings["input_text"]),
                "model_path": str(local_settings["model_path"]) if local_settings["model_path"] else "",
                "config_path": str(local_settings["config_path"]) if local_settings["config_path"] else "",
                "speaker_id": str(local_settings["speaker_id"]).strip(),
                "extra_args": str(local_settings["extra_args"]).strip(),
                "timeout_seconds": int(local_settings["timeout_seconds"]),
            },
            int(local_settings["timeout_seconds"]),
        )
        output_path.write_bytes(audio_bytes)
        if not output_path.exists():
            raise RuntimeError(f"Piper HTTP sidecar did not create output file: {output_path}")
        return {
            "provider": LOCAL_PIPER_PROVIDER,
            "output_path": str(output_path),
            "content_type": content_type or "audio/wav",
            "response_meta": {
                "bytes": output_path.stat().st_size,
                "execution_transport": "http_service",
                "base_url": base_url,
            },
        }
    result = subprocess.run(
        build_piper_command(local_settings),
        input=str(local_settings["input_text"]),
        capture_output=True,
        text=True,
        timeout=int(local_settings["timeout_seconds"]),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Piper failed with code {result.returncode}: {(result.stderr or result.stdout).strip()}")
    if not output_path.exists():
        raise RuntimeError(f"Piper did not create output file: {output_path}")
    return {
        "provider": LOCAL_PIPER_PROVIDER,
        "output_path": str(output_path),
        "content_type": "audio/wav",
        "response_meta": {
            "bytes": output_path.stat().st_size,
            "stderr_tail": (result.stderr or "").strip()[-1000:],
            "execution_transport": "local_process",
        },
    }


def perform_local_request(request_item: dict[str, Any], providers_config_path: Path) -> dict[str, Any]:
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", ""))
    if provider in LOCAL_COMFYUI_PROVIDERS:
        return perform_comfyui_request(request_item, providers_config_path)
    if provider == LOCAL_PIPER_PROVIDER:
        return perform_piper_request(request_item, providers_config_path)
    raise RuntimeError(f"Unsupported local provider: {provider}")
