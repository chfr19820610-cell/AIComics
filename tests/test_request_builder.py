from __future__ import annotations

from pathlib import Path

import pytest

from aicomic.core.models import JobRecord, ProviderRequestRecord
from aicomic.providers.request_builder import (
    ProviderRequestBuildError,
    action_for_beat,
    apply_provider_overrides,
    build_horror_prompt_context,
    build_horror_visual_prompt,
    build_image_prompt,
    build_request_payload,
    build_tts_prompt,
    build_video_prompt,
    extract_request_records,
    index_episode_manifest,
    is_horror_shot,
    parse_shot_id_from_job,
    resolve_endpoint,
    translate_horror_anchor,
    translate_horror_camera,
    translate_horror_emotion,
    translate_horror_scene,
    visual_direction_for_strategy,
    write_provider_requests,
)


SIMPLE_SHOT = {"scene": "村口", "visual": "远景", "action": "走", "emotion": "平静", "camera": "固定", "characters": ["小明"]}
HORROR_SHOT = {"scene": "老宅堂屋", "visual": "暗光", "action": "指", "emotion": "震惊", "camera": "背影",
               "horror_beat": "taboo", "avoidance_strategy": "dark_light", "continuity_anchor": "旧照片",
               "characters": ["阿玲"]}


class TestProviderRequestBuildError:
    def test_message(self) -> None:
        err = ProviderRequestBuildError([{"job_id": "J1", "reason": "missing"}])
        assert "1 个无效" in str(err)
        assert err.skipped_jobs == [{"job_id": "J1", "reason": "missing"}]


class TestIndexEpisodeManifest:
    def test_indexes_episodes(self) -> None:
        manifest = {"episodes": [{"episode_code": "E01", "title": "第一集", "shots": [{"shot_id": "S001"}]}]}
        result = index_episode_manifest(manifest)
        assert "E01" in result
        assert result["E01"]["episode"]["title"] == "第一集"
        assert result["E01"]["shots"]["S001"] == {"shot_id": "S001"}


class TestParseShotIdFromJob:
    @pytest.mark.parametrize("job_id,expected", [
        ("JOB_E01_S001_IMAGE", "S001"),
        ("PREFIX_A01_B002_C003", "B002"),
        ("too_short", ""),
        ("", ""),
    ])
    def test_various(self, job_id: str, expected: str) -> None:
        assert parse_shot_id_from_job(job_id) == expected


class TestResolveEndpoint:
    @pytest.mark.parametrize("provider,expected", [
        ("openai_image", "/v1/images/generations"),
        ("local_comfyui_image", "/local/comfyui/prompt"),
        ("openai_tts", "/v1/audio/speech"),
        ("sora", "/v1/videos"),
        ("local_comfyui_video", "/local/comfyui/video"),
        ("manual_web", "/manual/web-submit"),
        ("windows_tts", "/local/windows-tts"),
        ("local_piper_tts", "/local/piper-tts"),
        ("unknown_provider", "/providers/unknown_provider/image"),
    ])
    def test_resolves(self, provider: str, expected: str) -> None:
        assert resolve_endpoint(provider, "image") == expected


class TestIsHorrorShot:
    @pytest.mark.parametrize("shot,expected", [
        ({"horror_beat": "taboo"}, True),
        ({"horror_beat": ""}, False),
        ({}, False),
    ])
    def test_detects(self, shot: dict, expected: bool) -> None:
        assert is_horror_shot(shot) == expected


class TestBuildImagePrompt:
    def test_normal(self) -> None:
        result = build_image_prompt("测试", {"scene": "森林", "visual": "日出", "action": "奔跑", "emotion": "快乐",
                                              "camera": "远景", "characters": ["小红"]})
        assert "测试" in result
        assert "森林" in result

    def test_horror(self) -> None:
        result = build_image_prompt("恐怖", HORROR_SHOT)
        assert "anime folk horror" in result


class TestBuildVideoPrompt:
    def test_normal(self) -> None:
        result = build_video_prompt("测试", {"scene": "森林", "visual": "日落", "action": "说", "emotion": "悲伤",
                                             "camera": "近景", "characters": []})
        assert "3-4 秒" in result
        assert "日落" in result

    def test_horror(self) -> None:
        result = build_video_prompt("恐怖", HORROR_SHOT)
        assert "cinematic motion" in result


class TestTranslateHorrorScene:
    @pytest.mark.parametrize("value,expected", [
        ("老宅堂屋", "abandoned ancestral house interior"),
        ("村口枯井", "old dry well"),
        ("雾气山路", "foggy mountain road"),
        ("祖坟边", "old family graveyard"),
        ("废弃祠堂", "deserted ancestral shrine"),
        ("未知地点", "folk horror location at night"),
    ])
    def test_scenes(self, value: str, expected: str) -> None:
        assert expected in translate_horror_scene(value)


class TestTranslateHorrorAnchor:
    @pytest.mark.parametrize("value,expected", [
        ("符纸", "yellow ritual paper"),
        ("红绳", "red ritual thread"),
        ("旧照片", "faded family photograph"),
        ("白瓷碗", "porcelain offering bowl"),
        ("黑伞", "black umbrella"),
        ("门缝", "door gap"),
        ("未知", "ritual object"),
    ])
    def test_anchors(self, value: str, expected: str) -> None:
        assert expected in translate_horror_anchor(value)


class TestTranslateHorrorEmotion:
    @pytest.mark.parametrize("value,expected", [
        ("震惊", "shocked"),
        ("真相大白", "shocked"),
        ("惊惧", "terrified"),
        ("失控", "terrified"),
        ("不安", "uneasy"),
        ("未解之谜", "unresolved"),
        ("钩子", "unresolved"),
        ("普通情绪", "quiet dread"),
    ])
    def test_emotions(self, value: str, expected: str) -> None:
        assert expected in translate_horror_emotion(value)


