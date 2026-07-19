"""Local provider adapter — ComfyUI & Piper request building and execution."""

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
from urllib.request import ProxyHandler, build_opener, Request
from urllib.parse import urlencode
import uuid

from aicomic.providers.provider_planner import load_provider_settings
from aicomic.security.production_rehearsal import FIXTURE_MODEL_MARKER

LOCAL_COMFYUI_PROVIDER = "local_comfyui_image"
LOCAL_COMFYUI_VIDEO_PROVIDER = "local_comfyui_video"
LOCAL_COMFYUI_VIDEO_WAN22_PROVIDER = "local_comfyui_video_wan22"
LOCAL_PIPER_PROVIDER = "local_piper_tts"
LOCAL_COMFYUI_PROVIDERS = {LOCAL_COMFYUI_PROVIDER, LOCAL_COMFYUI_VIDEO_PROVIDER, LOCAL_COMFYUI_VIDEO_WAN22_PROVIDER}
LOCAL_EXECUTION_PROVIDERS = LOCAL_COMFYUI_PROVIDERS | {LOCAL_PIPER_PROVIDER}
_NO_PROXY = build_opener(ProxyHandler({}))
_COMFYUI_LOADERS = {"CLIPLoader", "DualCLIPLoader", "TripleCLIPLoader", "VAELoader", "UNETLoader", "CheckpointLoader", "CheckpointLoaderSimple", "LoraLoader", "ControlNetLoader"}


def _strip_quotes(value: str) -> str:
    return value.strip().strip("\"'")

def resolve_config_path(raw_path: str, base_dir: Path) -> Path | None:
    value = _strip_quotes(raw_path)
    if value.lower() in {"null", "none", "~"}:
        value = ""
    if not value:
        return None
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def parse_int(raw: object, default: int) -> int:
    s = str(raw).strip()
    return int(s) if s.isdigit() else default


def parse_float(raw: object, default: float) -> float:
    try:
        return float(str(raw).strip())
    except ValueError:
        return default


def optional_string(raw: object) -> str:
    return _strip_quotes(str(raw)) if str(raw).strip().lower() not in {"null", "none", "~", ""} else ""


def command_parts(cmd: str) -> list[str]:
    parts = shlex.split(cmd)
    return parts if parts else ["piper"]


def command_executable(cmd: str) -> str:
    parts = command_parts(cmd)
    exe = parts[0]
    if Path(exe).name == "env":
        for p in parts[1:]:
            if "=" in p and not p.startswith("-"):
                continue
            if p.startswith("-"):
                continue
            exe = p
            break
    return exe


def command_available(cmd: str) -> bool:
    exe = command_executable(cmd)
    return Path(exe).exists() if Path(exe).is_absolute() else shutil.which(exe) is not None


