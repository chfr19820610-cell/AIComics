from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from aicomic.characters.database import (
    _row_to_dict,
    connect_character_database,
    ensure_character_schema,
    get_character_by_id,
    get_project_characters,
    insert_character,
    list_characters,
    update_character,
)
from aicomic.characters.models import (
    Character,
    CharacterCreateRequest,
    CharacterUpdateRequest,
    now_utc_iso,
)
from aicomic.characters.prompt_injector import (
    build_character_context_block,
    build_enriched_prompt_for_shot,
    enhance_image_prompt,
    inject_character_descriptions,
    validate_character_prompt_integrity,
)
from aicomic.characters.script_parser import (
    CHARACTER_TAG_PATTERN,
    extract_character_tags,
    extract_characters_from_manifest,
    extract_characters_with_visuals,
)
from aicomic.characters.service import CharacterService


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def char_db(tmp_path: Path):
    """Create a fresh character database in a temp dir."""
    db_path = tmp_path / "test_characters.db"
    conn = connect_character_database(db_path)
    ensure_character_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_character_dict() -> dict[str, Any]:
    """A sample character record dict."""
    now = now_utc_iso()
    return {
        "id": str(uuid.uuid4()),
        "name": "女主",
        "description": "20岁出头，黑长直发，淡蓝色丝巾，白色衬衫配深灰色包臀裙",
        "gender": "女",
        "age_group": "青年",
        "tags": ["主角", "女性"],
        "project_id": "test_project_001",
        "reference_prompt": "20岁出头女性，黑长直发，淡蓝色丝巾，白色衬衫，深灰色包臀裙，学生气未脱",
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture
def sample_char_service(tmp_path: Path) -> CharacterService:
    """Create a CharacterService backed by a temp dir."""
    return CharacterService(state_dir=tmp_path)


@pytest.fixture
def sample_manifest() -> dict[str, Any]:
    """A minimal episode manifest for parser tests."""
    return {
        "project_id": "test_project_001",
        "season": 1,
        "episodes": [
            {
                "episode_code": "E01",
                "title": "第一集",
                "shots": [
                    {
                        "shot_id": "S01",
                        "scene": "办公室",
                        "characters": ["女主", "反派主管"],
                        "visual": "女主站在办公桌前，反派主管双手抱胸站在对面",
                        "action": "对峙",
                        "emotion": "紧张",
                        "camera": "中景",
                        "ai_video": False,
                    },
                    {
                        "shot_id": "S02",
                        "scene": "会议室",
                        "characters": ["女主", "男主"],
                        "visual": "男主推门而入，女主惊讶抬头",
                        "action": "推门走入",
                        "emotion": "反转",
                        "camera": "低角度",
                        "ai_video": True,
                    },
                ],
            },
            {
                "episode_code": "E02",
                "title": "第二集",
                "shots": [
                    {
                        "shot_id": "S01",
                        "scene": "走廊",
                        "characters": ["女主", "反派主管"],
                        "visual": "两人在走廊相遇",
                        "action": "擦肩而过",
                        "emotion": "冷漠",
                        "camera": "侧拍",
                        "ai_video": False,
                    },
                ],
            },
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# Tests: Database layer
# ═══════════════════════════════════════════════════════════════════════


class TestCharacterDatabase:
    def test_ensure_schema_creates_tables(self, char_db):
        """Verify all character tables exist after schema initialization."""
        cursor = char_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "characters" in tables
        assert "reference_images" in tables
        assert "lora_models" in tables
        assert "project_characters" in tables

    def test_insert_and_get_character(self, char_db, sample_character_dict):
        """Insert a character and retrieve it by id."""
        insert_character(char_db, sample_character_dict)
        fetched = get_character_by_id(char_db, sample_character_dict["id"])
        assert fetched is not None
        assert fetched["name"] == "女主"
        assert fetched["gender"] == "女"
        assert fetched["tags"] == ["主角", "女性"]

    def test_get_missing_character(self, char_db):
        """Getting a non-existent character returns None."""
        assert get_character_by_id(char_db, "nonexistent") is None

    def test_update_character(self, char_db, sample_character_dict):
        """Update a character's fields."""
        insert_character(char_db, sample_character_dict)
        updates = {
            "name": "女主角",
            "reference_prompt": "Updated prompt",
            "updated_at": now_utc_iso(),
        }
        result = update_character(char_db, sample_character_dict["id"], updates)
        assert result is True

        fetched = get_character_by_id(char_db, sample_character_dict["id"])
        assert fetched is not None
        assert fetched["name"] == "女主角"
        assert fetched["reference_prompt"] == "Updated prompt"

    def test_update_nonexistent_character(self, char_db):
        """Updating a non-existent character returns False."""
        updates = {"name": "NewName", "updated_at": now_utc_iso()}
        result = update_character(char_db, "nonexistent", updates)
        assert result is False

    def test_list_characters(self, char_db, sample_character_dict):
        """List characters with and without filters."""
        insert_character(char_db, sample_character_dict)

        # All
        all_chars = list_characters(char_db)
        assert len(all_chars) >= 1

        # By project
        project_chars = list_characters(char_db, project_id="test_project_001")
        assert len(project_chars) == 1

        # By non-matching project
        empty = list_characters(char_db, project_id="nonexistent")
        assert len(empty) == 0

    def test_list_characters_with_tag(self, char_db, sample_character_dict):
        """Filter characters by tag substring."""
        insert_character(char_db, sample_character_dict)
        tagged = list_characters(char_db, tag="主角")
        assert len(tagged) == 1

        no_match = list_characters(char_db, tag="反派")
        assert len(no_match) == 0

    def test_project_characters_link(self, char_db, sample_character_dict):
        """Link a character to a project and retrieve it."""
        insert_character(char_db, sample_character_dict)
        char_db.execute(
            "INSERT INTO project_characters (project_id, character_id, role_tag) VALUES (?, ?, ?)",
            ("test_project_001", sample_character_dict["id"], "女主"),
        )
        char_db.commit()

        linked = get_project_characters(char_db, "test_project_001")
        assert len(linked) == 1
        assert linked[0]["name"] == "女主"
        assert linked[0]["role_tag"] == "女主"

    def test_delete_character(self, char_db, sample_character_dict):
        """Delete a character and verify it's gone."""
        insert_character(char_db, sample_character_dict)
        char_id = sample_character_dict["id"]

        from aicomic.characters.database import delete_character
        assert delete_character(char_db, char_id) is True
        assert get_character_by_id(char_db, char_id) is None

    def test_delete_nonexistent(self, char_db):
        """Deleting a non-existent character returns False."""
        from aicomic.characters.database import delete_character
        assert delete_character(char_db, "nonexistent") is False


# ═══════════════════════════════════════════════════════════════════════
# Tests: Service layer
# ═══════════════════════════════════════════════════════════════════════


class TestCharacterService:
    def test_create_character(self, sample_char_service):
        """Create a character via service layer."""
        request = CharacterCreateRequest(
            name="测试角色",
            description="测试描述",
            gender="男",
            age_group="青年",
            tags=["测试", "男配"],
            project_id="proj_001",
            reference_prompt="一个测试角色 prompt",
        )
        char = sample_char_service.create_character(request)
        assert char.name == "测试角色"
        assert char.gender == "男"
        assert char.tags == ["测试", "男配"]
        assert char.id is not None

    def test_get_character(self, sample_char_service):
        """Retrieve a character by id."""
        request = CharacterCreateRequest(name="小红")
        created = sample_char_service.create_character(request)
        fetched = sample_char_service.get_character(created.id)
        assert fetched is not None
        assert fetched.name == "小红"

    def test_get_nonexistent(self, sample_char_service):
        """Getting a non-existent character returns None."""
        assert sample_char_service.get_character("nonexistent") is None

    def test_update_character(self, sample_char_service):
        """Update a character through the service."""
        created = sample_char_service.create_character(
            CharacterCreateRequest(name="原名", description="原描述")
        )
        updated = sample_char_service.update_character(
            created.id,
            CharacterUpdateRequest(name="新名", description="新描述"),
        )
        assert updated is not None
        assert updated.name == "新名"
        assert updated.description == "新描述"

    def test_delete_character(self, sample_char_service):
        """Delete a character through the service."""
        created = sample_char_service.create_character(
            CharacterCreateRequest(name="待删除")
        )
        assert sample_char_service.delete_character(created.id) is True
        assert sample_char_service.get_character(created.id) is None
        # Second delete should return False
        assert sample_char_service.delete_character(created.id) is False

    def test_list_and_count(self, sample_char_service):
        """List and count characters."""
        sample_char_service.create_character(
            CharacterCreateRequest(name="角色A", project_id="p1")
        )
        sample_char_service.create_character(
            CharacterCreateRequest(name="角色B", project_id="p1")
        )
        sample_char_service.create_character(
            CharacterCreateRequest(name="角色C", project_id="p2")
        )

        assert sample_char_service.count_characters() == 3
        assert sample_char_service.count_characters(project_id="p1") == 2
        assert len(sample_char_service.list_characters(project_id="p1")) == 2
        assert len(sample_char_service.list_characters(project_id="p2")) == 1

    def test_search_characters(self, sample_char_service):
        """Search characters by name, description, or tags."""
        sample_char_service.create_character(
            CharacterCreateRequest(
                name="男主角",
                description="英俊潇洒",
                tags=["主角", "男"],
            )
        )
        sample_char_service.create_character(
            CharacterCreateRequest(
                name="女主角",
                description="美丽大方",
                tags=["主角", "女"],
            )
        )

        results = sample_char_service.search_characters("男主")
        assert len(results) == 1
        assert results[0].name == "男主角"

        results = sample_char_service.search_characters("主角")
        assert len(results) == 2

        results = sample_char_service.search_characters("美丽")
        assert len(results) == 1
        assert results[0].name == "女主角"

    def test_character_response_shape(self, sample_char_service):
        """Verify the response dict has the expected fields."""
        created = sample_char_service.create_character(
            CharacterCreateRequest(name="形状测试", tags=["a", "b"])
        )
        resp = created.to_response()
        data = resp.model_dump()
        assert "id" in data
        assert "name" in data
        assert "tags" in data
        assert data["tags"] == ["a", "b"]
        assert "created_at" in data
        assert "updated_at" in data


# ═══════════════════════════════════════════════════════════════════════
# Tests: Script Parser
# ═══════════════════════════════════════════════════════════════════════


class TestScriptParser:
    def test_extract_character_tags_plain(self):
        """Extract [角色名] tags from text."""
        text = "在[女主]和[反派主管]的对峙中"
        tags = extract_character_tags(text)
        assert len(tags) == 2
        assert tags[0]["name"] == "女主"
        assert tags[1]["name"] == "反派主管"

    def test_extract_character_tags_with_alias(self):
        """Extract [角色名:别名] tags."""
        text = "[男主:总裁]推门而入"
        tags = extract_character_tags(text)
        assert len(tags) == 1
        assert tags[0]["name"] == "男主"
        assert tags[0]["alias"] == "总裁"

    def test_extract_character_tags_no_match(self):
        """Text without tags returns empty list."""
        assert extract_character_tags("普通文本") == []

    def test_extract_character_tags_empty(self):
        """Empty string returns empty list."""
        assert extract_character_tags("") == []

    def test_extract_characters_from_manifest(self, sample_manifest):
        """Extract unique character names from the manifest."""
        chars = extract_characters_from_manifest(sample_manifest)
        names = {c["name"] for c in chars}
        assert "女主" in names
        assert "反派主管" in names
        assert "男主" in names
        assert len(chars) == 3  # 3 unique characters across all shots

    def test_extract_characters_with_visuals(self, sample_manifest):
        """Extract characters with their visual descriptions."""
        chars = extract_characters_with_visuals(sample_manifest)
        char_map = {c["name"]: c for c in chars}

        assert "女主" in char_map
        assert len(char_map["女主"]["episodes"]) == 2  # appears in E01 and E02
        assert char_map["女主"]["best_visual"] != ""

        assert "男主" in char_map
        assert len(char_map["男主"]["visual_contexts"]) == 1

    def test_character_tag_pattern(self):
        """Verify the compiled regex matches correctly."""
        assert CHARACTER_TAG_PATTERN.findall("[女主]") == [("女主", "")]
        assert CHARACTER_TAG_PATTERN.findall("[男主:总裁]") == [("男主", "总裁")]
        assert CHARACTER_TAG_PATTERN.findall("没有标签") == []


# ═══════════════════════════════════════════════════════════════════════
# Tests: Prompt Injector
# ═══════════════════════════════════════════════════════════════════════


class TestPromptInjector:
    def test_inject_character_descriptions(self, sample_char_service):
        """Replace [角色名] markers with character descriptions."""
        sample_char_service.create_character(
            CharacterCreateRequest(
                name="女主",
                reference_prompt="20岁女性，黑长直发，白色衬衫",
            )
        )
        sample_char_service.create_character(
            CharacterCreateRequest(
                name="男主",
                reference_prompt="28岁男性，西装修身，气质非凡",
            )
        )

        project_chars = sample_char_service.list_characters()
        prompt = "在[女主]和[男主]的对话中"
        result = inject_character_descriptions(prompt, project_chars)

        assert "[女主]" not in result
        assert "20岁女性，黑长直发，白色衬衫" in result
        assert "28岁男性，西装修身，气质非凡" in result

    def test_inject_unknown_marker_preserved(self, sample_char_service):
        """Unknown [角色名] markers are left unchanged."""
        prompt = "[未知角色]出现了"
        result = inject_character_descriptions(prompt, [])
        assert result == prompt

    def test_build_character_context_block(self, sample_char_service):
        """Build a formatted character context block."""
        sample_char_service.create_character(
            CharacterCreateRequest(
                name="女主",
                reference_prompt="黑长直发，白色衬衫",
                project_id="p1",
            )
        )

        block = build_character_context_block(
            ["女主", "不存在角色"],
            sample_char_service,
            project_id="p1",
        )
        assert "[角色信息]" in block
        assert "女主" in block
        assert "黑长直发" in block
        assert "不存在角色" in block
        assert "未定义" in block

    def test_enhance_image_prompt(self, sample_char_service):
        """End-to-end prompt enhancement with character injection."""
        sample_char_service.create_character(
            CharacterCreateRequest(
                name="女主",
                reference_prompt="年轻女性，黑长发",
                project_id="p1",
            )
        )

        enhanced = enhance_image_prompt(
            "[女主]站在门口",
            ["女主"],
            sample_char_service,
            project_id="p1",
        )
        assert "[角色信息]" in enhanced
        assert "年轻女性" in enhanced

    def test_build_enriched_prompt_for_shot(self, sample_char_service):
        """Build a full enriched prompt from a shot dict."""
        sample_char_service.create_character(
            CharacterCreateRequest(
                name="女主",
                reference_prompt="年轻女性",
                project_id="p1",
            )
        )

        shot = {
            "shot_id": "S01",
            "scene": "办公室",
            "characters": ["女主"],
            "visual": "女主认真工作",
            "action": "打字",
            "emotion": "专注",
        }
        enriched = build_enriched_prompt_for_shot(shot, sample_char_service, project_id="p1")
        assert "办公室" in enriched
        assert "女主认真工作" in enriched
        assert "打字" in enriched
        assert "专注" in enriched
        # Character context should be present
        assert "年轻女性" in enriched
        assert "[角色信息]" in enriched

    def test_validate_prompt_integrity(self):
        """Validate prompt integrity checks."""
        # Valid case
        result = validate_character_prompt_integrity(
            "[角色信息]\n- 女主: 描述\n\n场景：办公室",
            original_length=20,
        )
        assert result["valid"] is True

        # Empty prompt
        result = validate_character_prompt_integrity("", original_length=0)
        assert result["valid"] is False

        # Duplicate context blocks
        result = validate_character_prompt_integrity(
            "[角色信息]\n描述\n[角色信息]\n重复",
            original_length=10,
        )
        assert result["valid"] is False

    def test_validate_prompt_too_long(self):
        """Validate that extremely long prompts are flagged."""
        long_prompt = "x" * 6000
        result = validate_character_prompt_integrity(long_prompt, original_length=10)
        assert result["valid"] is False


# ═══════════════════════════════════════════════════════════════════════
# Tests: Model serialization / edge cases
# ═══════════════════════════════════════════════════════════════════════


class TestCharacterModels:
    def test_character_to_dict_roundtrip(self, sample_character_dict):
        """Character dict -> Character model -> dict."""
        char = Character.from_dict(sample_character_dict)
        assert char.name == "女主"
        assert char.tags == ["主角", "女性"]

        as_dict = char.to_dict()
        assert as_dict["name"] == "女主"
        assert as_dict["tags"] == ["主角", "女性"]

    def test_character_from_row(self, char_db, sample_character_dict):
        """Character from DB row -> Character model."""
        insert_character(char_db, sample_character_dict)
        row = char_db.execute(
            "SELECT * FROM characters WHERE id = ?",
            (sample_character_dict["id"],),
        ).fetchone()
        char = Character.from_row(tuple(row))
        assert char.name == "女主"
        assert char.tags == ["主角", "女性"]

    def test_tags_empty_string_handling(self, char_db):
        """Empty tags string should parse to empty list."""
        now = now_utc_iso()
        record = {
            "id": str(uuid.uuid4()),
            "name": "无标签",
            "tags": "",
            "created_at": now,
            "updated_at": now,
        }
        insert_character(char_db, record)
        fetched = get_character_by_id(char_db, record["id"])
        assert fetched is not None
        assert fetched["tags"] == []

    def test_create_request_validation(self):
        """CharacterCreateRequest validates required fields."""
        # Name is required
        with pytest.raises(ValueError):
            CharacterCreateRequest(name="")

        # Valid minimal request
        req = CharacterCreateRequest(name="有效角色")
        assert req.name == "有效角色"
        assert req.description == ""
        assert req.tags == []
