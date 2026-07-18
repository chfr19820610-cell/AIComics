from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.config import ProjectPaths
from aicomic.providers.readiness import build_provider_readiness_report, write_provider_readiness_report
from aicomic.security.dependency_audit import build_dependency_audit_report, write_dependency_audit_report
from aicomic.security.production_readiness import (
    build_production_risk_register,
    collect_auth_risks,
    collect_edition_risks,
    write_production_risk_register,
)
from aicomic.security.production_rehearsal import (
    build_rehearsal_environment,
    prepare_comfyui_fixture_models,
    run_mock_comfyui_server,
    temporary_environment,
)


def assert_openai_excluded(risk_register: dict[str, object]) -> None:
    risk_ids = {str(item["id"]) for item in risk_register["risk_items"]}
    excluded_ids = {str(item["id"]) for item in risk_register["excluded_items"]}
    if "openai-live-provider-disabled" in risk_ids:
        raise RuntimeError("OpenAI live provider risk must be excluded from this validation scope.")
    if "openai-live-provider-disabled" not in excluded_ids:
        raise RuntimeError("OpenAI live provider exclusion was not recorded.")


def main() -> int:
    provider_requests_path = ProjectPaths.reports_dir() / "provider_requests_local.json"
    provider_readiness_path = ProjectPaths.reports_dir() / "provider_readiness_report.json"
    strict_provider_readiness_path = ProjectPaths.reports_dir() / "provider_readiness_strict_report.json"
    strict_provider_readiness = build_provider_readiness_report(ProjectPaths.providers_config_path(), provider_requests_path)
    write_provider_readiness_report(provider_readiness_path, strict_provider_readiness)
    write_provider_readiness_report(strict_provider_readiness_path, strict_provider_readiness)

    dependency_audit_path = ProjectPaths.reports_dir() / "dependency_audit_report.json"
    dependency_audit = build_dependency_audit_report(PROJECT_ROOT)
    write_dependency_audit_report(dependency_audit_path, dependency_audit)

    production_risk_register_path = ProjectPaths.reports_dir() / "production_risk_register.json"
    strict_risk_register_path = ProjectPaths.reports_dir() / "production_risk_register_strict.json"
    strict_risk_register = build_production_risk_register(
        PROJECT_ROOT,
        web_config_path=PROJECT_ROOT / "config" / "web.yaml",
        edition_config_path=PROJECT_ROOT / "config" / "edition.yaml",
        providers_config_path=ProjectPaths.providers_config_path(),
        provider_readiness_path=strict_provider_readiness_path,
        dependency_audit_path=dependency_audit_path,
        require_openai_live=False,
        deployment_mode="production",
    )
    write_production_risk_register(production_risk_register_path, strict_risk_register)
    write_production_risk_register(strict_risk_register_path, strict_risk_register)
    strict_risk_ids = {str(item["id"]) for item in strict_risk_register["risk_items"]}
    expected_strict_risks = {str(item["id"]) for item in collect_auth_risks(PROJECT_ROOT / "config" / "web.yaml")}
    expected_strict_risks.update(
        str(item["id"]) for item in collect_edition_risks(PROJECT_ROOT / "config" / "edition.yaml", "production")
    )
    if not bool(strict_provider_readiness.get("full_local_ready", False)):
        expected_strict_risks.update(
            {
                "local_comfyui_image-server-unavailable",
                "local_comfyui_video-server-unavailable",
                "local_comfyui_image-models-missing",
                "local_comfyui_video-models-missing",
            }
        )
    missing_expected = sorted(expected_strict_risks - strict_risk_ids)
    if missing_expected:
        raise RuntimeError(f"strict production risk register did not detect expected risks: {missing_expected}")
    if expected_strict_risks and int(strict_risk_register["blocking_count"]) <= 0:
        raise RuntimeError("strict production register should block open production risks.")
    assert_openai_excluded(strict_risk_register)

    rehearsal_model_root = ProjectPaths.state_dir() / "production_rehearsal_validation" / "comfyui_models"
    fixture_report = prepare_comfyui_fixture_models(
        rehearsal_model_root,
        PROJECT_ROOT / "local_providers" / "comfyui" / "model_requirements.json",
    )
    with run_mock_comfyui_server() as mock_comfyui:
        rehearsal_env = build_rehearsal_environment(PROJECT_ROOT, str(mock_comfyui["base_url"]), rehearsal_model_root)
        with temporary_environment(rehearsal_env):
            rehearsal_provider_readiness_path = ProjectPaths.reports_dir() / "provider_readiness_rehearsal_report.json"
            rehearsal_provider_readiness = build_provider_readiness_report(ProjectPaths.providers_config_path(), provider_requests_path)
            write_provider_readiness_report(rehearsal_provider_readiness_path, rehearsal_provider_readiness)
            rehearsal_risk_register_path = ProjectPaths.reports_dir() / "production_risk_register_rehearsal.json"
            rehearsal_risk_register = build_production_risk_register(
                PROJECT_ROOT,
                web_config_path=PROJECT_ROOT / "config" / "web.production.example.yaml",
                providers_config_path=ProjectPaths.providers_config_path(),
                provider_readiness_path=rehearsal_provider_readiness_path,
                dependency_audit_path=dependency_audit_path,
                require_openai_live=False,
                deployment_mode="rehearsal",
            )
            write_production_risk_register(rehearsal_risk_register_path, rehearsal_risk_register)

    rehearsal_risk_ids = {str(item["id"]) for item in rehearsal_risk_register["risk_items"]}
    if int(rehearsal_risk_register["blocking_count"]) != 0:
        raise RuntimeError(f"rehearsal risk register should have no blocking risks: {rehearsal_risk_register}")
    if "local-piper-license-review-required" in rehearsal_risk_ids:
        raise RuntimeError("Piper license policy should resolve the prior unknown-license warning.")
    if not {
        "local_comfyui_image-mock-server-used",
        "local_comfyui_video-mock-server-used",
        "local_comfyui_image-fixture-models-used",
        "local_comfyui_video-fixture-models-used",
    }.issubset(rehearsal_risk_ids):
        raise RuntimeError(f"rehearsal register should record mock/fixture warnings: {sorted(rehearsal_risk_ids)}")
    assert_openai_excluded(rehearsal_risk_register)
    if dependency_audit["lock_status"] != "direct_lock_enforced":
        raise RuntimeError(f"dependency direct lock should be enforced: {dependency_audit['lock_status']}")

    validation_payload = {
        "run_id": f"production_risk_register_validation_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "run_at": datetime.now().astimezone().isoformat(),
        "strict": {
            "status": strict_risk_register["status"],
            "risk_count": strict_risk_register["risk_count"],
            "blocking_count": strict_risk_register["blocking_count"],
            "warning_count": strict_risk_register["warning_count"],
            "provider_readiness_path": str(provider_readiness_path),
            "canonical_risk_register_path": str(production_risk_register_path),
            "risk_register_path": str(strict_risk_register_path),
        },
        "rehearsal": {
            "status": rehearsal_risk_register["status"],
            "risk_count": rehearsal_risk_register["risk_count"],
            "blocking_count": rehearsal_risk_register["blocking_count"],
            "warning_count": rehearsal_risk_register["warning_count"],
            "provider_readiness_path": str(rehearsal_provider_readiness_path),
            "risk_register_path": str(rehearsal_risk_register_path),
            "fixture_model_count": fixture_report["fixture_model_count"],
            "mock_comfyui_base_url": mock_comfyui["base_url"],
        },
        "expected_strict_risks_detected": True,
        "openai_excluded": True,
        "dependency_lock_status": dependency_audit["lock_status"],
        "dependency_transitive_lock_status": dependency_audit["transitive_lock_status"],
        "dependency_cve_audit_status": dependency_audit["cve_audit_status"],
        "strict_full_local_ready": bool(strict_provider_readiness.get("full_local_ready", False)),
        "report_path": str(ProjectPaths.reports_dir() / "production_risk_register_validation_report.json"),
    }
    output_path = ProjectPaths.reports_dir() / "production_risk_register_validation_report.json"
    output_path.write_text(json.dumps(validation_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
