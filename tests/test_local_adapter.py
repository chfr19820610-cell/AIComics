from __future__ import annotations

import json
from pathlib import Path

import pytest

from aicomic.providers.local_adapter import (
    command_available,
    command_executable,
    command_parts,
    extract_comfyui_execution_error,
    extract_first_comfyui_artifact,
    inspect_comfyui_model_requirements,
    inspect_comfyui_workflow_model_usage,
    inspect_comfyui_workflow_path,
    inspect_piper_license,
    inspect_piper_license_policy,
    inspect_piper_paths,
    is_comfyui_fixture_model,
    optional_string,
    parse_float,
    parse_int,
    resolve_config_path,
    substitute_placeholders,
)
from aicomic.security.production_rehearsal import FIXTURE_MODEL_MARKER


class TestResolveConfigPath:
    @pytest.mark.parametrize("raw,expected", [
        ("/abs/path", "/abs/path"),
        ("", None),
        ("null", None),
        ("None", None),
        ("~", None),
    ])
    def test_paths(self, raw: str, expected: str | None, tmp_path: Path) -> None:
        result = resolve_config_path(raw, tmp_path)
        if expected is None:
            assert result is None
        else:
            assert str(result).endswith(expected)

    def test_relative(self, tmp_path: Path) -> None:
        assert str(resolve_config_path("sub/file.txt", tmp_path)).endswith("sub/file.txt")


class TestParseInt:
    @pytest.mark.parametrize("value,default,expected", [(42, 0, 42), ("abc", 5, 5), ("", 1, 1)])
    def test_parse(self, value: object, default: int, expected: int) -> None:
        assert parse_int(value, default) == expected


class TestParseFloat:
    @pytest.mark.parametrize("value,default,expected", [(3.14, 0.0, 3.14), ("abc", 1.5, 1.5), ("", 2.0, 2.0)])
    def test_parse(self, value: object, default: float, expected: float) -> None:
        assert parse_float(value, default) == expected


class TestOptionalString:
    @pytest.mark.parametrize("value,expected", [("hello", "hello"), ("null", ""), ("None", ""), ("~", ""), ("", "")])
    def test_optional(self, value: object, expected: str) -> None:
        assert optional_string(value) == expected

    def test_strips_quotes(self) -> None:
        assert optional_string('"hello"') == "hello"


class TestCommandParts:
    @staticmethod
    def test_basic() -> None:
        assert command_parts("piper --model test.onnx") == ["piper", "--model", "test.onnx"]

    @staticmethod
    def test_empty_fallback() -> None:
        assert command_parts("") == ["piper"]

    @staticmethod
    def test_env_command() -> None:
        assert command_parts("env python -m piper") == ["env", "python", "-m", "piper"]


class TestCommandExecutable:
    @pytest.mark.parametrize("command,expected", [
        ("piper", "piper"),
        ("/usr/bin/piper", "/usr/bin/piper"),
        ("env python -m piper", "python"),
        ("env -i piper", "piper"),
    ])
    def test_executable(self, command: str, expected: str) -> None:
        assert command_executable(command) == expected


class TestCommandAvailable:
    def test_existing_absolute(self, tmp_path: Path) -> None:
        exe = tmp_path / "test_bin"
        exe.touch()
        exe.chmod(0o755)
        assert command_available(str(exe)) is True

    def test_nonexistent(self) -> None:
        assert command_available("/nonexistent/binary_test") is False

    def test_nonexistent_relative(self) -> None:
        assert command_available("this_binary_should_not_exist_abc123") is False


class TestSubstitutePlaceholders:
    @pytest.mark.parametrize("value,expected", [
        ("{{key}}", "value"),
        ("prefix_{{key}}_suffix", "prefix_value_suffix"),
        (["{{key}}"], ["value"]),
        ({"a": "{{key}}"}, {"a": "value"}),
        (42, 42),
    ])
    def test_substitute(self, value: object, expected: object) -> None:
        assert substitute_placeholders(value, {"{{key}}": "value"}) == expected

    def test_direct_match(self) -> None:
        assert substitute_placeholders("direct_match", {"direct_match": "replaced"}) == "replaced"


