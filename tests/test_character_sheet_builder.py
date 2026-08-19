#!/usr/bin/env python3
"""test_character_sheet_builder.py — 角色设定图生成器验证测试

验证:
  1. 预设模板生成正确(prompt/negative_prompt/layout/aspect)
  2. 结构化角色(CharacterAppearance)10+维度全覆盖
  3. 风格适配(anime_donghua/realistic_cn/horror_folk)切换正确
  4. build_sheet_from_character桥接Character对象
  5. generate_character_sheet_prompt桥接CharacterService
  6. 镜头意图分类器无回归
  7. 边界case:空字段/超长描述/未知风格
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from aicomic.characters.character_sheet_builder import (
    build_character_sheet_prompt,
    build_from_preset,
    CharacterAppearance,
    build_sheet_from_character,
    PRESETS,
)
from aicomic.characters.prompt_injector import generate_character_sheet_prompt
from aicomic.providers.prompt_enhancer import classify_shot_intent, enhance_by_intent


# ═══ Fixtures ═══

@pytest.fixture
def ancient_hero_appearance() -> CharacterAppearance:
    return CharacterAppearance(
        name="古风帅哥",
        gender="男",
        age_group="青年",
        body_type="高挑修长",
        face_shape="瓜子脸",
        eyes="狭长双眼，眼尾细长上挑",
        skin="清透瓷白肌肤",
        hairstyle="长发微卷凌乱，发丝拂面",
        hair_color="墨黑",
        hair_accessory="金质华丽发冠",
        outfit="锦衣华服貂裘",
        outfit_details="丰富的暗纹，金丝描边，宽袖广带",
        outfit_color="玄色底金纹",
        accessories="腰间玉佩，金丝绶带",
        temperament="疯批感，阴郁感，潇洒",
        aura="有柔和感情的眼神",
        signature_features=["左眼下方泪痣"],
    )


# ═══ 1. 预设模板 ═══

class TestPresets:
    def test_ancient_hero_preset(self) -> None:
        r = build_from_preset("ancient_hero")
        assert "prompt" in r and "negative_prompt" in r
        assert "turnaround sheet" in r["prompt"]
        assert "古风帅哥" in r["prompt"]
        assert "WHITE BACKGROUND" in r["prompt"]
        assert "inconsistent proportions" in r["negative_prompt"]
        assert "7-zone" in r["layout"]
        assert r["aspect_ratio"] == "16:9"

    def test_anime_girl_preset(self) -> None:
        r = build_from_preset("anime_girl")
        assert "prompt" in r
        assert "turnaround sheet" in r["prompt"]
        assert "少女" in r["prompt"]
        assert "anime" in r["prompt"].lower()

    def test_horror_ghost_preset(self) -> None:
        r = build_from_preset("horror_ghost")
        assert "prompt" in r
        assert "turnaround sheet" in r["prompt"]
        assert "horror" in r["prompt"].lower() or "恐怖" in r["prompt"]

    def test_unknown_preset_fallback(self) -> None:
        """未知预设不报错, 回退到ancient_hero"""
        r = build_from_preset("nonexistent_preset")
        assert "prompt" in r
        assert len(r["prompt"]) > 100


# ═══ 2. 结构化角色 ═══

class TestCharacterAppearance:
    def test_all_dimensions_in_prompt(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(appearance=ancient_hero_appearance)
        prompt = r["prompt"]
        # 10+维度全部出现在prompt中
        assert "古风帅哥" in prompt  # name
        assert "男" in prompt  # gender
        assert "青年" in prompt  # age_group
        assert "高挑修长" in prompt  # body_type
        assert "瓜子脸" in prompt  # face_shape
        assert "狭长双眼" in prompt  # eyes
        assert "清透瓷白肌肤" in prompt  # skin
        assert "长发微卷凌乱" in prompt  # hair
        assert "墨黑" in prompt  # hair_color
        assert "金质华丽发冠" in prompt  # hair_accessory
        assert "锦衣华服貂裘" in prompt  # outfit
        assert "金丝描边" in prompt  # outfit_details
        assert "玄色底金纹" in prompt  # outfit_color
        assert "腰间玉佩" in prompt  # accessories
        assert "疯批感" in prompt  # temperament
        assert "有柔和感情的眼神" in prompt  # aura
        assert "左眼下方泪痣" in prompt  # signature

    def test_character_desc_built(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(appearance=ancient_hero_appearance)
        desc = r["character_desc"]
        assert "古风帅哥" in desc
        assert "狭长双眼" in desc
        assert "锦衣华服貂裘" in desc

    def test_layout_structure(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(appearance=ancient_hero_appearance)
        prompt = r["prompt"]
        # 7分区结构关键词
        assert "front view" in prompt.lower() or "正面" in prompt
        assert "side view" in prompt.lower() or "侧面" in prompt
        assert "back view" in prompt.lower() or "背面" in prompt
        assert "facial" in prompt.lower() or "面部" in prompt
        assert "Golden" in prompt or "ratio" in prompt.lower()
        assert "detail" in prompt.lower() or "细节" in prompt
        assert "ratio" in prompt.lower() or "比例" in prompt


# ═══ 3. 风格适配 ═══

class TestArtStyles:
    def test_anime_donghua_style(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(appearance=ancient_hero_appearance, art_style="anime_donghua")
        assert "anime" in r["prompt"].lower()

    def test_realistic_cn_style(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(appearance=ancient_hero_appearance, art_style="realistic_cn")
        assert "ultra-realistic" in r["prompt"].lower() or "写实" in r["prompt"]

    def test_horror_folk_style(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(appearance=ancient_hero_appearance, art_style="horror_folk")
        assert "horror" in r["prompt"].lower() or "恐怖" in r["prompt"]

    def test_unknown_style_fallback(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(appearance=ancient_hero_appearance, art_style="nonexistent")
        assert len(r["prompt"]) > 100  # 不报错, 有输出


# ═══ 4. 桥接Character对象 ═══

class TestBuildSheetFromCharacter:
    def test_with_full_character(self) -> None:
        mock_char = MagicMock()
        mock_char.name = "测试角色"
        mock_char.description = "高大威猛的剑客，黑色长袍，银色护甲"
        mock_char.gender = "男"
        mock_char.age_group = "青年"
        mock_char.reference_prompt = ""
        mock_char.tags = []

        r = build_sheet_from_character(mock_char)
        assert "prompt" in r
        assert "测试角色" in r["prompt"]
        assert "高大威猛" in r["prompt"]

    def test_with_empty_description(self) -> None:
        mock_char = MagicMock()
        mock_char.name = "空角色"
        mock_char.description = ""
        mock_char.gender = ""
        mock_char.age_group = ""
        mock_char.reference_prompt = ""
        mock_char.tags = []

        r = build_sheet_from_character(mock_char)
        assert "prompt" in r
        assert "空角色" in r["prompt"]


# ═══ 5. 桥接CharacterService ═══

class TestGenerateFromService:
    def test_normal_character(self) -> None:
        mock_service = MagicMock()
        mock_char = MagicMock()
        mock_char.name = "测试"
        mock_char.description = "短发少女，蓝色裙子"
        mock_char.gender = "女"
        mock_char.age_group = "少女"
        mock_char.reference_prompt = ""
        mock_char.tags = []
        mock_service.get_character.return_value = mock_char

        r = generate_character_sheet_prompt(mock_service, "char-001")
        assert "prompt" in r
        assert "测试" in r["prompt"]
        assert "短发少女" in r["prompt"]

    def test_nonexistent_character(self) -> None:
        mock_service = MagicMock()
        mock_service.get_character.return_value = None

        r = generate_character_sheet_prompt(mock_service, "nonexistent-id")
        assert "error" in r
        assert r["prompt"] == ""


# ═══ 6. 镜头意图分类器无回归 ═══

class TestShotIntentNoRegression:
    def test_exposition(self) -> None:
        shot = {"scene": "村庄", "emotion": "平静", "camera": "远景", "action": "静立"}
        r = classify_shot_intent(shot, 0, 8)
        assert r.intent == "exposition"

    def test_climax(self) -> None:
        shot = {"scene": "悬崖", "emotion": "恐惧", "camera": "大特写", "action": "尖叫"}
        r = classify_shot_intent(shot, 6, 8)
        assert r.intent == "climax"

    def test_transition(self) -> None:
        shot = {"scene": "山路→山洞", "emotion": "紧张", "camera": "中景", "action": "走入山洞"}
        r = classify_shot_intent(shot, 3, 8)
        # 转场检测: scene中有→
        assert r.intent in ("transition", "rising_action")


# ═══ 7. 边界case ═══

class TestEdgeCases:
    def test_empty_appearance(self) -> None:
        app = CharacterAppearance(name="空")
        r = build_character_sheet_prompt(appearance=app)
        assert "prompt" in r
        assert "空" in r["prompt"]
        assert len(r["prompt"]) > 100

    def test_very_long_description(self) -> None:
        app = CharacterAppearance(
            name="超长描述角色",
            outfit="x" * 500,
        )
        r = build_character_sheet_prompt(appearance=app)
        assert "prompt" in r
        # prompt不应该爆炸
        assert len(r["prompt"]) < 5000

    def test_style_override(self, ancient_hero_appearance: CharacterAppearance) -> None:
        r = build_character_sheet_prompt(
            appearance=ancient_hero_appearance,
            style="赛博朋克风格，霓虹灯光",
        )
        assert "赛博朋克" in r["prompt"] or "霓虹" in r["prompt"]

    def test_enhance_by_intent_still_works(self) -> None:
        """ensure enhance_by_intent (from previous round) still imports and works"""
        shot = {"scene": "村庄", "emotion": "平静", "camera": "远景", "action": "静立"}
        r = enhance_by_intent(
            base_prompt="Anime illustration, scene: 村庄",
            shot=shot,
            shot_index=0,
            total_shots=8,
        )
        assert "prompt" in r
        assert len(r["prompt"]) > len("Anime illustration, scene: 村庄")
