"""Tests for ROADMAP gap closures — cookie persist, template override, full pipeline, multilang episode, remote GPU."""
from __future__ import annotations

from pathlib import Path

import pytest


# === ④ Cookie 持久化 ===

class TestCookiePersist:
    def test_check_cookie_validity(self, tmp_path):
        from aicomic.publish.cookie_manager import check_cookie_validity, CookieStatus
        cookie_path = tmp_path / "douyin_test.json"
        cookie_path.write_text('[{"name":"sessionid","value":"abc","expires":9999999999}]')
        status = check_cookie_validity(cookie_path, platform="douyin")
        assert isinstance(status, CookieStatus)
        assert status.valid is True

    def test_expired_cookie_detected(self, tmp_path):
        from aicomic.publish.cookie_manager import check_cookie_validity, CookieStatus
        cookie_path = tmp_path / "expired.json"
        cookie_path.write_text('[{"name":"sessionid","value":"abc","expires":1000}]')
        status = check_cookie_validity(cookie_path, platform="douyin")
        assert status.valid is False
        assert status.reason == "expired"

    def test_missing_cookie(self, tmp_path):
        from aicomic.publish.cookie_manager import check_cookie_validity
        status = check_cookie_validity(tmp_path / "nonexistent.json", platform="douyin")
        assert status.valid is False
        assert status.reason == "not_found"

    def test_batch_check_all_platforms(self, tmp_path):
        from aicomic.publish.cookie_manager import batch_check_cookies
        results = batch_check_cookies({
            "douyin": tmp_path / "douyin.json",
            "xiaohongshu": tmp_path / "xhs.json",
        })
        assert "douyin" in results
        assert "xiaohongshu" in results
        assert all(not r.valid for r in results.values())  # both don't exist


# === ① 模板覆盖管线 ===

class TestTemplatePipelineOverride:
    def test_template_has_pipeline_override_field(self):
        from aicomic.core.template_engine import load_template, get_pipeline_override
        t = load_template("horror")
        # pipeline_override is optional; get_pipeline_override always returns a dict
        override = get_pipeline_override("horror")
        assert isinstance(override, dict)

    def test_get_pipeline_override_returns_dict(self):
        from aicomic.core.template_engine import get_pipeline_override
        override = get_pipeline_override("horror")
        assert isinstance(override, dict)

    def test_unknown_template_returns_empty_override(self):
        from aicomic.core.template_engine import get_pipeline_override
        override = get_pipeline_override("nonexistent")
        assert override == {}


# === ② 蓝图→分镜→全管线 ===

class TestFullPipeline:
    def test_run_full_pipeline_exists(self):
        from aicomic.core.novel_pipeline import run_full_pipeline
        assert callable(run_full_pipeline)

    def test_full_pipeline_returns_dict(self):
        from aicomic.core.novel_pipeline import run_full_pipeline
        blueprint = {
            "hook": "测试钩子",
            "shots": [{"shot_id": "S01", "visual": "测试画面", "narration": "测试旁白"}],
            "total_shots": 1,
        }
        result = run_full_pipeline(blueprint, template_name="horror")
        assert "blueprint" in result
        assert "shot_plan" in result
        assert "asset_plan" in result
        assert "render_plan" in result


# === ③ 一集→多语言版本 ===

class TestMultilangEpisode:
    def test_build_multilang_episode_exists(self):
        from aicomic.video_synthesis.i18n import build_multilang_episode
        assert callable(build_multilang_episode)

    def test_returns_per_language_plan(self, tmp_path):
        from aicomic.video_synthesis.i18n import build_multilang_episode
        zh_srt = tmp_path / "zh.srt"
        zh_srt.write_text("1\n00:00:00,000 --> 00:00:03,000\n夜里不能回头\n")
        result = build_multilang_episode(
            zh_srt_path=zh_srt,
            output_dir=tmp_path / "multilang",
            languages=["en", "ja"],
        )
        assert "en" in result
        assert "ja" in result
        for lang, plan in result.items():
            assert "subtitle_path" in plan
            assert "tts_voice" in plan


# === ⑤ 多机推理 ===

class TestRemoteGPU:
    def test_remote_gpu_dispatch_exists(self):
        from aicomic.providers.cloud_mode import remote_gpu_dispatch
        assert callable(remote_gpu_dispatch)

    def test_dispatch_to_remote(self):
        from aicomic.providers.cloud_mode import remote_gpu_dispatch
        result = remote_gpu_dispatch(
            prompt="a horror scene",
            comfyui_urls=["http://gpu1:8188", "http://gpu2:8188"],
        )
        assert "assigned_url" in result
        assert "prompt" in result
        assert result["assigned_url"] in ["http://gpu1:8188", "http://gpu2:8188"]

    def test_dispatch_round_robin(self):
        from aicomic.providers.cloud_mode import remote_gpu_dispatch
        urls = ["http://gpu1:8188", "http://gpu2:8188", "http://gpu3:8188"]
        assigned = set()
        for i in range(6):
            r = remote_gpu_dispatch(prompt=f"scene {i}", comfyui_urls=urls)
            assigned.add(r["assigned_url"])
        # Should use at least 2 different GPUs
        assert len(assigned) >= 2