class TestTranslateHorrorCamera:
    @pytest.mark.parametrize("value,expected", [
        ("背影", "medium back-view"),
        ("远景", "distant static wide"),
        ("极近", "extreme close-up"),
        ("物件", "close-up"),
        ("低角度", "low angle wide"),
        ("暗光", "dark handheld flashlight"),
        ("普通镜头", "cinematic vertical"),
    ])
    def test_cameras(self, value: str, expected: str) -> None:
        assert expected in translate_horror_camera(value)


class TestVisualDirectionForStrategy:
    @pytest.mark.parametrize("strategy,expected", [
        ("back_view", "behind"),
        ("silhouette", "silhouette"),
        ("close_up", "close-up"),
        ("object", "by itself"),
        ("fog", "fog"),
        ("dark_light", "flashlight beam"),
        ("unknown", "dark obstructed"),
    ])
    def test_strategies(self, strategy: str, expected: str) -> None:
        assert expected in visual_direction_for_strategy(strategy, "object")


class TestActionForBeat:
    @pytest.mark.parametrize("beat,expected", [
        ("taboo", "points toward"),
        ("omen", "footsteps"),
        ("escalation", "shifts by itself"),
        ("reveal", "past disappearance"),
        ("hook", "whispers"),
        ("unknown", "supernatural moment"),
    ])
    def test_beats(self, beat: str, expected: str) -> None:
        assert expected in action_for_beat(beat, "object")


class TestBuildHorrorPromptContext:
    def test_with_horror(self) -> None:
        result = build_horror_prompt_context({"horror_beat": "taboo", "sound_cue": "whisper"})
        assert "玄学民俗" in result
        assert "taboo" in result

    def test_without_horror(self) -> None:
        assert build_horror_prompt_context({"scene": "普通"}) == ""


class TestBuildTtsPrompt:
    def test_extracts_dialogue(self) -> None:
        assert build_tts_prompt({"dialogue": "你好世界"}) == "你好世界"

    def test_empty_dialogue(self) -> None:
        assert build_tts_prompt({"dialogue": ""}) == ""


class TestBuildRequestPayload:
    def test_image_job(self) -> None:
        job = JobRecord(job_id="JOB_E01_S001_IMAGE", episode_code="E01", job_type="image", provider="openai_image", status="pending")
        payload = build_request_payload(job, "openai_image", "测试集", "S001", SIMPLE_SHOT, Path("/out"))
        assert payload["job_type"] == "image"
        assert payload["output_path"].endswith(".png")
        assert "测试集" in payload["prompt"]

    def test_video_job(self) -> None:
        job = JobRecord(job_id="JOB_E01_S001_VIDEO", episode_code="E01", job_type="video", provider="local_comfyui_video", status="pending")
        payload = build_request_payload(job, "local_comfyui_video", "测试", "S001", SIMPLE_SHOT, Path("/out"))
        assert payload["job_type"] == "video"
        assert payload["output_path"].endswith(".mp4")

    def test_tts_job(self) -> None:
        job = JobRecord(job_id="JOB_E01_S001_TTS", episode_code="E01", job_type="tts", provider="openai_tts", status="pending")
        payload = build_request_payload(job, "openai_tts", "测试", "S001", {"dialogue": "hello"}, Path("/out"))
        assert payload["job_type"] == "tts"
        assert payload["output_path"].endswith(".wav")
        assert payload["prompt"] == "hello"


class TestApplyProviderOverrides:
    def test_no_overrides(self) -> None:
        jobs = [JobRecord("J1", "E01", "image", "openai_image", "pending")]
        assert apply_provider_overrides(jobs, None) is jobs

    def test_with_overrides(self) -> None:
        jobs = [JobRecord("J1", "E01", "image", "openai_image", "pending")]
        result = apply_provider_overrides(jobs, {"image": "local_comfyui_image"})
        assert result[0].provider == "local_comfyui_image"

    def test_partial_override(self) -> None:
        jobs = [JobRecord("J1", "E01", "image", "openai_image", "pending"),
                JobRecord("J2", "E01", "video", "sora", "pending")]
        result = apply_provider_overrides(jobs, {"image": "local_comfyui_image"})
        assert result[0].provider == "local_comfyui_image"
        assert result[1].provider == "sora"


class TestExtractRequestRecords:
    def test_extracts(self) -> None:
        payload = {"request_records": [
            {"request_id": "R1", "job_id": "J1", "provider": "p1", "job_type": "image",
             "request_status": "ready", "endpoint": "/ep", "payload_path": "/out"}
        ]}
        records = extract_request_records(payload)
        assert len(records) == 1
        assert isinstance(records[0], ProviderRequestRecord)
        assert records[0].request_id == "R1"

    def test_empty(self) -> None:
        assert extract_request_records({}) == []


class TestWriteProviderRequests:
    def test_writes_file(self, tmp_path: Path) -> None:
        path = tmp_path / "requests.json"
        payload = {"request_count": 1, "requests": [{"request_id": "R1"}]}
        write_provider_requests(path, payload)
        assert path.exists()
        assert "R1" in path.read_text(encoding="utf-8")

    def test_excludes_request_records(self, tmp_path: Path) -> None:
        path = tmp_path / "out.json"
        payload = {"request_count": 1, "requests": [], "request_records": [{"request_id": "R1"}]}
        write_provider_requests(path, payload)
        content = path.read_text(encoding="utf-8")
        assert "request_records" not in content