class TestIsComfyuiFixtureModel:
    def test_detects_fixture_marker(self, tmp_path: Path) -> None:
        path = tmp_path / "fixture.safetensors"
        path.write_bytes(FIXTURE_MODEL_MARKER.encode("utf-8") + b"data")
        assert is_comfyui_fixture_model(path) is True

    def test_regular_model(self, tmp_path: Path) -> None:
        path = tmp_path / "model.safetensors"
        path.write_bytes(b"regular model data")
        assert is_comfyui_fixture_model(path) is False

    def test_nonexistent(self, tmp_path: Path) -> None:
        assert is_comfyui_fixture_model(tmp_path / "missing.bin") is False


class TestInspectComfyuiWorkflowPath:
    def test_none(self) -> None:
        result = inspect_comfyui_workflow_path(None)
        assert result["workflow_configured"] is False

    def test_valid_api_workflow(self, tmp_path: Path) -> None:
        wf = tmp_path / "workflow.json"
        wf.write_text(json.dumps({"1": {"class_type": "KSampler", "inputs": {"seed": 1}}}, ensure_ascii=False))
        result = inspect_comfyui_workflow_path(wf)
        assert result["workflow_api_format"] is True
        assert result["workflow_node_count"] == 1

    def test_not_api_format(self, tmp_path: Path) -> None:
        wf = tmp_path / "invalid.json"
        wf.write_text(json.dumps({"last_node_id": 5, "_meta": {}}, ensure_ascii=False))
        result = inspect_comfyui_workflow_path(wf)
        assert result["workflow_valid_json"] is True
        assert result["workflow_api_format"] is False

    def test_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "workflow_dir"
        d.mkdir()
        result = inspect_comfyui_workflow_path(d)
        assert "directory" in result["workflow_error"]

    def test_non_existent(self, tmp_path: Path) -> None:
        result = inspect_comfyui_workflow_path(tmp_path / "missing.json")
        assert "does not exist" in result["workflow_error"]

    def test_invalid_json(self, tmp_path: Path) -> None:
        wf = tmp_path / "bad.json"
        wf.write_text("{bad json", encoding="utf-8")
        result = inspect_comfyui_workflow_path(wf)
        assert "Invalid JSON" in result["workflow_error"]


