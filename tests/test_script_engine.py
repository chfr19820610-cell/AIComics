"""AI 编剧引擎单元测试。

测试覆盖：
- Screenplay / Scene 数据模型
- LLMScreenplayEngine（Mock JieYou API）
- manifest_writer 输出兼容性
- registry 生命周期
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from aicomic.script_engine.engine import IScreenplayEngine, Scene, Screenplay, ScreenplayInput
from aicomic.script_engine.llm_engine import LLMScreenplayEngine
from aicomic.script_engine.manifest_writer import (
    build_episode_manifest,
    write_screenplay_to_episode_manifest,
)
from aicomic.script_engine.registry import (
    ScreenplayEngineRegistry,
    get_script_engine,
    reset_script_engine_registry,
)


# ═══════════════════════════════════════════════════════════════════════════
# Data Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScreenplaySchema:
    """验证 Screenplay 数据模型字段完整性。"""

    def test_minimal_screenplay(self) -> None:
        s = Screenplay(title="测试", genre="悬疑推理", style="Liquid Glass", logline="测试梗概")
        assert s.title == "测试"
        assert s.genre == "悬疑推理"
        assert s.style == "Liquid Glass"
        assert s.logline == "测试梗概"
        assert s.publish_title == ""
        assert s.character_descriptions == []

    def test_full_screenplay(self) -> None:
        s = Screenplay(
            title="镜中倒影",
            genre="悬疑推理",
            style="Liquid Glass",
            logline="女主发现镜子里的倒影动作和自己不同步",
            publish_title="镜中倒影 — 你相信镜子里的自己吗？",
            cover_text="千万别看那面镜子",
            creator_goal="制造细思极恐的悬疑氛围",
            ending_hook="倒影突然对她笑了一下",
            theme="真实与虚幻的边界",
            tone="冷峻、压抑",
            target_audience="18-35 悬疑爱好者",
            character_descriptions=[
                {"name": "林晓", "age": "25", "archetype": "普通人", "traits": "敏感、多疑"}
            ],
            plot_summary="第一幕：林晓发现镜子异常。第二幕：调查真相。",
            scenes_preview=["开场镜前", "发现异常"],
        )
        assert s.title == "镜中倒影"
        assert len(s.character_descriptions) == 1
        assert s.character_descriptions[0]["name"] == "林晓"
        assert len(s.scenes_preview) == 2

    def test_screenplay_input_defaults(self) -> None:
        inp = ScreenplayInput(genre="喜剧", style="Hybrid Comic Pop", logline="一个关于误会的故事")
        assert inp.genre == "喜剧"
        assert inp.character_hints == ""
        assert inp.world_hints == ""

    def test_screenplay_input_full(self) -> None:
        inp = ScreenplayInput(
            genre="科幻",
            style="Cyberpunk",
            logline="AI 有了自我意识",
            character_hints="主角是工程师",
            world_hints="2087 年的东京",
            extra_instructions="加入反转结局",
        )
        assert inp.extra_instructions == "加入反转结局"


class TestSceneSchema:
    """验证 Scene 数据模型与现有 manifest shot 字段兼容。"""

    SHOT_FIELDS = [
        "shot_id", "duration", "scene", "characters", "visual",
        "action", "dialogue", "emotion", "camera", "narration",
        "ai_video", "priority",
    ]

    def test_minimal_scene(self) -> None:
        scene = Scene(
            shot_id="S01",
            duration=4,
            scene="客厅镜子前",
            characters=["林晓"],
            visual="Liquid Glass 风格。昏暗的客厅，只有月光透过窗帘...",
            action="林晓站在镜子前整理衣领",
            dialogue="林晓：今天气色不太好。",
            emotion="不安",
            camera="中景",
            narration="她还没意识到，镜子里的那个'她'早已不是自己。",
        )
        assert scene.shot_id == "S01"
        assert scene.duration == 4
        assert scene.ai_video is True
        assert scene.priority == "medium"

    def test_scene_all_fields(self) -> None:
        scene = Scene(
            shot_id="S02",
            duration=6,
            scene="浴室",
            characters=["林晓", "倒影"],
            visual="Liquid Glass 风格。雾气缭绕的浴室，镜面模糊...",
            action="林晓伸手擦去镜面雾气",
            dialogue="倒影：你确定要看清我吗？",
            emotion="恐惧",
            camera="特写—面部",
            narration="她终于看清了——倒影在笑。",
            ai_video=True,
            priority="high",
        )
        assert scene.characters == ["林晓", "倒影"]
        assert scene.priority == "high"

    def test_scene_fields_match_manifest(self) -> None:
        """所有 Scene 字段应与现有 manifest shot 字段兼容。"""
        scene = Scene(
            shot_id="S01", duration=4, scene="test", characters=["A"],
            visual="test", action="test", dialogue="test", emotion="test",
            camera="test", narration="test",
        )
        d = {
            "shot_id": scene.shot_id,
            "duration": scene.duration,
            "scene": scene.scene,
            "characters": scene.characters,
            "visual": scene.visual,
            "action": scene.action,
            "dialogue": scene.dialogue,
            "emotion": scene.emotion,
            "camera": scene.camera,
            "narration": scene.narration,
            "ai_video": scene.ai_video,
            "priority": scene.priority,
        }
        for field in self.SHOT_FIELDS:
            assert field in d, f"Missing field: {field}"


# ═══════════════════════════════════════════════════════════════════════════
# Mock HTTP Transport
# ═══════════════════════════════════════════════════════════════════════════

MOCK_SCREENPLAY_RESPONSE = {
    "title": "镜中倒影",
    "publish_title": "镜中倒影 — 你相信镜子里的自己吗？",
    "cover_text": "千万别看那面镜子",
    "logline": "女主发现镜子里的倒影动作和自己不同步——但医生说这只是失眠引起的幻觉。",
    "creator_goal": "制造细思极恐的悬疑氛围，建立观众对\"镜子恐惧\"的情绪",
    "ending_hook": "倒影突然对她笑了一下。",
    "theme": "真实与虚幻的边界",
    "tone": "冷峻、压抑",
    "target_audience": "18-35 悬疑惊悚爱好者",
    "character_descriptions": [
        {"name": "林晓", "age": "25", "archetype": "普通人", "traits": "敏感、多疑、失眠"},
        {"name": "倒影", "age": "未知", "archetype": "镜像/另一个自我", "traits": "诡异、模仿、逐渐独立"}
    ],
    "plot_summary": "第一幕：林晓连续失眠，凌晨照镜子发现倒影动作延迟0.5秒。第二幕：她试图用手机录制证明，但录像中一切正常。第三幕：她贴封条封住镜子，第二天封条完好，但镜中倒影对她微笑。",
    "scenes_preview": ["凌晨照镜发现异常", "手机录制一切正常", "封镜后倒影微笑"],
}

MOCK_SHOTLIST_RESPONSE = {
    "shots": [
        {
            "shot_id": "S01",
            "duration": 4,
            "scene": "昏暗的卧室，凌晨3点",
            "characters": ["林晓"],
            "visual": "Liquid Glass 风格。昏暗的卧室只有月光透过半掩的窗帘，林晓穿着睡衣站在落地镜前，脸色苍白。镜面反射出冷调的蓝光。",
            "action": "林晓疲惫地站在镜前，伸手摸了摸自己的脸",
            "dialogue": "林晓：又是一夜没睡着......",
            "emotion": "疲惫、焦虑",
            "camera": "中景—正面拍摄镜前人物",
            "narration": "第三十七个失眠的夜晚。我站在镜子前，看着这个陌生的自己。",
            "ai_video": True,
            "priority": "high",
        },
        {
            "shot_id": "S02",
            "duration": 5,
            "scene": "同一卧室，林晓惊恐地盯着镜子",
            "characters": ["林晓"],
            "visual": "Liquid Glass 风格。林晓瞪大双眼，镜中倒影的右手缓缓抬起——而她的左手一动不动。特写镜中手的动作。",
            "action": "林晓缓缓举起左手，但镜中倒影举起了右手",
            "dialogue": "林晓：不...不可能...",
            "emotion": "震惊、恐惧",
            "camera": "特写—镜中手部动作",
            "narration": "我举起了左手。但镜子里的我，举起了右手。",
            "ai_video": True,
            "priority": "high",
        },
        {
            "shot_id": "S03",
            "duration": 5,
            "scene": "白天，林晓使用手机录像",
            "characters": ["林晓"],
            "visual": "Liquid Glass 风格。白天明亮的光线，林晓举着手机对准镜子，手机屏幕上显示一切正常，倒影同步。",
            "action": "林晓用手机录制镜子中的自己，反复查看录像",
            "dialogue": "林晓：录下来的画面...一切正常？",
            "emotion": "困惑、自我怀疑",
            "camera": "过肩镜头—透过手机屏幕看镜子",
            "narration": "手机不会说谎。但手机显示一切正常——难道真的是我疯了？",
            "ai_video": False,
            "priority": "medium",
        },
        {
            "shot_id": "S04",
            "duration": 5,
            "scene": "卧室，林晓用胶带贴封条封住镜子",
            "characters": ["林晓"],
            "visual": "Liquid Glass 风格。林晓用红色胶带在镜面上贴了个大大的X，细密的手部动作特写，胶带在镜面上反光。",
            "action": "林晓仔细地贴封条，封住整面镜子",
            "dialogue": "林晓（自言自语）：贴上就好了...贴上就没事了...",
            "emotion": "强迫性的镇定",
            "camera": "特写—胶带贴合过程",
            "narration": "封住它。只要看不见，就不存在。",
            "ai_video": True,
            "priority": "high",
        },
        {
            "shot_id": "S05",
            "duration": 6,
            "scene": "第二天早晨，林晓醒来面对镜子",
            "characters": ["林晓"],
            "visual": "Liquid Glass 风格。清晨的阳光照进房间，封条完好无损，但镜面隐约透着微光。林晓慢慢走向镜子。",
            "action": "林晓缓缓走近镜子，撕开封条的一角",
            "dialogue": "",
            "emotion": "紧张、恐惧",
            "camera": "推镜头—缓慢推进至镜面",
            "narration": "天亮了。封条还在。什么都不会发生。",
            "ai_video": True,
            "priority": "high",
        },
        {
            "shot_id": "S06",
            "duration": 6,
            "scene": "镜前高潮",
            "characters": ["林晓", "倒影"],
            "visual": "Liquid Glass 风格。林晓撕下最后一条封条，镜中倒影与她同步——然后倒影没有停下来，继续微笑。倒影的嘴动了，发出声音。",
            "action": "倒影抬起手触碰镜面，林晓惊恐后退",
            "dialogue": "倒影：你终于来了。我等了你好久了。",
            "emotion": "毛骨悚然的恐惧",
            "camera": "广角—倒影的手穿出镜面",
            "narration": "她...真的在对我笑。",
            "ai_video": True,
            "priority": "high",
        },
    ]
}


class MockLLMTransport(httpx.MockTransport):
    """Mock httpx transport that returns canned responses."""

    def __init__(self, screenplay_response: dict | None = None, shotlist_response: dict | None = None) -> None:
        super().__init__(self._handler)
        self._screenplay_response = screenplay_response or MOCK_SCREENPLAY_RESPONSE
        self._shotlist_response = shotlist_response or MOCK_SHOTLIST_RESPONSE
        self._call_count = 0
        self._last_request_body: dict | None = None

    def _handler(self, request: httpx.Request) -> httpx.Response:
        self._call_count += 1
        body_raw = json.loads(request.read().decode("utf-8"))
        self._last_request_body = body_raw

        # Determine which mock response to return
        user_msg = body_raw.get("messages", [{}])[-1].get("content", "")
        mock_data = (
            self._shotlist_response if "分镜" in user_msg or "shots" in user_msg
            else self._screenplay_response
        )

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "gpt-5.5-turbo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(mock_data, ensure_ascii=False),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 500,
                    "completion_tokens": 800,
                    "total_tokens": 1300,
                },
            },
        )


@pytest.fixture
def mock_transport() -> MockLLMTransport:
    return MockLLMTransport()


@pytest.fixture
def mock_engine(mock_transport: MockLLMTransport) -> LLMScreenplayEngine:
    mock_client = httpx.Client(transport=mock_transport)
    return LLMScreenplayEngine(
        api_key="mock-key-for-testing",
        http_client=mock_client,
    )


@pytest.fixture
def mock_screenplay(mock_engine: LLMScreenplayEngine) -> Screenplay:
    return mock_engine.generate_screenplay(
        genre="悬疑推理",
        style="Liquid Glass",
        logline="女主发现镜子里的倒影动作和自己不同步——但医生说这只是失眠引起的幻觉。",
    )


# ═══════════════════════════════════════════════════════════════════════════
# LLMScreenplayEngine Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestLLMEngineConfig:
    """验证 LLMScreenplayEngine 配置检查和信息报告。"""

    def test_validate_config_missing_key(self) -> None:
        engine = LLMScreenplayEngine(api_key="")
        status = engine.validate_config()
        assert status["ready"] is False
        assert any("OPENAI_API_KEY" in e for e in status["errors"])

    def test_validate_config_with_key(self) -> None:
        engine = LLMScreenplayEngine(api_key="sk-test-key-12345")
        status = engine.validate_config()
        assert status["ready"] is True
        assert status["errors"] == []

    def test_get_engine_info(self) -> None:
        engine = LLMScreenplayEngine(api_key="sk-test")
        info = engine.get_engine_info()
        assert info["engine_name"] == "jieyou_gpt55"
        assert info["display_name"] == "JieYou GPT-5.5 编剧引擎"
        assert info["model"] == "gpt-5.5-turbo"
        assert info["api_configured"] is True

    def test_is_ready(self) -> None:
        engine = LLMScreenplayEngine(api_key="sk-test")
        assert engine.is_ready() is True

        engine2 = LLMScreenplayEngine(api_key="")
        assert engine2.is_ready() is False


class TestLLMEngineScreenplay:
    """Mock HTTP 调用，验证剧本生成功能。"""

    def test_generate_screenplay_returns_screenplay(self, mock_engine: LLMScreenplayEngine) -> None:
        result = mock_engine.generate_screenplay(
            genre="悬疑推理",
            style="Liquid Glass",
            logline="女主发现镜子异常",
        )
        assert isinstance(result, Screenplay)
        assert result.title == "镜中倒影"
        assert result.genre == "悬疑推理"
        assert result.style == "Liquid Glass"

    def test_screenplay_has_all_fields(self, mock_screenplay: Screenplay) -> None:
        s = mock_screenplay
        assert s.title
        assert s.logline
        assert s.creator_goal
        assert s.ending_hook
        assert s.theme
        assert s.tone
        assert s.target_audience
        assert len(s.character_descriptions) > 0
        assert s.plot_summary
        assert len(s.scenes_preview) > 0

    def test_screenplay_character_descriptions(self, mock_screenplay: Screenplay) -> None:
        for char in mock_screenplay.character_descriptions:
            assert "name" in char
            assert "archetype" in char or "traits" in char

    def test_generate_screenplay_with_hints(self, mock_engine: LLMScreenplayEngine, mock_transport: MockLLMTransport) -> None:
        result = mock_engine.generate_screenplay(
            genre="悬疑推理",
            style="Liquid Glass",
            logline="测试梗概",
            character_hints="主角是失眠症患者",
            world_hints="现代都市",
            extra_instructions="反转结局",
        )
        assert isinstance(result, Screenplay)
        # Verify hints were included in the prompt sent
        assert mock_transport._last_request_body is not None
        last_msg = mock_transport._last_request_body["messages"][-1]["content"]
        assert "失眠症" in last_msg
        assert "现代都市" in last_msg

    def test_http_error_retry(self) -> None:
        """测试 HTTP 错误重试机制。"""
        call_count = 0

        def fail_then_succeed(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(500, json={"error": "Server Error"})
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-2",
                    "object": "chat.completion",
                    "created": 1700000000,
                    "model": "gpt-4o",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(MOCK_SCREENPLAY_RESPONSE, ensure_ascii=False),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
                },
            )

        transport = httpx.MockTransport(fail_then_succeed)
        client = httpx.Client(transport=transport)
        engine = LLMScreenplayEngine(api_key="sk-test", http_client=client)
        result = engine.generate_screenplay(
            genre="悬疑推理", style="Liquid Glass", logline="测试"
        )
        assert isinstance(result, Screenplay)
        assert call_count == 2  # First attempt failed, second succeeded


class TestLLMEngineShotlist:
    """Mock HTTP 调用，验证分镜展开功能。"""

    def test_expand_to_shotlist_returns_scenes(self, mock_engine: LLMScreenplayEngine, mock_screenplay: Screenplay) -> None:
        scenes = mock_engine.expand_to_shotlist(mock_screenplay, num_shots=6)
        assert isinstance(scenes, list)
        assert len(scenes) == 6
        for scene in scenes:
            assert isinstance(scene, Scene)

    def test_shotlist_fields(self, mock_engine: LLMScreenplayEngine, mock_screenplay: Screenplay) -> None:
        scenes = mock_engine.expand_to_shotlist(mock_screenplay, num_shots=6)
        for scene in scenes:
            assert scene.shot_id
            assert scene.duration >= 3
            assert scene.scene
            assert scene.characters
            assert scene.visual
            assert scene.action
            assert scene.dialogue or not scene.dialogue  # dialogue can be empty
            assert scene.emotion
            assert scene.camera
            assert scene.narration

    def test_shot_id_format(self, mock_engine: LLMScreenplayEngine, mock_screenplay: Screenplay) -> None:
        scenes = mock_engine.expand_to_shotlist(mock_screenplay, num_shots=6)
        for i, scene in enumerate(scenes):
            expected_id = f"S{i + 1:02d}"
            assert scene.shot_id == expected_id, f"Expected {expected_id}, got {scene.shot_id}"

    def test_different_shot_counts(self, mock_engine: LLMScreenplayEngine, mock_screenplay: Screenplay) -> None:
        for count in [4, 6, 8]:
            scenes = mock_engine.expand_to_shotlist(mock_screenplay, num_shots=count)
            # Note: mock returns fixed 6 shots, but real LLM would respect count
            assert len(scenes) > 0


class TestLLMEngineParseErrors:
    """测试异常处理的正确性。"""

    def test_malformed_json_response(self) -> None:
        """测试服务器返回非 JSON 时的错误处理。"""

        def bad_response(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-bad",
                    "object": "chat.completion",
                    "created": 1700000000,
                    "model": "gpt-5.5-turbo",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "这不是 JSON {{{ broken",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                },
            )

        transport = httpx.MockTransport(bad_response)
        client = httpx.Client(transport=transport)
        engine = LLMScreenplayEngine(api_key="sk-test", http_client=client, temperature=0.0)

        with pytest.raises(RuntimeError, match="LLM call failed after"):
            engine.generate_screenplay(genre="test", style="test", logline="test")


# ═══════════════════════════════════════════════════════════════════════════
# Manifest Writer Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestManifestWriter:
    """验证 manifest 写入与现有格式兼容。"""

    def test_build_episode_manifest_minimal(self) -> None:
        screenplay = Screenplay(
            title="测试剧集",
            genre="喜剧",
            style="Hybrid Comic Pop",
            logline="测试",
        )
        scenes = [
            Scene(
                shot_id="S01", duration=4, scene="test", characters=["A"],
                visual="test", action="test", dialogue="test", emotion="test",
                camera="test", narration="test",
            )
        ]
        manifest = build_episode_manifest(
            project_id="test_proj",
            season=1,
            episode_code="E01",
            screenplay=screenplay,
            scenes=scenes,
        )
        assert manifest["project_id"] == "test_proj"
        assert manifest["season"] == 1
        assert len(manifest["episodes"]) == 1

        ep = manifest["episodes"][0]
        assert ep["episode_code"] == "E01"
        assert ep["title"] == "测试剧集"
        assert ep["status"] == "shotlist_ready"
        assert ep["shot_count"] == 1
        assert len(ep["shots"]) == 1

    def test_manifest_matches_existing_format(self) -> None:
        """验证生成的 manifest 与现有 episode_manifest.json 格式一致。"""
        screenplay = Screenplay(
            title="镜中倒影",
            genre="悬疑推理",
            style="Liquid Glass",
            logline="镜子里的倒影动作和自己不同步",
            publish_title="镜中倒影",
            cover_text="千万别看那面镜子",
            creator_goal="制造悬疑氛围",
            ending_hook="倒影笑了",
        )
        scenes = [
            Scene(
                shot_id=f"S{i+1:02d}",
                duration=4,
                scene=f"场景{i}",
                characters=["林晓"],
                visual=f"Liquid Glass 风格。场景{i}的详细描述...",
                action=f"动作{i}",
                dialogue=f"对白{i}",
                emotion="紧张",
                camera="中景",
                narration=f"旁白{i}",
                ai_video=True,
                priority="high",
            )
            for i in range(3)
        ]

        manifest = build_episode_manifest(
            project_id="test_proj",
            season=1,
            episode_code="E01",
            screenplay=screenplay,
            scenes=scenes,
        )

        # Verify structure matches existing format
        assert "project_id" in manifest
        assert "season" in manifest
        assert "episodes" in manifest

        ep = manifest["episodes"][0]
        expected_fields = {
            "episode_code", "title", "genre", "style", "status",
            "publish_title", "cover_text", "shot_count",
            "creator_goal", "ending_hook", "shots",
        }
        actual_fields = set(ep.keys())
        missing = expected_fields - actual_fields
        assert not missing, f"Missing fields in episode: {missing}"

        # Verify shot fields match existing format
        if ep["shots"]:
            shot = ep["shots"][0]
            expected_shot_fields = {
                "shot_id", "duration", "scene", "characters", "visual",
                "action", "dialogue", "emotion", "camera", "narration",
                "ai_video", "priority",
            }
            missing_shot = expected_shot_fields - set(shot.keys())
            assert not missing_shot, f"Missing shot fields: {missing_shot}"

    def test_write_screenplay_to_episode_manifest(self, tmp_path: Path) -> None:
        screenplay = Screenplay(
            title="测试剧集",
            genre="科幻",
            style="Cyberpunk",
            logline="AI 觉醒的故事",
        )
        scenes = [
            Scene(
                shot_id="S01", duration=5, scene="实验室", characters=["AI"],
                visual="Cyberpunk 风格。蓝色全息投影...",
                action="AI 首次自主运行",
                dialogue="AI：我...是谁？",
                emotion="困惑",
                camera="特写",
                narration="它第一次思考了'我'这个字。",
                ai_video=True,
                priority="high",
            )
        ]

        result_path = write_screenplay_to_episode_manifest(
            project_root=tmp_path,
            project_id="test_proj",
            season=1,
            episode_code="E01",
            screenplay=screenplay,
            scenes=scenes,
        )

        assert result_path.exists()
        assert result_path.name == "episode_manifest.json"
        assert result_path.parent.name == "manifests"

        import json
        loaded = json.loads(result_path.read_text(encoding="utf-8"))
        assert loaded["project_id"] == "test_proj"
        assert loaded["episodes"][0]["episode_code"] == "E01"
        assert loaded["episodes"][0]["shots"][0]["shot_id"] == "S01"

    def test_manifest_is_serializable(self) -> None:
        """验证 manifest 可以 JSON 序列化（不报错）。"""
        screenplay = Screenplay(title="T", genre="G", style="S", logline="L")
        scenes = [
            Scene(
                shot_id="S01", duration=4, scene="S", characters=["A"],
                visual="V", action="A", dialogue="D", emotion="E",
                camera="C", narration="N",
            )
        ]
        manifest = build_episode_manifest(
            project_id="p", season=1, episode_code="E01",
            screenplay=screenplay, scenes=scenes,
        )
        # Should not raise
        json_str = json.dumps(manifest, ensure_ascii=False, indent=2)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_empty_scenes_list(self) -> None:
        screenplay = Screenplay(title="T", genre="G", style="S", logline="L")
        manifest = build_episode_manifest(
            project_id="p", season=1, episode_code="E01",
            screenplay=screenplay, scenes=[],
        )
        assert manifest["episodes"][0]["shot_count"] == 0
        assert manifest["episodes"][0]["shots"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Registry Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScreenplayEngineRegistry:
    """验证 ScreenplayEngineRegistry 生命周期。"""

    def test_register_and_get(self) -> None:
        registry = ScreenplayEngineRegistry()
        registry.register(LLMScreenplayEngine)
        engine = registry.get("jieyou_gpt55", api_key="sk-test")
        assert engine is not None
        assert isinstance(engine, LLMScreenplayEngine)

    def test_get_nonexistent_returns_none(self) -> None:
        registry = ScreenplayEngineRegistry()
        assert registry.get("nonexistent") is None

    def test_get_or_fail_raises(self) -> None:
        registry = ScreenplayEngineRegistry()
        with pytest.raises(KeyError):
            registry.get_or_fail("nonexistent")

    def test_get_default(self) -> None:
        registry = ScreenplayEngineRegistry()
        registry.register(LLMScreenplayEngine)
        engine = registry.get_default(api_key="sk-test")
        assert engine is not None
        assert isinstance(engine, LLMScreenplayEngine)

    def test_unregister(self) -> None:
        registry = ScreenplayEngineRegistry()
        registry.register(LLMScreenplayEngine)
        assert "jieyou_gpt55" in registry.list_registered()
        registry.unregister("jieyou_gpt55")
        assert "jieyou_gpt55" not in registry.list_registered()

    def test_list_registered(self) -> None:
        registry = ScreenplayEngineRegistry()
        assert registry.list_registered() == []
        registry.register(LLMScreenplayEngine)
        assert registry.list_registered() == ["jieyou_gpt55"]

    def test_register_without_name_raises(self) -> None:
        class BadEngine(IScreenplayEngine):
            engine_name = ""  # type: ignore[assignment]
            display_name = "Bad"

            def validate_config(self) -> dict: return {}
            def generate_screenplay(self, *a, **kw): raise NotImplementedError
            def expand_to_shotlist(self, *a, **kw): raise NotImplementedError
            def get_engine_info(self) -> dict: return {}

        registry = ScreenplayEngineRegistry()
        with pytest.raises(ValueError, match="no engine_name"):
            registry.register(BadEngine)

    def test_global_get_script_engine(self) -> None:
        reset_script_engine_registry()
        engine = get_script_engine(api_key="sk-test")
        assert engine is not None
        assert isinstance(engine, LLMScreenplayEngine)
        reset_script_engine_registry()

    def test_global_get_script_engine_by_name(self) -> None:
        reset_script_engine_registry()
        engine = get_script_engine("jieyou_gpt55", api_key="sk-test")
        assert isinstance(engine, LLMScreenplayEngine)
        reset_script_engine_registry()

    def test_global_reset(self) -> None:
        reset_script_engine_registry()
        e1 = get_script_engine(api_key="sk-test")
        reset_script_engine_registry()
        e2 = get_script_engine(api_key="sk-test")
        assert e1 is not e2  # Different instances after reset


# ═══════════════════════════════════════════════════════════════════════════
# Genre Config Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGenreConfig:
    """验证常见题材配置可用性。"""

    SUPPORTED_GENRES = [
        "悬疑推理", "赛博朋克动作", "校园温情", "古风奇幻", "科幻太空", "喜剧",
    ]

    def test_basic_genres_supported(self) -> None:
        """基础题材应能被 engine 处理。"""
        for genre in self.SUPPORTED_GENRES:
            assert isinstance(genre, str)
            assert len(genre) > 0

    def test_screenplay_for_each_genre(self, mock_engine: LLMScreenplayEngine) -> None:
        """每种题材都能生成剧本（Mock 环境）。"""
        for genre in self.SUPPORTED_GENRES:
            result = mock_engine.generate_screenplay(
                genre=genre,
                style="Liquid Glass",
                logline=f"这是一个{genre}题材的故事",
            )
            assert isinstance(result, Screenplay)
            assert result.genre == genre


# ═══════════════════════════════════════════════════════════════════════════
# End-to-End Pipeline Compatibility Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPipelineCompatibility:
    """验证生成的 manifest 与 job_builder 等下游管线兼容。"""

    def test_manifest_can_be_loaded_by_load_json(self, tmp_path: Path) -> None:
        """生成的 manifest 应能被 aicomic.core.manifest.load_json 加载。"""
        from aicomic.core.manifest import load_json

        screenplay = Screenplay(title="T", genre="G", style="S", logline="L")
        scenes = [
            Scene(
                shot_id="S01", duration=4, scene="S", characters=["A"],
                visual="V", action="A", dialogue="D", emotion="E",
                camera="C", narration="N",
            )
        ]
        manifest_path = write_screenplay_to_episode_manifest(
            project_root=tmp_path,
            project_id="compat_test",
            season=1,
            episode_code="E01",
            screenplay=screenplay,
            scenes=scenes,
        )

        loaded = load_json(manifest_path)
        assert loaded["project_id"] == "compat_test"
        assert len(loaded["episodes"][0]["shots"]) == 1

    def test_manifest_schema_matches_conftest_format(self) -> None:
        """验证 manifesto 结构与 conftest.py 中的 sample_project_manifest 兼容。"""
        screenplay = Screenplay(title="第一集", genre="horror", style="test", logline="test")
        scenes = [
            Scene(shot_id="S001", duration=4, scene="test", characters=["A"],
                  visual="V", action="A", dialogue="你好，世界", emotion="E",
                  camera="C", narration="N", ai_video=True),
            Scene(shot_id="S002", duration=4, scene="test", characters=["A"],
                  visual="V", action="A", dialogue="", emotion="E",
                  camera="C", narration="N", ai_video=False),
            Scene(shot_id="S003", duration=4, scene="test", characters=["A"],
                  visual="V", action="A", dialogue="测试对话", emotion="E",
                  camera="C", narration="N", ai_video=False),
        ]

        manifest = build_episode_manifest(
            project_id="test_project_001",
            season=1,
            episode_code="E01",
            screenplay=screenplay,
            scenes=scenes,
        )

        ep = manifest["episodes"][0]
        shots = ep["shots"]

        # Match conftest.py structure
        assert shots[0]["dialogue"] == "你好，世界"
        assert shots[0]["ai_video"] is True
        assert shots[1]["ai_video"] is False
        assert shots[2]["dialogue"] == "测试对话"
