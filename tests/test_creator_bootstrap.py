from __future__ import annotations

from aicomic.core.creator_bootstrap import (
    build_character_bible,
    build_creator_profile,
    build_episode_blueprint,
    build_prompt_pack_template,
    build_release_checklist_markdown,
    build_story_bible,
    build_style_bible,
)


class TestBuildCreatorProfile:
    def test_builds_profile(self) -> None:
        profile = build_creator_profile(
            project_name="测试项目",
            genre="horror",
            style="写实",
            logline="主角在恐怖世界中生存",
            protagonist_name="小明",
            target_audience="18-35",
            tone="紧张",
            season_hook="每集死一个人",
            episode_target_count=12,
        )
        assert profile["project_name"] == "测试项目"
        assert profile["genre"] == "horror"
        assert profile["working_mode"] == "creator_single_user"
        assert profile["episode_target_count"] == 12
        assert "pipeline_steps" in profile

    def test_minimal_profile(self) -> None:
        profile = build_creator_profile(
            project_name="P", genre="g", style="s", logline="l",
            protagonist_name="小明", target_audience="18-35",
            tone="t", season_hook="h", episode_target_count=1,
        )
        assert profile["episode_target_count"] == 1


class TestBuildStoryBible:
    def test_builds_bible(self) -> None:
        bible = build_story_bible("P", "horror", "logline", "小明", "紧张", "钩子")
        assert bible["project_name"] == "P"
        assert bible["concept_logline"] == "logline"
        assert isinstance(bible["world_rules"], list)
        assert isinstance(bible["narrative_beats"], list)

    def test_empty_values(self) -> None:
        bible = build_story_bible("", "", "", "", "", "")
        assert bible["tone_keywords"] == ["强钩子", "情绪反转", "短剧节奏"]


class TestBuildCharacterBible:
    def test_builds_with_protagonist(self) -> None:
        bible = build_character_bible("小明")
        characters = bible["characters"]
        assert len(characters) == 3
        assert characters[0]["name"] == "小明"
        assert characters[0]["role"] == "主角"

    def test_all_have_voices(self) -> None:
        bible = build_character_bible("Tom")
        for c in bible["characters"]:
            assert "voice_notes" in c


class TestBuildStyleBible:
    def test_builds_style_bible(self) -> None:
        style = build_style_bible("写实", "紧张")
        assert style["style_profile"] == "写实"
        assert style["aspect_ratio"] == "9:16"
        assert "visual_direction" in style
        assert "asset_strategy" in style

    def test_asset_strategy_has_keys(self) -> None:
        style = build_style_bible("s", "t")
        assert "image" in style["asset_strategy"]
        assert "video" in style["asset_strategy"]
        assert "tts" in style["asset_strategy"]


class TestBuildEpisodeBlueprint:
    def test_builds_blueprint(self) -> None:
        bp = build_episode_blueprint(12, "小明", "钩子")
        assert bp["episode_target_count"] == 12
        assert len(bp["episodes"]) == 12
        assert len(bp["arcs"]) == 4  # ceil(12/3) = 4

    def test_clamps_to_max_24(self) -> None:
        bp = build_episode_blueprint(100, "小明", "钩子")
        assert bp["episode_target_count"] == 24

    def test_minimum_1(self) -> None:
        bp = build_episode_blueprint(0, "小明", "钩子")
        assert bp["episode_target_count"] == 1

    def test_first_episode_seeded(self) -> None:
        bp = build_episode_blueprint(3, "小明", "钩子")
        assert bp["episodes"][0]["status"] == "seeded"
        assert bp["episodes"][1]["status"] == "planned"


class TestBuildPromptPackTemplate:
    def test_builds_template(self) -> None:
        tpl = build_prompt_pack_template("P", "horror", "写实", "小明", "紧张")
        assert "image_prompt_template" in tpl
        assert "video_prompt_template" in tpl
        assert "tts_prompt_template" in tpl
        assert "subtitle_rule" in tpl

    def test_template_contains_project_name(self) -> None:
        tpl = build_prompt_pack_template("测试项目", "g", "s", "小明", "t")
        # The prompt template is built from style/genre parameters, not project name
        assert "g" in tpl["image_prompt_template"]


class TestBuildReleaseChecklistMarkdown:
    def test_contains_project_name(self) -> None:
        md = build_release_checklist_markdown("测试项目")
        assert "# 测试项目" in md

    def test_contains_checklist_items(self) -> None:
        md = build_release_checklist_markdown("P")
        assert "- [ ]" in md
        assert "世界观" in md
        assert "发布标题" in md
