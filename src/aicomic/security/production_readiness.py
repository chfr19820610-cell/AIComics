from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aicomic.core.edition import load_edition_capability, resolve_edition_config_path
from aicomic.utils.atomic_io import atomic_write_json
from aicomic.core.config import ProjectPaths
from aicomic.core.runtime_env import prime_runtime_env_for_web_config
from aicomic.providers.readiness import build_provider_readiness_report
from aicomic.security.dependency_audit import build_dependency_audit_report


DEFAULT_JWT_SECRETS = {
    "aicomic-dev-secret-change-me",
    "change-me",
    "dev-secret",
    "secret",
}


def parse_scalar(raw_value: str) -> Any:
    value = os.path.expandvars(raw_value.strip().strip("'").strip('"'))
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def load_two_level_yaml(config_path: Path) -> dict[str, dict[str, Any]]:
    if not config_path.exists():
        return {}
    config_map: dict[str, dict[str, Any]] = {}
    current_section = ""
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            config_map.setdefault(current_section, {})
            continue
        if ":" not in line or not current_section:
            continue
        key, raw_value = line.split(":", 1)
        config_map[current_section][key.strip()] = parse_scalar(raw_value)
    return config_map


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def make_risk(
    risk_id: str,
    title: str,
    category: str,
    severity: str,
    evidence: str,
    remediation: str,
    production_blocking: bool,
    status: str = "open",
) -> dict[str, Any]:
    return {
        "id": risk_id,
        "title": title,
        "category": category,
        "severity": severity,
        "status": status,
        "production_blocking": production_blocking,
        "evidence": evidence,
        "remediation": remediation,
    }


def collect_provider_items(provider_readiness: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("provider", "")): item
        for item in provider_readiness.get("items", [])
        if isinstance(item, dict) and item.get("provider")
    }


def collect_auth_risks(web_config_path: Path) -> list[dict[str, Any]]:
    prime_runtime_env_for_web_config(web_config_path)
    config = load_two_level_yaml(web_config_path)
    server = config.get("server", {})
    auth = config.get("auth", {})
    cors_raw = str(server.get("cors_allow_origins", "*"))
    cors_values = [item.strip() for item in cors_raw.split(",") if item.strip()]
    jwt_secret = str(auth.get("jwt_secret", ""))
    risks: list[dict[str, Any]] = []

    if "*" in cors_values:
        risks.append(
            make_risk(
                "prod-cors-wildcard",
                "Production CORS allows every origin",
                "web_auth",
                "high",
                f"{web_config_path}: server.cors_allow_origins={cors_raw}",
                "Use an explicit production domain list in config/web.production.example.yaml or AICOMIC_WEB_CONFIG_PATH.",
                True,
            )
        )
    if not bool(auth.get("auth_enabled", False)):
        risks.append(
            make_risk(
                "prod-auth-disabled",
                "Production auth is disabled",
                "web_auth",
                "critical",
                f"{web_config_path}: auth.auth_enabled={auth.get('auth_enabled', False)}",
                "Enable auth.auth_enabled for production and require personal password login.",
                True,
            )
        )
    if bool(auth.get("dev_login_enabled", False)):
        risks.append(
            make_risk(
                "prod-dev-login-enabled",
                "Development login remains enabled",
                "web_auth",
                "high",
                f"{web_config_path}: auth.dev_login_enabled={auth.get('dev_login_enabled', False)}",
                "Disable auth.dev_login_enabled in the production web config.",
                True,
            )
        )
    if bool(auth.get("mock_sso_enabled", False)):
        risks.append(
            make_risk(
                "prod-mock-sso-enabled",
                "Mock SSO remains enabled",
                "web_auth",
                "high",
                f"{web_config_path}: auth.mock_sso_enabled={auth.get('mock_sso_enabled', False)}",
                "Disable auth.mock_sso_enabled in the production web config.",
                True,
            )
        )
    if jwt_secret in DEFAULT_JWT_SECRETS or "${" in jwt_secret or len(jwt_secret) < 32:
        risks.append(
            make_risk(
                "prod-jwt-secret-unsafe",
                "JWT secret is not production-safe",
                "web_auth",
                "critical",
                f"{web_config_path}: auth.jwt_secret is default, placeholder, or too short.",
                "Set AICOMIC_JWT_SECRET to a long random secret and load it through the production web config.",
                True,
            )
        )
    return risks


