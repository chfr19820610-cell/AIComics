"""Phase 3 tests — template→pipeline binding, batch season, language packs, publish orchestration, remote ComfyUI."""
from __future__ import annotations

from pathlib import Path

import pytest


# === ① 模板→管线绑定 ===
from aicomic.core.template_engine import load_template, build_blueprint_from_template


class TestTemplatePipelineBinding:
    def test_init_with_template_populates_project_manifest(self, tmp_path):
        """init-project --template should write template metadata into project_manifest."""
        from aicomic.core.project_initializer import initialize_project
        result = initialize_project(tmp_path, "test_project", "恐怖", "暗黑", template="horror")
        assert result["project_id"]
        import json
        manifest = json.loads((tmp_path / result["project_id"] / "manifests" / "project_manifest.json").read_text())
        assert manifest.get("template") == "horror"

    def test_init_with_template_writes_blueprint(self, tmp_path):
        """init-project --template should also generate episode_blueprint from template."""
        from aicomic.core.project_initializer import initialize_project
        result = initialize_project(tmp_path, "test_project2", "悬疑", "冷峻", template="mystery")
        import json
        bp_path = tmp_path / result["project_id"] / "docs" / "episode_blueprint.json"
        assert bp_path.exists()
        bp = json.loads(bp_path.read_text())
        # Blueprint should have acts from mystery template
        assert len(bp.get("acts", [])) == 5

    def test_init_without_template_works_as_before(self, tmp_path):
        """Backward compat: init-project without --template still works."""
        from aicomic.core.project_initializer import initialize_project
        result = initialize_project(tmp_path, "test_project3", "爱情", "温暖")
        assert result["project_id"]


# === ② 批量编排 ===
from aicomic.core.novel_pipeline import build_season_production_plan, generate_episode_plan


class TestBatchSeasonOrchestration:
    def test_batch_plan_generates_all_episodes(self):
        episodes = [
            {"episode_code": f"E{i:02d}", "shot_count": 8, "blueprint": {
                "acts": [{"act_id": "A1", "title": "x", "beat": "x", "shot_count": 8}],
                "characters": [{"name": "主角", "role": "x", "visual_rule": "x"}],
                "locations": ["场景"],
                "visual_motifs": [],
                "emotion_map": {},
            }}
            for i in range(1, 13)
        ]
        plan = build_season_production_plan(episodes, template_name="workplace")
        assert plan["episode_count"] == 12
        assert plan["total_shots"] == 96  # 12 * 8

    def test_batch_plan_has_production_order(self):
        episodes = [{"episode_code": "E01", "shot_count": 5, "blueprint": {"acts": [], "characters": [], "locations": [], "visual_motifs": [], "emotion_map": {}}}]
        plan = build_season_production_plan(episodes, template_name="workplace")
        assert "production_order" in plan or "episode_plans" in plan


# === ③ 语言包管理 ===
from aicomic.video_synthesis.i18n import build_multilang_subtitle_set, get_voice_for_language


class TestLanguagePackManagement:
    def test_language_pack_generates_all_versions(self, tmp_path):
        # Write a simple zh SRT file
        srt_content = "1\n00:00:00,000 --> 00:00:03,000\n夜里不能回头\n\n2\n00:00:03,000 --> 00:00:06,000\n井口有声音\n"
        zh_srt = tmp_path / "zh.srt"
        zh_srt.write_text(srt_content, encoding="utf-8")
        result = build_multilang_subtitle_set(zh_srt, tmp_path, languages=["en", "ja", "ko"])
        assert "zh" in result  # original
        assert "en" in result
        assert "ja" in result
        assert "ko" in result
        for lang, path in result.items():
            assert Path(path).exists()

    def test_language_pack_voices_mapped(self):
        for lang in ["zh", "en", "ja", "ko"]:
            voice = get_voice_for_language(lang)
            assert voice  # non-empty


# === ④ 发布编排 ===
from aicomic.publish.domestic_publisher import PublishPayload
from aicomic.publish.youtube_publisher import YouTubePayload


class TestPublishOrchestration:
    def test_multi_platform_payloads_from_pack(self):
        from pathlib import Path
        pack = {
            "titles": {"main": "测试标题"},
            "description": "测试描述",
            "tags": ["标签1"],
            "platform_copy": {
                "douyin": {"title": "抖音标题", "description": "抖音描述", "tags": ["抖音标签"]},
                "youtube": {"title": "YT标题", "description": "YT描述", "tags": ["yt_tag"]},
            }
        }
        dom = PublishPayload.from_publish_pack(pack, Path("/tmp/v.mp4"))
        yt = YouTubePayload.from_publish_pack(pack, "/tmp/v.mp4")
        assert dom.title == "抖音标题"
        assert yt.title == "YT标题"
        assert dom.title != yt.title  # platform-specific

    def test_publish_adapter_preserves_common_fields(self):
        from pathlib import Path
        pack = {"titles": {"main": "通用"}, "description": "通用描述", "tags": ["t"]}
        dom = PublishPayload.from_publish_pack(pack, Path("/tmp/v.mp4"))
        yt = YouTubePayload.from_publish_pack(pack, "/tmp/v.mp4")
        assert dom.description == "通用描述"
        assert yt.description == "通用描述"


# === ⑤ 远程 ComfyUI ===
from aicomic.providers.cloud_mode import apply_cloud_mode, is_cloud_mode


class TestRemoteComfyUI:
    def test_remote_comfyui_config_detected(self):
        """Config with remote_url should be recognized as remote ComfyUI."""
        from aicomic.providers.cloud_mode import filter_cloud_providers
        providers = ["local_comfyui_image", "remote_comfyui", "openai_image"]
        filtered = filter_cloud_providers(providers)
        assert "local_comfyui_image" not in filtered
        assert "remote_comfyui" in filtered  # remote_* stays
        assert "openai_image" in filtered

    def test_apply_cloud_with_remote(self):
        config = {
            "image_providers": {"default": "local_comfyui_image", "available": ["local_comfyui_image", "remote_comfyui", "openai_image"]},
            "video_providers": {"default": "local_comfyui_video", "available": ["local_comfyui_video", "remote_comfyui", "seedance"]},
            "tts_providers": {"default": "openai_tts", "available": ["openai_tts", "local_piper_tts"]},
        }
        result = apply_cloud_mode(config)
        assert "local_" not in result["image_providers"]["default"]
        assert "local_" not in result["video_providers"]["default"]
        # remote_comfyui should survive
        assert "remote_comfyui" in result["image_providers"]["available"]