def substitute_placeholders(value: object, replacements: dict[str, object]) -> object:
    if isinstance(value, str):
        updated = replacements.get(value, value)
        for k, v in replacements.items():
            if isinstance(updated, str):
                updated = updated.replace(k, str(v))
        return updated
    if isinstance(value, list):
        return [substitute_placeholders(i, replacements) for i in value]
    if isinstance(value, dict):
        return {k: substitute_placeholders(v, replacements) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Path / file inspection helpers
# ---------------------------------------------------------------------------

def _path_check(path: Path | None, label: str) -> dict[str, Any]:
    """Return {<label>_configured, _exists, _is_file}."""
    return {
        f"{label}_configured": path is not None,
        f"{label}_exists": bool(path and path.exists()),
        f"{label}_is_file": bool(path and path.is_file()),
    }


def _inspect_workflow_json(workflow_path: Path | None) -> dict[str, Any]:
    """Validate a workflow path is API-prompt JSON and return inspection."""
    result = dict(workflow_configured=False, workflow_exists=False, workflow_is_file=False,
                  workflow_valid_json=False, workflow_api_format=False, workflow_node_count=0, workflow_error="")
    result.update(_path_check(workflow_path, "workflow"))
    if workflow_path and result["workflow_exists"] and not result["workflow_is_file"]:
        result["workflow_error"] = "workflow_path points to a directory; configure a JSON file inside the workflow folder."
        return result
    if result["workflow_configured"] and not result["workflow_exists"]:
        result["workflow_error"] = "Configured workflow_path does not exist yet."
        return result
    if not result["workflow_is_file"] or workflow_path is None:
        if not result["workflow_configured"]:
            result["workflow_error"] = ""
        return result
    try:
        wf = json.loads(workflow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        result["workflow_error"] = f"Invalid JSON at line {e.lineno}, col {e.colno}: {e.msg}"
        return result
    except OSError as e:
        result["workflow_error"] = f"Cannot read workflow: {e}"
        return result
    if not isinstance(wf, dict) or not wf:
        result["workflow_error"] = "Workflow must be a non-empty object in ComfyUI API format."
        return result
    result["workflow_valid_json"] = True
    nodes = {k: v for k, v in wf.items() if isinstance(v, dict) and k != "_meta"}
    result["workflow_node_count"] = len(nodes)
    result["workflow_api_format"] = bool(nodes) and all(isinstance(n.get("class_type"), str) and bool(n["class_type"]) and isinstance(n.get("inputs"), dict) for n in nodes.values())
    if not result["workflow_api_format"]:
        result["workflow_error"] = "Workflow must have class_type and inputs per node."
    return result


def _inspect_model_loader_nodes(workflow_path: Path | None) -> dict[str, Any]:
    """Count model-loader nodes; if absent, model requirements are not enforced."""
    if workflow_path is None or not workflow_path.is_file():
        return {"workflow_requires_model_files": True, "workflow_model_loader_count": 0, "workflow_model_loader_nodes": [],
                "workflow_model_usage_note": "Workflow unavailable; model requirements enforced."}
    try:
        wf = json.loads(workflow_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"workflow_requires_model_files": True, "workflow_model_loader_count": 0, "workflow_model_loader_nodes": [],
                "workflow_model_usage_note": "Workflow not readable; model requirements enforced."}
    if not isinstance(wf, dict):
        return {"workflow_requires_model_files": True, "workflow_model_loader_count": 0, "workflow_model_loader_nodes": [],
                "workflow_model_usage_note": "Workflow not API JSON; model requirements enforced."}
    loaders = [{"node_id": str(nid), "class_type": str(n.get("class_type", "")).strip()}
               for nid, n in wf.items() if isinstance(n, dict)
               and (n.get("class_type") in _COMFYUI_LOADERS or "loader" in str(n.get("class_type", "")).lower())]
    return {"workflow_requires_model_files": bool(loaders), "workflow_model_loader_count": len(loaders),
            "workflow_model_loader_nodes": loaders,
            "workflow_model_usage_note": "Workflow has model loader nodes." if loaders else "No model loader nodes (smoke tier OK)."}


def inspect_comfyui_model_requirements(provider: str, model_root: Path | None, model_manifest_path: Path | None) -> dict[str, Any]:
    """Inspect model manifest and check which required models exist under model_root."""
    mp_status = _path_check(model_manifest_path, "model_manifest")
    mr_status = _path_check(model_root, "model_root")
    result = {k: v for d in (mp_status, mr_status) for k, v in d.items()}
    result.update({"model_manifest_path": str(model_manifest_path) if model_manifest_path else "",
                   "model_root": str(model_root) if model_root else "", "model_manifest_error": "", "model_root_error": "",
                   "required_model_count": 0, "present_required_model_count": 0, "missing_required_model_count": 0,
                   "fixture_required_model_count": 0, "present_required_models": [], "missing_required_models": [],
                   "fixture_required_models": [], "required_models_ready": False})

    required_models: list[dict] = []
    if not mp_status["model_manifest_configured"]:
        result["model_manifest_error"] = "Model manifest not configured."
    elif not mp_status["model_manifest_exists"]:
        result["model_manifest_error"] = "Model manifest does not exist."
    elif not mp_status["model_manifest_is_file"]:
        result["model_manifest_error"] = "Model manifest is a directory."
    elif model_manifest_path:
        try:
            mf = json.loads(model_manifest_path.read_text(encoding="utf-8"))
            reqs = (mf or {}).get("providers", {}).get(provider, [])
            if isinstance(reqs, list):
                required_models = [i for i in reqs if isinstance(i, dict) and str(i.get("filename", "")).strip()]
            if not required_models:
                result["model_manifest_error"] = f"No model requirements for provider: {provider}"
        except (OSError, json.JSONDecodeError) as e:
            result["model_manifest_error"] = f"Cannot read manifest: {e}"

    if not mr_status["model_root_configured"]:
        result["model_root_error"] = "model_root not configured."
    elif not mr_status["model_root_exists"]:
        result["model_root_error"] = "model_root does not exist."
    elif not mr_status["model_root_is_file"]:
        result["model_root_error"] = "model_root must be a directory."

    if model_root and mr_status["model_root_is_file"]:
        for item in required_models:
            fn = str(item.get("filename", "")).strip()
            sd = str(item.get("subdir", "")).strip().strip("/")
            rel = Path(sd) / fn if sd else Path(fn)
            mp = model_root / rel
            entry = {"filename": fn, "subdir": sd, "relative_path": str(rel), "path": str(mp), "source": str(item.get("source", ""))}
            if mp.is_file():
                result["present_required_models"].append(entry)
                if _is_fixture(mp):
                    result["fixture_required_models"].append(entry)
            else:
                result["missing_required_models"].append(entry)
    elif required_models:
        for item in required_models:
            fn = str(item.get("filename", "")).strip()
            sd = str(item.get("subdir", "")).strip().strip("/")
            rel = Path(sd) / fn if sd else Path(fn)
            result["missing_required_models"].append({"filename": fn, "subdir": sd, "relative_path": str(rel), "path": str((model_root / rel) if model_root else rel), "source": str(item.get("source", ""))})

    result["required_model_count"] = len(required_models)
    result["present_required_model_count"] = len(result["present_required_models"])
    result["missing_required_model_count"] = len(result["missing_required_models"])
    result["fixture_required_model_count"] = len(result["fixture_required_models"])
    result["required_models_ready"] = (mp_status["model_manifest_configured"] and mp_status["model_manifest_exists"]
                                       and mp_status["model_manifest_is_file"] and mr_status["model_root_configured"]
                                       and mr_status["model_root_exists"] and result["model_root_is_file"]
                                       and len(required_models) > 0 and not result["missing_required_models"])
    return result


def _is_fixture(model_path: Path) -> bool:
    try:
        return FIXTURE_MODEL_MARKER.encode("utf-8") in model_path.open("rb").read(len(FIXTURE_MODEL_MARKER) + 8)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http(method: str, url: str, timeout: int, body: dict | None = None) -> dict:
    """Low-level HTTP request returning parsed JSON dict."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body else None
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    try:
        with _NO_PROXY.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')}") from e
    except URLError as e:
        raise RuntimeError(f"URLError: {e.reason}") from e


def _http_bytes(url: str, timeout: int) -> tuple[bytes, str]:
    """GET request returning (raw bytes, content-type)."""
    try:
        with _NO_PROXY.open(url, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except HTTPError as e:
        raise RuntimeError(f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')}") from e
    except URLError as e:
        raise RuntimeError(f"URLError: {e.reason}") from e


def get_json(url: str, timeout: int) -> dict:
    return _http("GET", url, timeout)


def post_json(url: str, body: dict, timeout: int) -> dict:
    return _http("POST", url, timeout, body)


def post_json_for_bytes(url: str, body: dict, timeout: int) -> tuple[bytes, str]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _NO_PROXY.open(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except HTTPError as e:
        raise RuntimeError(f"HTTPError {e.code}: {e.read().decode('utf-8', errors='replace')}") from e
    except URLError as e:
        raise RuntimeError(f"URLError: {e.reason}") from e


def get_bytes(url: str, timeout: int) -> tuple[bytes, str]:
    return _http_bytes(url, timeout)


# ---------------------------------------------------------------------------
# ComfyUI settings, preflight, request building
# ---------------------------------------------------------------------------

def get_comfyui_settings(settings: dict, providers_config_path: Path, payload: dict, provider: str) -> dict:
    section = settings.get(provider, {})
    is_video = provider == LOCAL_COMFYUI_VIDEO_PROVIDER
    wf_key = "AICOMIC_COMFYUI_VIDEO_WORKFLOW_PATH" if is_video else "AICOMIC_COMFYUI_WORKFLOW_PATH"
    wf_env = os.environ.get(wf_key, os.environ.get("AICOMIC_COMFYUI_WORKFLOW_PATH", section.get("workflow_path", "")))
    return {
        "base_url": str(os.environ.get("AICOMIC_COMFYUI_BASE_URL", section.get("base_url", "http://127.0.0.1:8188"))).rstrip("/"),
        "provider": provider,
        "timeout_seconds": parse_int(os.environ.get("AICOMIC_COMFYUI_TIMEOUT_SECONDS", section.get("timeout_seconds", 30)), 30),
        "poll_timeout_seconds": parse_int(os.environ.get("AICOMIC_COMFYUI_POLL_TIMEOUT_SECONDS", section.get("poll_timeout_seconds", 180)), 180),
        "poll_interval_seconds": parse_float(os.environ.get("AICOMIC_COMFYUI_POLL_INTERVAL_SECONDS", section.get("poll_interval_seconds", 2.0)), 2.0),
        "workflow_path": resolve_config_path(str(wf_env), providers_config_path.parent),
        "model_root": resolve_config_path(str(os.environ.get("AICOMIC_COMFYUI_MODEL_ROOT", section.get("model_root", "../local_providers/comfyui/models"))), providers_config_path.parent),
        "model_manifest_path": resolve_config_path(str(os.environ.get("AICOMIC_COMFYUI_MODEL_MANIFEST_PATH", section.get("model_manifest_path", "../local_providers/comfyui/model_requirements.json"))), providers_config_path.parent),
        "seed": str(section.get("seed", "123456789")).strip() or "123456789",
        "width": str(section.get("width", "1024")).strip() or "1024",
        "height": str(section.get("height", "1536")).strip() or "1536",
        "output_prefix": str(section.get("output_prefix", "aicomic")).strip() or "aicomic",
        "replacements": {
            "{{prompt}}": str(payload.get("prompt", "")),
            "{{negative_prompt}}": str(section.get("negative_prompt", "")),
            "{{seed}}": parse_int(str(section.get("seed", "123456789")), 123456789),
            "{{width}}": parse_int(str(section.get("width", "1024")), 1024),
            "{{height}}": parse_int(str(section.get("height", "1536")), 1536),
            "{{steps}}": parse_int(str(section.get("steps", "4")), 4),
            "{{cfg}}": parse_float(str(section.get("cfg", "1")), 1.0),
            "{{video_length}}": parse_int(str(section.get("video_length", "9")), 9),
            "{{fps}}": parse_float(str(section.get("fps", "8")), 8.0),
            "{{output_prefix}}": f"{section.get('output_prefix', 'aicomic')}_{payload.get('episode_code', '')}_{payload.get('shot_id', '')}",
            "{{episode_code}}": str(payload.get("episode_code", "")),
            "{{shot_id}}": str(payload.get("shot_id", "")),
            "{{job_id}}": str(payload.get("job_id", "")),
            "{{output_path}}": str(payload.get("output_path", "")),
        },
    }


def load_comfyui_workflow(local_settings: dict) -> dict:
    wf = local_settings["workflow_path"]
    st = _inspect_workflow_json(wf)
    if not st["workflow_api_format"]:
        raise RuntimeError(f"ComfyUI workflow not usable: {st['workflow_error']}")
    return substitute_placeholders(deepcopy(json.loads(wf.read_text(encoding="utf-8"))), local_settings["replacements"])


def probe_comfyui_server(base_url: str, timeout: float = 1.0) -> dict:
    try:
        p = get_json(f"{base_url}/system_stats", int(timeout))
        return {"comfyui_server_available": True, "comfyui_server_error": "", "comfyui_server_mode": "mock" if p.get("aicomic_mock_comfyui") else "live", "comfyui_server_payload_keys": sorted(str(k) for k in p.keys())}
    except Exception as e:
        return {"comfyui_server_available": False, "comfyui_server_error": str(e), "comfyui_server_mode": "unavailable", "comfyui_server_payload_keys": []}


def build_comfyui_preflight(local_settings: dict) -> dict:
    wf_path = local_settings["workflow_path"]
    wf_st = _inspect_workflow_json(wf_path)
    ml_st = _inspect_model_loader_nodes(wf_path)
    md_st = inspect_comfyui_model_requirements(str(local_settings.get("provider", LOCAL_COMFYUI_PROVIDER)), local_settings.get("model_root"), local_settings.get("model_manifest_path"))
    sv_st = probe_comfyui_server(local_settings["base_url"])
    enforce = bool(ml_st["workflow_requires_model_files"])
    ready = bool(wf_st["workflow_api_format"]) and (bool(md_st["required_models_ready"]) if enforce else True) and bool(sv_st["comfyui_server_available"])
    wf_env = "AICOMIC_COMFYUI_VIDEO_WORKFLOW_PATH" if str(local_settings.get("provider")) == LOCAL_COMFYUI_VIDEO_PROVIDER else "AICOMIC_COMFYUI_WORKFLOW_PATH"
    return {"ready": ready, "base_url": local_settings["base_url"], **sv_st, **wf_st, **md_st, **ml_st,
            "model_requirements_enforced": enforce,
            "configured_required_models_ready": bool(md_st["required_models_ready"]),
            "required_models_ready": bool(md_st["required_models_ready"]) if not enforce else True,
            "workflow_path": str(wf_path) if wf_path else "",
            "notes": f"Place API workflow at {wf_path} or use {wf_env}; {'place model weights' if enforce else 'smoke OK'}"}


def build_comfyui_request_preview(request_item: dict, providers_config_path: Path) -> dict:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", LOCAL_COMFYUI_PROVIDER))
    ls = get_comfyui_settings(settings, providers_config_path, payload, provider)
    pf = build_comfyui_preflight(ls)
    body = {"prompt": load_comfyui_workflow(ls) if pf["workflow_api_format"] else {}, "client_id": "aicomic-dry-run"}
    return {"method": "POST", "url": f"{ls['base_url']}/prompt", "headers": {"Content-Type": "application/json"}, "body": body, "preflight": pf}


# ---------------------------------------------------------------------------
# Piper settings, preflight, request building
# ---------------------------------------------------------------------------

def get_piper_settings(settings: dict, providers_config_path: Path, payload: dict) -> dict:
    sec = settings.get(LOCAL_PIPER_PROVIDER, {})
    cmd = os.environ.get("AICOMIC_PIPER_COMMAND", sec.get("command", "piper")).strip() or "piper"
    cmd = cmd.replace("{{python_executable}}", sys.executable).replace("{{project_root}}", str(providers_config_path.parent.parent.resolve()))
    return {
        "base_url": optional_string(os.environ.get("AICOMIC_PIPER_BASE_URL", sec.get("base_url", ""))).rstrip("/"),
        "command": cmd.strip().strip("\"'"),
        "model_path": resolve_config_path(str(os.environ.get("AICOMIC_PIPER_MODEL_PATH", sec.get("model_path", ""))), providers_config_path.parent),
        "config_path": resolve_config_path(str(os.environ.get("AICOMIC_PIPER_CONFIG_PATH", sec.get("config_path", ""))), providers_config_path.parent),
        "model_card_path": resolve_config_path(str(os.environ.get("AICOMIC_PIPER_MODEL_CARD_PATH", sec.get("model_card_path", "../local_providers/piper/models/MODEL_CARD"))), providers_config_path.parent),
        "speaker_id": optional_string(sec.get("speaker_id", "")),
        "timeout_seconds": parse_int(sec.get("timeout_seconds", 120), 120),
        "extra_args": optional_string(sec.get("extra_args", "")),
        "input_text": str(payload.get("prompt", "")),
        "output_path": Path(str(payload.get("output_path", ""))),
    }


def inspect_piper_paths(model_path: Path | None, config_path: Path | None) -> dict[str, Any]:
    mp, cp = _path_check(model_path, "model"), _path_check(config_path, "config")
    result = {**mp, **cp, "model_extension": model_path.suffix.lower() if model_path else "",
              "model_error": "", "config_error": "", "config_ready": (not cp["config_configured"] or (cp["config_exists"] and cp["config_is_file"]))}
    if mp["model_exists"] and not mp["model_is_file"]:
        result["model_error"] = "model_path is a directory; use a .onnx file."
    elif mp["model_configured"] and not mp["model_exists"]:
        result["model_error"] = "model_path does not exist."
    elif not mp["model_configured"]:
        result["model_error"] = "model_path not configured."
    if cp["config_configured"] and cp["config_exists"] and not cp["config_is_file"]:
        result["config_error"] = "config_path is a directory."
    elif cp["config_configured"] and not cp["config_exists"]:
        result["config_error"] = "config_path does not exist."
    return result


def inspect_piper_license(model_card_path: Path | None) -> dict[str, Any]:
    ck = _path_check(model_card_path, "model_card")
    result = {**ck, "model_card_path": str(model_card_path) if model_card_path else "",
              "model_card_error": "", "license": "Unknown", "license_status": "review_required", "production_license_ready": False}
    if not ck["model_card_configured"]:
        result["model_card_error"] = "MODEL_CARD not configured."
        return result
    if ck["model_card_exists"] and not ck["model_card_is_file"]:
        result["model_card_error"] = "MODEL_CARD is a directory."
        return result
    if not ck["model_card_exists"]:
        result["model_card_error"] = "MODEL_CARD does not exist."
        return result
    if model_card_path:
        try:
            for line in model_card_path.read_text(encoding="utf-8").splitlines():
                lc = line.strip().lower()
                if lc.startswith("* license:") or lc.startswith("license:"):
                    result["license"] = line.split(":", 1)[1].strip() or "Unknown"
                    break
        except OSError as e:
            result["model_card_error"] = f"Cannot read MODEL_CARD: {e}"
            return result
    if result["license"].strip().lower() not in {"unknown", "n/a", "none", "tbd", "review required"}:
        result["license_status"] = "known"
        result["production_license_ready"] = True
    return result


def inspect_piper_license_policy(model_card_path: Path | None) -> dict[str, Any]:
    if model_card_path is None:
        return {"license_policy_path": "", "license_policy_exists": False, "license_policy_approved": False, "license_policy": {}}
    pp = model_card_path.with_name("LICENSE_REVIEW.json")
    if not pp.exists():
        return {"license_policy_path": str(pp), "license_policy_exists": False, "license_policy_approved": False, "license_policy": {}}
    policy = json.loads(pp.read_text(encoding="utf-8")) if pp.is_file() else {}
    return {"license_policy_path": str(pp), "license_policy_exists": True, "license_policy_approved": bool(policy.get("production_use_approved", False)) and bool(policy.get("repository_license", "")),
            "license_policy": policy, "license_policy_repository_license": str(policy.get("repository_license", "")).strip(),
            "license_policy_dataset_license": str(policy.get("dataset_license", "")).strip()}


def probe_piper_service(base_url: str, timeout: float = 1.0) -> dict:
    url = base_url.rstrip("/")
    try:
        p = get_json(f"{url}/health", int(timeout))
        return {"piper_service_configured": True, "piper_service_available": True, "piper_service_error": "", "piper_service_mode": str(p.get("mode", "http_service") or "http_service"), "piper_service_payload_keys": sorted(str(k) for k in p.keys()) if isinstance(p, dict) else []}
    except Exception as e:
        return {"piper_service_configured": True, "piper_service_available": False, "piper_service_error": str(e), "piper_service_mode": "unavailable", "piper_service_payload_keys": []}


def build_piper_preflight(local_settings: dict) -> dict:
    mp, cp = local_settings["model_path"], local_settings["config_path"]
    bu = str(local_settings.get("base_url", "")).strip()
    sv_st = probe_piper_service(bu, 1.0) if bu else {"piper_service_configured": False, "piper_service_available": False, "piper_service_error": "", "piper_service_mode": "local_process", "piper_service_payload_keys": []}
    ca = command_available(str(local_settings["command"]))
    ps = inspect_piper_paths(mp, cp)
    ls = inspect_piper_license(local_settings.get("model_card_path"))
    lp = inspect_piper_license_policy(local_settings.get("model_card_path"))
    if ls["license_status"] != "known" and lp.get("license_policy_approved"):
        ls["license_status"] = "approved_by_policy"
        ls["production_license_ready"] = True
        ls["license"] = str(lp.get("license_policy_repository_license", "approved"))
    ready = ((bool(bu) and sv_st["piper_service_available"]) or (not bu and ca)) and ps["model_configured"] and ps["model_exists"] and ps["model_is_file"] and ps["config_ready"]
    return {"ready": ready, "execution_transport": "http_service" if bu else "local_process", "command_available": ca,
            **sv_st, **ps, **ls, **lp, "base_url": bu, "model_path": str(mp) if mp else "", "config_path": str(cp) if cp else "",
            "notes": "Piper HTTP or local process, plus .onnx model and optional config."}


def build_piper_command(local_settings: dict) -> list[str]:
    mp = local_settings["model_path"]
    if mp is None:
        raise RuntimeError("Piper model_path not configured")
    args = [*command_parts(str(local_settings["command"])), "--model", str(mp), "--output_file", str(local_settings["output_path"])]
    if local_settings["config_path"]:
        args.extend(["--config", str(local_settings["config_path"])])
    if str(local_settings["speaker_id"]).strip():
        args.extend(["--speaker", str(local_settings["speaker_id"])])
    if str(local_settings["extra_args"]).strip():
        args.extend(shlex.split(str(local_settings["extra_args"])))
    return args


def build_piper_request_preview(request_item: dict, providers_config_path: Path) -> dict:
    ls = get_piper_settings(load_provider_settings(providers_config_path), providers_config_path, request_item.get("payload", {}))
    pf = build_piper_preflight(ls)
    if str(ls.get("base_url", "")).strip():
        return {"method": "POST", "url": f"{str(ls['base_url']).rstrip('/')}/synthesize", "headers": {"Content-Type": "application/json"},
                "body": {"text": ls["input_text"], "model_path": str(ls["model_path"]) if ls["model_path"] else "",
                         "config_path": str(ls["config_path"]) if ls["config_path"] else "",
                         "speaker_id": str(ls["speaker_id"]).strip(), "extra_args": str(ls["extra_args"]).strip(), "timeout_seconds": int(ls["timeout_seconds"])},
                "preflight": pf}
    cmd = build_piper_command(ls) if ls["model_path"] else []
    return {"method": "LOCAL_PROCESS", "url": "local:piper", "headers": {}, "body": {"input_text": ls["input_text"], "output_path": str(ls["output_path"]), "command": cmd}, "preflight": pf}


def build_local_request_preview(request_item: dict, providers_config_path: Path) -> dict:
    provider = str(request_item.get("payload", {}).get("provider", ""))
    if provider in LOCAL_COMFYUI_PROVIDERS:
        return build_comfyui_request_preview(request_item, providers_config_path)
    if provider == LOCAL_PIPER_PROVIDER:
        return build_piper_request_preview(request_item, providers_config_path)
    return {"method": "", "url": "", "headers": {}, "body": {}, "preflight": {"ready": False, "notes": f"Unsupported: {provider}"}}


# ---------------------------------------------------------------------------
# ComfyUI artifact extraction
# ---------------------------------------------------------------------------

def extract_first_comfyui_artifact(history: dict, prompt_id: str) -> dict | None:
    outputs = (history.get(prompt_id, {}) or {}).get("outputs", {})
    for out in outputs.values() if isinstance(outputs, dict) else []:
        if not isinstance(out, dict):
            continue
        for coll, kind in (("images", "image"), ("videos", "video"), ("gifs", "video")):
            for art in (out.get(coll) or []):
                if isinstance(art, dict) and art.get("filename"):
                    return {"filename": str(art["filename"]), "subfolder": str(art.get("subfolder", "")), "type": str(art.get("type", "output")), "artifact_kind": kind}
    return None


def extract_comfyui_execution_error(history: dict, prompt_id: str) -> str:
    status = (history.get(prompt_id, {}) or {}).get("status", {})
    for msg in (isinstance(status, dict) and status.get("messages") or []):
        if isinstance(msg, list) and len(msg) == 2 and msg[0] == "execution_error" and isinstance(msg[1], dict):
            loc = f"{msg[1].get('node_type', '')}#{msg[1].get('node_id', '')}" if msg[1].get("node_type") and msg[1].get("node_id") else str(msg[1].get("node_type", "") or msg[1].get("node_id", "") or "unknown")
            return f"ComfyUI error at {loc}: {msg[1].get('exception_message', '')}" if msg[1].get("exception_message") else f"ComfyUI error at {loc}"
    return f"ComfyUI prompt failed before producing an output artifact: {prompt_id}" if isinstance(status, dict) and str(status.get("status_str", "")).strip().lower() == "error" else ""


# ---------------------------------------------------------------------------
# Request execution
# ---------------------------------------------------------------------------

def perform_comfyui_request(request_item: dict, providers_config_path: Path) -> dict:
    settings = load_provider_settings(providers_config_path)
    payload = request_item.get("payload", {})
    provider = str(payload.get("provider", LOCAL_COMFYUI_PROVIDER))
    ls = get_comfyui_settings(settings, providers_config_path, payload, provider)
    wf = load_comfyui_workflow(ls)
    client_id = f"aicomic-{uuid.uuid4()}"
    resp = post_json(f"{ls['base_url']}/prompt", {"prompt": wf, "client_id": client_id}, int(ls["timeout_seconds"]))
    pid = str(resp.get("prompt_id", ""))
    if not pid:
        raise RuntimeError("No prompt_id from ComfyUI")
    deadline = time.time() + int(ls["poll_timeout_seconds"])
    meta = None
    while time.time() < deadline:
        hist = get_json(f"{ls['base_url']}/history/{pid}", int(ls["timeout_seconds"]))
        meta = extract_first_comfyui_artifact(hist, pid)
        if meta:
            break
        err = extract_comfyui_execution_error(hist, pid)
        if err:
            raise RuntimeError(err)
        time.sleep(float(ls["poll_interval_seconds"]))
    if not meta:
        raise RuntimeError(f"ComfyUI timed out: {pid}")
    query = urlencode({k: v for k, v in meta.items() if k != "artifact_kind"})
    data, ct = get_bytes(f"{ls['base_url']}/view?{query}", int(ls["timeout_seconds"]))
    op = Path(str(payload["output_path"]))
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_bytes(data)
    return {"provider": provider, "output_path": str(op), "content_type": ct, "response_meta": {"prompt_id": pid, "source_artifact": meta, "bytes": len(data)}}


def perform_piper_request(request_item: dict, providers_config_path: Path) -> dict:
    ls = get_piper_settings(load_provider_settings(providers_config_path), providers_config_path, request_item.get("payload", {}))
    if not build_piper_preflight(ls)["ready"]:
        raise RuntimeError("Piper not ready")
    op = Path(str(ls["output_path"]))
    op.parent.mkdir(parents=True, exist_ok=True)
    bu = str(ls.get("base_url", "")).strip()
    if bu:
        data, ct = post_json_for_bytes(f"{bu.rstrip('/')}/synthesize", {"text": str(ls["input_text"]), "model_path": str(ls["model_path"]) if ls["model_path"] else "", "config_path": str(ls["config_path"]) if ls["config_path"] else "", "speaker_id": str(ls["speaker_id"]).strip(), "extra_args": str(ls["extra_args"]).strip(), "timeout_seconds": int(ls["timeout_seconds"])}, int(ls["timeout_seconds"]))
        op.write_bytes(data)
        if not op.exists():
            raise RuntimeError(f"Piper HTTP did not create {op}")
        return {"provider": LOCAL_PIPER_PROVIDER, "output_path": str(op), "content_type": ct or "audio/wav", "response_meta": {"bytes": op.stat().st_size, "execution_transport": "http_service", "base_url": bu}}
    result = subprocess.run(build_piper_command(ls), input=str(ls["input_text"]), capture_output=True, text=True, timeout=int(ls["timeout_seconds"]), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Piper failed ({result.returncode}): {(result.stderr or result.stdout).strip()}")
    if not op.exists():
        raise RuntimeError(f"Piper did not create {op}")
    return {"provider": LOCAL_PIPER_PROVIDER, "output_path": str(op), "content_type": "audio/wav", "response_meta": {"bytes": op.stat().st_size, "stderr_tail": (result.stderr or "").strip()[-1000:], "execution_transport": "local_process"}}


# Public aliases for test compatibility
inspect_comfyui_workflow_path = _inspect_workflow_json
inspect_comfyui_workflow_model_usage = _inspect_model_loader_nodes
is_comfyui_fixture_model = _is_fixture


def comfyui_server_available(base_url: str, timeout_seconds: float = 1.0) -> tuple[bool, str]:
    """Check if ComfyUI server is reachable. Returns (available, error_string)."""
    try:
        get_json(f"{base_url}/system_stats", int(timeout_seconds))
        return True, ""
    except Exception as e:
        return False, str(e)


def perform_local_request(request_item: dict, providers_config_path: Path) -> dict:
    provider = str(request_item.get("payload", {}).get("provider", ""))
    if provider in LOCAL_COMFYUI_PROVIDERS:
        return perform_comfyui_request(request_item, providers_config_path)
    if provider == LOCAL_PIPER_PROVIDER:
        return perform_piper_request(request_item, providers_config_path)
    raise RuntimeError(f"Unsupported local provider: {provider}")
