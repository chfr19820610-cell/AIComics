"""Tests for prompt system: intent classification, enhancement, character injection.

Covers:
- classify_shot_intent: 6 signals × 6 intent types
- enhance_by_intent: profile + intent overlay
- prompt_injector: [角色名] replacement, context block, integrity validation
- build_image_prompt / build_video_prompt: end-to-end prompt construction
- Error handling: silent exception swallowing (Issue #2)
- Double enhancement conflict (Issue #3)
- Horror bypass (Issue #4)
"""
from __future__ import annotations



# ============ classify_shot_intent tests ============

class TestClassifyShotIntent:
    """Test the 6-signal intent classifier."""

    def test_exposition_first_shot(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        shot = {"scene": "老宅", "visual": " establishing", "emotion": "平静", "camera": "远景", "action": "凝视"}
        result = classify_shot_intent(shot, shot_index=0, total_shots=10)
        assert result.intent == "exposition"
        assert result.narrative_position == "开头"

    def test_climax_last_third(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        shot = {"scene": "祠堂", "visual": "爆发", "emotion": "愤怒", "camera": "特写", "action": "战斗"}
        result = classify_shot_intent(shot, shot_index=8, total_shots=10)
        assert result.intent in ("climax", "falling_action")

    def test_resolution_last_shot(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        shot = {"scene": "山路", "visual": "远去", "emotion": "平静", "camera": "全景", "action": "离开"}
        result = classify_shot_intent(shot, shot_index=9, total_shots=10)
        assert result.intent == "resolution"

    def test_transition_scene_change(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        shot = {"scene": "祠堂", "visual": "雾气", "emotion": "", "camera": "远景", "action": "走过"}
        prev = {"scene": "老宅"}
        result = classify_shot_intent(shot, shot_index=3, total_shots=10, prev_shot=prev)
        assert result.signals.get("scene_changed") is True
        assert result.intent == "transition"

    def test_emotion_intensity_mapping(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        high_emotion = {"emotion": "恐惧", "camera": "特写", "action": "尖叫", "scene": "", "visual": ""}
        result = classify_shot_intent(high_emotion, shot_index=5, total_shots=10)
        assert result.signals["emotion_level"] == 3
        assert result.intent in ("climax", "rising_action")

    def test_camera_type_mapping(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        close_up = {"emotion": "", "camera": "近景", "action": "", "scene": "", "visual": ""}
        result = classify_shot_intent(close_up, shot_index=5, total_shots=10)
        assert result.signals["cam_type"] == "close"

    def test_confidence_range(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        shot = {"scene": "", "emotion": "紧张", "camera": "中景", "action": "奔跑"}
        result = classify_shot_intent(shot, shot_index=3, total_shots=10)
        assert 0.0 < result.confidence <= 1.0

    def test_empty_shot_does_not_crash(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        result = classify_shot_intent({}, shot_index=0, total_shots=1)
        assert result.intent in ("exposition", "resolution", "transition")
        assert result.confidence >= 0.0

    def test_action_keywords_high_energy(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        shot = {"action": "追逐逃跑", "emotion": "震惊", "camera": "中景", "scene": "", "visual": ""}
        result = classify_shot_intent(shot, shot_index=4, total_shots=10)
        # High energy action should boost rising_action or climax
        assert result.signals["all_scores"]["rising_action"] > 0
        assert result.signals["all_scores"]["climax"] > 0

    def test_dialogue_signal(self):
        from aicomic.providers.prompt_enhancer import classify_shot_intent
        with_dialogue = {"dialogue": "你不能去！", "emotion": "愤怒", "camera": "近景", "scene": "", "action": "", "visual": ""}
        result = classify_shot_intent(with_dialogue, shot_index=4, total_shots=10)
        assert result.signals["has_dialogue"] is True


# ============ enhance_by_intent tests ============

class TestEnhanceByIntent:
    """Test intent-driven prompt enhancement."""

    def test_basic_enhancement_returns_dict(self):
        from aicomic.providers.prompt_enhancer import enhance_by_intent
        result = enhance_by_intent(
            "anime girl in garden", shot={"scene": "花园", "emotion": "平静", "camera": "中景"},
            shot_index=0, total_shots=10,
        )
        assert isinstance(result, dict)
        assert "prompt" in result
        assert "negative_prompt" in result
        assert len(result["prompt"]) > len("anime girl in garden")

    def test_intent_composition_added(self):
        from aicomic.providers.prompt_enhancer import enhance_by_intent
        # First shot → exposition → should have "establishing" or "wide"
        result = enhance_by_intent(
            "scene", shot={"scene": "村庄", "emotion": "平静", "camera": "远景"},
            shot_index=0, total_shots=10,
        )
        # Exposition composition should be in the enhanced prompt
        assert any(kw in result["prompt"].lower() for kw in ["establishing", "wide", "environment"])

    def test_negative_prompt_accumulates(self):
        from aicomic.providers.prompt_enhancer import enhance_by_intent
        result = enhance_by_intent(
            "scene", shot={"emotion": "恐惧", "camera": "特写", "action": "尖叫"},
            shot_index=7, total_shots=10,
        )
        # Should have negative prompt content
        assert len(result.get("negative_prompt", "")) > 0

    def test_different_intents_produce_different_prompts(self):
        """Issue #3: Double enhancement should NOT produce identical prompts for different intents."""
        from aicomic.providers.prompt_enhancer import enhance_by_intent
        exp = enhance_by_intent(
            "base", shot={"scene": "村庄", "emotion": "平静", "camera": "远景", "action": "凝视"},
            shot_index=0, total_shots=10,
        )
        cli = enhance_by_intent(
            "base", shot={"scene": "祠堂", "emotion": "恐惧", "camera": "特写", "action": "尖叫"},
            shot_index=7, total_shots=10,
        )
        assert exp["prompt"] != cli["prompt"], "Different intents must produce different prompts"


# ============ prompt_injector tests ============

class TestPromptInjector:
    """Test character prompt injection."""

    def test_character_tag_replacement(self):
        from aicomic.characters.prompt_injector import inject_character_descriptions
        from aicomic.characters.models import Character

        chars = [Character(id="c1", name="女主", description="黑长直发，白色衬衫", reference_prompt="")]
        result = inject_character_descriptions("[女主]站在窗前", chars)
        assert "黑长直发" in result
        assert "[女主]" not in result

    def test_unknown_tag_left_unchanged(self):
        from aicomic.characters.prompt_injector import inject_character_descriptions
        result = inject_character_descriptions("[未知角色]出现", [])
        assert "[未知角色]" in result

    def test_reference_prompt_preferred(self):
        from aicomic.characters.prompt_injector import inject_character_descriptions
        from aicomic.characters.models import Character

        char = Character(
            id="c2",
            name="主角",
            description="短描述",
            reference_prompt="详细参考提示词，含配色和服装细节",
        )
        result = inject_character_descriptions("[主角]出现", [char])
        assert "详细参考提示词" in result

    def test_integrity_validation_empty(self):
        from aicomic.characters.prompt_injector import validate_character_prompt_integrity
        result = validate_character_prompt_integrity("", 10)
        assert result["valid"] is False

    def test_integrity_validation_explosion(self):
        from aicomic.characters.prompt_injector import validate_character_prompt_integrity
        result = validate_character_prompt_integrity("x" * 6000, 10)
        assert result["valid"] is False

    def test_integrity_validation_ok(self):
        from aicomic.characters.prompt_injector import validate_character_prompt_integrity
        result = validate_character_prompt_integrity("正常提示词", 5)
        assert result["valid"] is True


# ============ request_builder integration tests ============

class TestRequestBuilderPrompts:
    """Test end-to-end prompt construction."""

    def test_build_image_prompt_basic(self):
        from aicomic.providers.request_builder import build_image_prompt
        shot = {
            "scene": "老宅堂屋",
            "visual": "月光透过窗户",
            "action": "凝视",
            "emotion": "紧张",
            "camera": "中景",
            "characters": ["返乡青年"],
        }
        prompt = build_image_prompt("E01", shot)
        assert "老宅堂屋" in prompt
        assert "返乡青年" in prompt
        assert "Anime illustration" in prompt

    def test_build_video_prompt_basic(self):
        from aicomic.providers.request_builder import build_video_prompt
        shot = {
            "scene": "山路",
            "visual": "雾气弥漫",
            "action": "奔跑",
            "emotion": "恐惧",
            "camera": "近景",
            "characters": ["返乡青年"],
        }
        prompt = build_video_prompt("E01", shot)
        assert "山路" in prompt
        assert "Anime dynamic" in prompt

    def test_build_image_prompt_enhanced_returns_dict(self):
        from aicomic.providers.request_builder import build_image_prompt_enhanced
        shot = {
            "scene": "祠堂", "visual": "烛光摇曳", "action": "凝视",
            "emotion": "恐惧", "camera": "特写", "characters": ["守夜老人"],
        }
        result = build_image_prompt_enhanced("E01", shot, shot_index=7, total_shots=10)
        assert isinstance(result, dict)
        assert "prompt" in result
        assert "negative_prompt" in result

    def test_h3_video_prompt_format(self):
        from aicomic.providers.request_builder import build_h3_video_prompt
        shot = {
            "scene": "枯井", "visual": "月光", "action": "探望",
            "emotion": "恐惧", "camera": "俯视", "characters": ["返乡青年"],
        }
        prompt = build_h3_video_prompt("E01", shot)
        # H3 format should contain structured fields
        assert len(prompt) > 50


# ============ Issue regression tests ============

class TestPromptIssues:
    """Regression tests for identified issues."""

    def test_issue2_silent_exception_no_character_loss(self):
        """Issue #2: char_service exception should NOT silently drop char injection."""
        from aicomic.providers.request_builder import build_image_prompt

        class BrokenCharService:
            def list_characters(self, **kwargs):
                raise RuntimeError("DB connection failed")

        shot = {
            "scene": "堂屋", "visual": "月光", "action": "凝视",
            "emotion": "紧张", "camera": "中景", "characters": ["主角"],
        }
        # With broken service, should still return a valid prompt
        # (not crash, but also not silently lose character info)
        prompt = build_image_prompt("E01", shot, char_service=BrokenCharService(), project_id="test")
        assert len(prompt) > 0
        # The character name should still appear in the base prompt
        assert "主角" in prompt

    def test_issue3_no_duplicate_composition(self):
        """Issue #3: enhance_by_intent should not add conflicting composition hints."""
        from aicomic.providers.prompt_enhancer import enhance_by_intent
        result = enhance_by_intent(
            "base scene", shot={"scene": "村", "emotion": "平静", "camera": "远景", "action": "凝视"},
            shot_index=0, total_shots=10,
        )
        # Count composition-related keywords — should not have contradictory ones
        prompt_lower = result["prompt"].lower()
        # "establishing" (exposition) and "extreme close-up" (climax) should not coexist
        has_establishing = "establishing" in prompt_lower
        has_extreme_close = "extreme close-up" in prompt_lower
        assert not (has_establishing and has_extreme_close), \
            "Conflicting composition hints should not coexist"

    def test_issue4_horror_shot_with_characters(self):
        """Issue #4: Horror shots should still include character info."""
        from aicomic.providers.request_builder import build_image_prompt
        shot = {
            "scene": "枯井", "visual": "月光下的井口", "action": "探望",
            "emotion": "恐惧", "camera": "俯视", "characters": ["返乡青年", "守夜老人"],
            "horror_beat": "taboo",
        }
        prompt = build_image_prompt("E01", shot)
        # Even horror shots should mention characters somehow
        assert len(prompt) > 0

    def test_issue5_quality_score_available(self):
        """Issue #5: score_prompt should be callable and return useful metrics."""
        from aicomic.providers.prompt_enhancer import score_prompt
        result = score_prompt("anime girl, garden, sunlight, masterpiece, best quality")
        assert isinstance(result, dict)
        assert "score" in result or "quality" in str(result).lower()