def collect_edition_risks(edition_config_path: Path | None, deployment_mode: str) -> list[dict[str, Any]]:
    if deployment_mode != "production":
        return []

    active_edition_config_path = resolve_edition_config_path(edition_config_path)
    edition = load_edition_capability(active_edition_config_path)
    risks: list[dict[str, Any]] = []
    evidence_prefix = f"{active_edition_config_path}: edition.name={edition.edition_name}"
    if edition.edition_name != "creator":
        risks.append(
            make_risk(
                "prod-edition-not-creator-only",
                "Production edition is not aligned to the Creator-only product scope",
                "web_auth",
                "high",
                evidence_prefix,
                "Use the creator-only edition config for this project and point AICOMIC_EDITION_CONFIG_PATH to config/edition.production.yaml.",
                True,
            )
        )
    if not edition.auth_enabled:
        risks.append(
            make_risk(
                "prod-edition-auth-disabled",
                "Production edition disables auth at policy level",
                "web_auth",
                "critical",
                f"{evidence_prefix}, auth_enabled={edition.auth_enabled}",
                "Use an edition with auth_enabled=true, such as config/edition.production.yaml.",
                True,
            )
        )
    if edition.multi_user_enabled or edition.rbac_enabled or edition.audit_enabled or edition.oidc_enabled:
        risks.append(
            make_risk(
                "prod-edition-enterprise-capabilities-present",
                "Production edition still exposes enterprise-oriented capabilities",
                "web_auth",
                "high",
                (
                    f"{evidence_prefix}, multi_user_enabled={edition.multi_user_enabled},"
                    f" rbac_enabled={edition.rbac_enabled}, audit_enabled={edition.audit_enabled},"
                    f" oidc_enabled={edition.oidc_enabled}"
                ),
                "Disable multi-user, RBAC, audit, and OIDC capabilities in the active edition config.",
                True,
            )
        )
    return risks


def collect_comfyui_risks(provider_items: dict[str, dict[str, Any]], deployment_mode: str = "production") -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    labels = {
        "local_comfyui_image": "image",
        "local_comfyui_video": "video",
    }
    for provider, label in labels.items():
        item = provider_items.get(provider, {})
        readiness = item.get("readiness", {}) if isinstance(item, dict) else {}
        if not bool(readiness.get("workflow_api_format", False)):
            risks.append(
                make_risk(
                    f"{provider}-workflow-not-ready",
                    f"ComfyUI {label} workflow is not production-ready",
                    "local_provider",
                    "high",
                    str(readiness.get("workflow_error", "Workflow API format is not ready.")),
                    "Export a ComfyUI API prompt JSON and point providers.yaml to the concrete file.",
                    True,
                )
            )
        if not bool(readiness.get("comfyui_server_available", False)):
            risks.append(
                make_risk(
                    f"{provider}-server-unavailable",
                    f"ComfyUI {label} server is unavailable",
                    "local_provider",
                    "high",
                    str(readiness.get("comfyui_server_error", "ComfyUI /system_stats did not respond.")),
                    "Start ComfyUI at the configured base_url, then run provider-readiness and --confirm-live --limit 1.",
                    True,
                )
            )
        elif str(readiness.get("comfyui_server_mode", "")) == "mock":
            risks.append(
                make_risk(
                    f"{provider}-mock-server-used",
                    f"ComfyUI {label} uses mock rehearsal server",
                    "local_provider",
                    "medium",
                    f"base_url={readiness.get('base_url', '')}",
                    "Use a real ComfyUI service for final production acceptance; mock mode is only valid for CI/rehearsal.",
                    deployment_mode == "production",
                )
            )
        if not bool(readiness.get("required_models_ready", False)):
            missing = readiness.get("missing_required_models", [])
            risks.append(
                make_risk(
                    f"{provider}-models-missing",
                    f"ComfyUI {label} model weights are not validated",
                    "local_provider",
                    "high",
                    json.dumps(missing, ensure_ascii=False) if missing else "Required model manifest is missing or empty.",
                    "Place the listed model files under local_providers/comfyui/models and rerun provider-readiness.",
                    True,
                )
            )
        elif int(readiness.get("fixture_required_model_count", 0)) > 0:
            risks.append(
                make_risk(
                    f"{provider}-fixture-models-used",
                    f"ComfyUI {label} uses fixture model files",
                    "local_provider",
                    "medium",
                    json.dumps(readiness.get("fixture_required_models", []), ensure_ascii=False),
                    "Replace fixture model files with real ComfyUI weights before final production inference.",
                    deployment_mode == "production",
                )
            )
    return risks