class TestInspectComfyuiWorkflowModelUsage:
    def test_no_workflow(self) -> None:
        assert inspect_comfyui_workflow_model_usage(None)["workflow_requires_model_files"] is True

    def test_with_loader_node(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.json"
        wf.write_text(json.dumps({"5": {"class_type": "CLIPLoader", "inputs": {}}}))
        result = inspect_comfyui_workflow_model_usage(wf)
        assert result["workflow_requires_model_files"] is True
        assert result["workflow_model_loader_count"] == 1

    def test_no_loader_nodes(self, tmp_path: Path) -> None:
        wf = tmp_path / "wf.json"
        wf.write_text(json.dumps({"5": {"class_type": "KSampler", "inputs": {}}}))
        result = inspect_comfyui_workflow_model_usage(wf)
        assert result["workflow_requires_model_files"] is False

    def test_loader_in_name(self, tmp_path: Path) -> None:
        """'loader' substring in class_type should also be detected."""
        wf = tmp_path / "wf.json"
        wf.write_text(json.dumps({"5": {"class_type": "MyCustomLoader", "inputs": {}}}))
        result = inspect_comfyui_workflow_model_usage(wf)
        assert result["workflow_requires_model_files"] is True


class TestInspectComfyuiModelRequirements:
    def test_not_configured(self) -> None:
        result = inspect_comfyui_model_requirements("local_comfyui_image", None, None)
        assert result["model_manifest_configured"] is False
        assert result["model_root_configured"] is False

    def test_manifest_not_exists(self, tmp_path: Path) -> None:
        result = inspect_comfyui_model_requirements("local_comfyui_image", tmp_path, tmp_path / "missing.json")
        assert result["model_manifest_exists"] is False


class TestInspectPiperPaths:
    def test_not_configured(self) -> None:
        result = inspect_piper_paths(None, None)
        assert result["model_configured"] is False

    def test_model_exists(self, tmp_path: Path) -> None:
        model = tmp_path / "voice.onnx"
        model.touch()
        result = inspect_piper_paths(model, None)
        assert result["model_is_file"] is True

    def test_model_is_directory(self, tmp_path: Path) -> None:
        result = inspect_piper_paths(tmp_path, None)
        assert "directory" in result["model_error"]


class TestInspectPiperLicense:
    def test_not_configured(self) -> None:
        result = inspect_piper_license(None)
        assert result["model_card_configured"] is False

    def test_reads_license(self, tmp_path: Path) -> None:
        card = tmp_path / "MODEL_CARD"
        card.write_text("* License: MIT\nOther: data\n", encoding="utf-8")
        result = inspect_piper_license(card)
        assert result["license"] == "MIT"
        assert result["production_license_ready"] is True

    def test_unknown_license(self, tmp_path: Path) -> None:
        card = tmp_path / "MODEL_CARD"
        card.write_text("Description: Some model\n", encoding="utf-8")
        result = inspect_piper_license(card)
        assert result["license_status"] == "review_required"
        assert result["production_license_ready"] is False


class TestInspectPiperLicensePolicy:
    def test_no_card(self) -> None:
        assert inspect_piper_license_policy(None)["license_policy_exists"] is False

    def test_policy_approved(self, tmp_path: Path) -> None:
        card = tmp_path / "MODEL_CARD"
        card.touch()
        policy = tmp_path / "LICENSE_REVIEW.json"
        policy.write_text(json.dumps({"repository_license": "MIT", "production_use_approved": True}))
        result = inspect_piper_license_policy(card)
        assert result["license_policy_approved"] is True

    def test_policy_not_approved(self, tmp_path: Path) -> None:
        card = tmp_path / "MODEL_CARD"
        card.touch()
        policy = tmp_path / "LICENSE_REVIEW.json"
        policy.write_text(json.dumps({"repository_license": "", "production_use_approved": False}))
        result = inspect_piper_license_policy(card)
        assert result["license_policy_approved"] is False


class TestExtractComfyuiArtifact:
    def test_extracts_image(self) -> None:
        history = {"prompt_1": {"outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}}}}
        result = extract_first_comfyui_artifact(history, "prompt_1")
        assert result is not None
        assert result["artifact_kind"] == "image"
        assert result["filename"] == "out.png"

    def test_no_output(self) -> None:
        assert extract_first_comfyui_artifact({"prompt_1": {"outputs": {}}}, "prompt_1") is None


class TestExtractComfyuiExecutionError:
    def test_extracts_error(self) -> None:
        history = {
            "prompt_1": {
                "status": {
                    "messages": [
                        ["execution_error", {"node_type": "KSampler", "node_id": "5", "exception_message": "OOM"}]
                    ]
                }
            }
        }
        result = extract_comfyui_execution_error(history, "prompt_1")
        assert "OOM" in result
        assert "KSampler#5" in result

    def test_no_error(self) -> None:
        assert extract_comfyui_execution_error({"prompt_1": {"status": {"messages": []}}}, "prompt_1") == ""

    def test_status_str_error(self) -> None:
        history = {"prompt_1": {"status": {"status_str": "error", "messages": [["something", {}]]}}}
        result = extract_comfyui_execution_error(history, "prompt_1")
        assert "failed before producing" in result
