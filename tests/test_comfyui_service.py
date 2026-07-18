from __future__ import annotations

import os
from pathlib import Path

import pytest

from aicomic.providers.comfyui_service import (
    ComfyUIServiceConfig,
    build_start_environment,
    ensure_runtime_directories,
    load_metadata,
    now_iso,
    pid_is_alive,
    read_known_pid,
    resolve_comfyui_service_config,
    timestamp_slug,
    validate_runtime_files,
    write_metadata,
    write_pid,
)


class TestNowIso:
    def test_returns_string(self) -> None:
        assert isinstance(now_iso(), str)

    def test_contains_tz_info(self) -> None:
        # Should have timezone offset like +08:00 or Z
        iso = now_iso()
        assert "+" in iso or "Z" in iso or "-" in iso[10:]


class TestTimestampSlug:
    def test_returns_14_digit_string(self) -> None:
        slug = timestamp_slug()
        assert len(slug) == 14
        assert slug.isdigit()


class TestComfyUIServiceConfig:
    def test_base_url(self) -> None:
        config = ComfyUIServiceConfig(
            project_root=Path("/p"), runtime_root=Path("/r"), comfyui_root=Path("/c"),
            python_executable=Path("/p"), extra_model_paths_config=Path("/e"),
            output_directory=Path("/o"), input_directory=Path("/i"),
            temp_directory=Path("/t"), reports_directory=Path("/rp"),
            state_directory=Path("/s"), metadata_path=Path("/m"),
            pid_path=Path("/pid"), host="0.0.0.0", port=8188,
        )
        assert config.base_url == "http://0.0.0.0:8188"

    def test_command_contains_args(self) -> None:
        config = ComfyUIServiceConfig(
            project_root=Path("/p"), runtime_root=Path("/r"), comfyui_root=Path("/c"),
            python_executable=Path("/py"), extra_model_paths_config=Path("/e"),
            output_directory=Path("/o"), input_directory=Path("/i"),
            temp_directory=Path("/t"), reports_directory=Path("/rp"),
            state_directory=Path("/s"), metadata_path=Path("/m"),
            pid_path=Path("/pid"), host="127.0.0.1", port=8188,
        )
        cmd = config.command
        assert str(config.python_executable) in cmd
        assert "main.py" in cmd
        assert "--port" in cmd
        assert "8188" in cmd
        assert "--listen" in cmd

    def test_frozen_dataclass(self) -> None:
        config = resolve_comfyui_service_config(project_root=Path("/tmp"))
        with pytest.raises(AttributeError):
            config.host = "changed"  # type: ignore[misc]


class TestResolveComfyUIServiceConfig:
    def test_returns_config(self) -> None:
        config = resolve_comfyui_service_config(project_root=Path("/tmp"))
        assert isinstance(config, ComfyUIServiceConfig)
        assert config.host == "127.0.0.1"
        assert config.port == 8188

    def test_custom_host_port(self) -> None:
        config = resolve_comfyui_service_config(project_root=Path("/tmp"), host="0.0.0.0", port=8888)
        assert config.host == "0.0.0.0"
        assert config.port == 8888

    def test_paths_under_project_root(self) -> None:
        config = resolve_comfyui_service_config(project_root=Path("/myproject"))
        assert config.comfyui_root == Path("/myproject/local_providers/comfyui/runtime/ComfyUI")
        assert config.state_directory == Path("/myproject/state/comfyui_service")


class TestEnsureRuntimeDirectories:
    def test_creates_directories(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        ensure_runtime_directories(config)
        assert config.reports_directory.exists()
        assert config.state_directory.exists()
        assert config.output_directory.exists()
        assert config.input_directory.exists()
        assert config.temp_directory.exists()


class TestMetadata:
    def test_load_metadata_missing(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        assert load_metadata(config) == {}

    def test_write_and_load(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        payload = {"pid": 12345, "status": "running"}
        write_metadata(config, payload)
        loaded = load_metadata(config)
        assert loaded["pid"] == 12345

    def test_write_metadata_creates_parent(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        write_metadata(config, {"test": True})
        assert config.metadata_path.exists()


class TestPid:
    def test_write_and_read(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        write_pid(config, 99999)
        pid = read_known_pid(config, {"pid": 99999})
        assert pid == 99999

    def test_read_no_metadata(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        assert read_known_pid(config) is None


class TestPidIsAlive:
    def test_none_pid(self) -> None:
        assert pid_is_alive(None) is False

    def test_invalid_pid(self) -> None:
        assert pid_is_alive(999999999) is False


class TestValidateRuntimeFiles:
    def test_all_missing(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        errors = validate_runtime_files(config)
        assert len(errors) >= 3  # comfyui_root, python, extra_model_paths all missing

    def test_all_exist(self, tmp_path: Path) -> None:
        config = resolve_comfyui_service_config(project_root=tmp_path)
        config.comfyui_root.mkdir(parents=True, exist_ok=True)
        config.python_executable.parent.mkdir(parents=True, exist_ok=True)
        config.python_executable.touch()
        config.extra_model_paths_config.parent.mkdir(parents=True, exist_ok=True)
        config.extra_model_paths_config.touch()
        assert validate_runtime_files(config) == []


class TestBuildStartEnvironment:
    def test_sets_defaults(self) -> None:
        env = build_start_environment()
        assert env.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1"
        assert env.get("PYTHONUNBUFFERED") == "1"

    def test_preserves_existing_env(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_VAR", "keep_me")
        env = build_start_environment()
        assert env.get("MY_VAR") == "keep_me"