def collect_piper_risks(provider_items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    item = provider_items.get("local_piper_tts", {})
    readiness = item.get("readiness", {}) if isinstance(item, dict) else {}
    risks: list[dict[str, Any]] = []
    if not bool(readiness.get("ready", False)):
        risks.append(
            make_risk(
                "local-piper-runtime-not-ready",
                "Piper TTS runtime is not ready",
                "local_provider",
                "high",
                str(readiness.get("model_error") or readiness.get("config_error") or readiness.get("notes", "")),
                "Install Piper, configure the .onnx voice model and JSON config, then run a one-shot local TTS validation.",
                True,
            )
        )
    if readiness.get("license_status") not in {"known", "approved_by_policy"}:
        risks.append(
            make_risk(
                "local-piper-license-review-required",
                "Piper voice license needs commercial review",
                "local_provider",
                "medium",
                f"license={readiness.get('license', 'Unknown')}, model_card_path={readiness.get('model_card_path', '')}",
                "Replace the voice with a known commercial-safe model or attach legal approval for the current MODEL_CARD.",
                False,
            )
        )
    return risks


def collect_video_runtime_risks(
    providers_config_path: Path,
    provider_items: dict[str, dict[str, Any]],
    deployment_mode: str,
) -> list[dict[str, Any]]:
    if deployment_mode != "production":
        return []
    config = load_two_level_yaml(providers_config_path)
    video_config = config.get("local_comfyui_video", {})
    video_item = provider_items.get("local_comfyui_video", {})
    readiness = video_item.get("readiness", {}) if isinstance(video_item, dict) else {}
    risks: list[dict[str, Any]] = []
    workflow_path = str(readiness.get("workflow_path") or video_config.get("workflow_path", ""))
    if "live_smoke" in workflow_path:
        risks.append(
            make_risk(
                "local_comfyui_video-smoke-workflow-used",
                "ComfyUI video production route uses smoke workflow",
                "local_provider",
                "high",
                f"workflow_path={workflow_path}",
                "Use the full production video workflow for production batches; reserve smoke workflows for health checks.",
                True,
            )
        )
    try:
        poll_timeout_seconds = int(video_config.get("poll_timeout_seconds", 0))
    except (TypeError, ValueError):
        poll_timeout_seconds = 0
    if poll_timeout_seconds and poll_timeout_seconds < 1800:
        risks.append(
            make_risk(
                "local_comfyui_video-timeout-budget-low",
                "ComfyUI full video timeout budget is below observed local runtime",
                "local_provider",
                "medium",
                f"poll_timeout_seconds={poll_timeout_seconds}; observed_mps_full_video_exceeded=900",
                "Raise the production video timeout budget, use asynchronous result collection, or route full video jobs to a faster GPU worker.",
                False,
            )
        )
    return risks


def collect_dependency_risks(project_root: Path, dependency_audit_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dependency_report = load_optional_json(dependency_audit_path)
    if not dependency_report:
        dependency_report = build_dependency_audit_report(project_root)
    risks: list[dict[str, Any]] = []
    if not bool(dependency_report.get("direct_lock_enforced", False)):
        risks.append(
            make_risk(
                "dependency-lock-not-enforced",
                "Python dependency lock is not enforced",
                "supply_chain",
                "high",
                json.dumps(
                    {
                        "missing_direct_pins": dependency_report.get("missing_direct_pins", []),
                        "docker_constraint_enabled": dependency_report.get("docker_constraint_enabled", False),
                    },
                    ensure_ascii=False,
                ),
                "Pin direct runtime dependencies in requirements-lock.txt and enforce it in Dockerfile.",
                True,
            )
        )
    if dependency_report.get("cve_audit_status") != "completed":
        risks.append(
            make_risk(
                "dependency-cve-audit-not-completed",
                "Dependency CVE audit has not completed",
                "supply_chain",
                "medium",
                f"audit_tool_status={dependency_report.get('audit_tool_status', 'unknown')}",
                "Install pip-audit in the validation image or CI and archive reports/dependency_audit_report.json.",
                False,
            )
        )
    elif int(dependency_report.get("known_vulnerability_count", 0)) > 0:
        risks.append(
            make_risk(
                "dependency-known-vulnerabilities",
                "Dependency CVE audit found known vulnerabilities",
                "supply_chain",
                "high",
                f"known_vulnerability_count={dependency_report.get('known_vulnerability_count', 0)}",
                "Upgrade or pin patched package versions, then rerun dependency-audit.",
                True,
            )
        )
    if str(dependency_report.get("transitive_lock_status", "")) != "fully_locked":
        risks.append(
            make_risk(
                "dependency-transitive-lock-pending",
                "Transitive dependencies are not fully locked",
                "supply_chain",
                "medium",
                f"transitive_lock_status={dependency_report.get('transitive_lock_status', 'unknown')}",
                "Promote the direct constraints file to a fully resolved lock generated by pip-tools/uv before production release.",
                False,
            )
        )
    return dependency_report, risks


def build_production_risk_register(
    project_root: Path | None = None,
    web_config_path: Path | None = None,
    edition_config_path: Path | None = None,
    providers_config_path: Path | None = None,
    provider_readiness_path: Path | None = None,
    dependency_audit_path: Path | None = None,
    require_openai_live: bool = False,
    deployment_mode: str = "production",
) -> dict[str, Any]:
    root = (project_root or ProjectPaths.project_root()).resolve()
    active_web_config_path = (
        web_config_path
        or Path(os.environ.get("AICOMIC_WEB_CONFIG_PATH", "").strip() or root / "config" / "web.yaml")
    ).resolve()
    active_edition_config_path = resolve_edition_config_path(edition_config_path).resolve()
    active_providers_config_path = (providers_config_path or ProjectPaths.providers_config_path()).resolve()
    active_provider_readiness_path = (provider_readiness_path or root / "reports" / "provider_readiness_report.json").resolve()
    active_dependency_audit_path = (dependency_audit_path or root / "reports" / "dependency_audit_report.json").resolve()

    provider_readiness = load_optional_json(active_provider_readiness_path)
    if not provider_readiness:
        provider_requests_path = root / "reports" / "provider_requests_local.json"
        provider_readiness = build_provider_readiness_report(active_providers_config_path, provider_requests_path)
    provider_items = collect_provider_items(provider_readiness)

    dependency_report, dependency_risks = collect_dependency_risks(root, active_dependency_audit_path)
    risk_items = [
        *collect_auth_risks(active_web_config_path),
        *collect_edition_risks(active_edition_config_path, deployment_mode),
        *collect_comfyui_risks(provider_items, deployment_mode=deployment_mode),
        *collect_piper_risks(provider_items),
        *collect_video_runtime_risks(active_providers_config_path, provider_items, deployment_mode=deployment_mode),
        *dependency_risks,
    ]
    excluded_items: list[dict[str, Any]] = []
    if not require_openai_live:
        excluded_items.append(
            {
                "id": "openai-live-provider-disabled",
                "title": "OpenAI live provider disabled",
                "status": "excluded_by_current_scope",
                "reason": "User explicitly excluded OpenAI live provider risk from this repair cycle.",
            }
        )

    blocking_count = sum(1 for item in risk_items if item["status"] == "open" and item["production_blocking"])
    warning_count = sum(1 for item in risk_items if item["status"] == "open" and not item["production_blocking"])
    status = "blocked_for_production" if blocking_count else "ready_with_warnings" if warning_count else "ready_for_production"
    return {
        "status": status,
        "project_root": str(root),
        "web_config_path": str(active_web_config_path),
        "edition_config_path": str(active_edition_config_path),
        "providers_config_path": str(active_providers_config_path),
        "provider_readiness_path": str(active_provider_readiness_path),
        "dependency_audit_path": str(active_dependency_audit_path),
        "require_openai_live": require_openai_live,
        "deployment_mode": deployment_mode,
        "risk_count": len(risk_items),
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "risk_items": risk_items,
        "excluded_items": excluded_items,
        "provider_readiness_summary": {
            "status": provider_readiness.get("status", "unknown"),
            "manual_fallback_ready": provider_readiness.get("manual_fallback_ready", False),
            "local_core_ready": provider_readiness.get("local_core_ready", False),
            "local_video_ready": provider_readiness.get("local_video_ready", False),
            "full_local_ready": provider_readiness.get("full_local_ready", False),
        },
        "dependency_audit_summary": {
            "lock_status": dependency_report.get("lock_status", "unknown"),
            "transitive_lock_status": dependency_report.get("transitive_lock_status", "unknown"),
            "cve_audit_status": dependency_report.get("cve_audit_status", "unknown"),
            "audit_tool_status": dependency_report.get("audit_tool_status", "unknown"),
            "known_vulnerability_count": dependency_report.get("known_vulnerability_count", 0),
        },
        "next_actions": build_next_actions(risk_items),
    }


def build_next_actions(risk_items: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for risk in risk_items:
        remediation = str(risk.get("remediation", "")).strip()
        if remediation and remediation not in actions:
            actions.append(remediation)
    if not actions:
        actions.append("No open production readiness risks remain in the current scope.")
    return actions


def write_production_risk_register(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)
