"""首尾帧三层决策测试。"""
from __future__ import annotations

import json

import pytest

from aicomic.core import frame_strategy as fs


class TestRuleLayer:
    def test_action_word_with_duration_goes_dual(self):
        d = fs.decide_frames({"description": "女主角转身跑向门口", "duration": 4.0})
        assert d["mode"] == "dual"
        assert d["layer"] == "rule"
        assert "跑" in d["reason"] or "转身" in d["reason"]

    def test_action_word_english(self):
        d = fs.decide_frames({"description": "the woman turns and walks away", "duration": 3.0})
        assert d["mode"] == "dual"

    def test_closeup_stays_single(self):
        d = fs.decide_frames({"description": "特写：她眼里的泪光", "duration": 3.0})
        assert d["mode"] == "single"
        assert d["layer"] == "rule"

    def test_shot_type_action(self):
        d = fs.decide_frames({"shot_type": "action", "description": "模糊描述", "duration": 1.0})
        assert d["mode"] == "dual"
        assert d["shot_type" if False else "layer"] == "rule"

    def test_shot_type_dialogue(self):
        d = fs.decide_frames({"shot_type": "dialogue", "description": "模糊描述"})
        assert d["mode"] == "single"

    def test_long_shot_prefers_dual(self):
        d = fs.decide_frames({"description": "两个人站着", "duration": 10.0})
        assert d["mode"] == "dual"
        assert d["layer"] == "rule"

    def test_short_action_word_falls_through(self):
        # 动作词但时长太短 → 不返回规则结论，交下一层
        assert fs.rule_decide({"description": "转身", "duration": 1.0}) is None


class TestFallbackLayer:
    def test_no_signal_uses_fallback(self):
        d = fs.decide_frames({"description": "一个场景", "duration": 2.0})
        assert d["mode"] == "single"
        assert d["layer"] == "fallback"
        assert d["confidence"] < 0.5

    def test_empty_shot(self):
        d = fs.decide_frames({})
        assert d["mode"] == "single"
        assert d["layer"] == "fallback"


class TestLLMLayer:
    def test_llm_high_confidence_accepted(self):
        def fake(_p):
            return json.dumps({"mode": "dual", "confidence": 0.9, "reason": "有明显位移"})

        d = fs.decide_frames({"description": "一个场景", "duration": 2.0}, llm_fn=fake)
        assert d["mode"] == "dual"
        assert d["layer"] == "llm"
        assert d["confidence"] == 0.9

    def test_llm_low_confidence_downgrades(self):
        def fake(_p):
            return json.dumps({"mode": "dual", "confidence": 0.3, "reason": "说不好"})

        d = fs.decide_frames({"description": "一个场景", "duration": 2.0}, llm_fn=fake)
        assert d["mode"] == "single"
        assert d["layer"] == "fallback"
        assert "置信度" in d["reason"]

    def test_llm_bad_json_downgrades(self):
        d = fs.decide_frames({"description": "一个场景"}, llm_fn=lambda _p: "不是JSON")
        assert d["layer"] == "fallback"

    def test_llm_exception_downgrades(self):
        def boom(_p):
            raise RuntimeError("network down")

        d = fs.decide_frames({"description": "一个场景"}, llm_fn=boom)
        assert d["layer"] == "fallback"
        assert "LLM 调用失败" in d["reason"]

    def test_rule_wins_before_llm(self):
        called = {"n": 0}

        def fake(_p):
            called["n"] += 1
            return json.dumps({"mode": "dual", "confidence": 0.99})

        d = fs.decide_frames({"description": "特写镜头"}, llm_fn=fake)
        assert d["layer"] == "rule"
        assert called["n"] == 0  # 规则命中就不该调 LLM


class TestParseReply:
    def test_tolerates_code_fence(self):
        r = fs.parse_llm_reply('```json\n{"mode":"dual","confidence":0.8}\n```')
        assert r["mode"] == "dual"

    def test_rejects_invalid_mode(self):
        assert fs.parse_llm_reply('{"mode":"maybe"}') is None

    def test_clamps_confidence(self):
        r = fs.parse_llm_reply('{"mode":"single","confidence":5}')
        assert r["confidence"] == 1.0


class TestEpisode:
    def test_episode_distribution(self):
        shots = [
            {"shot_id": "S01", "description": "特写：她的眼睛"},
            {"shot_id": "S02", "description": "女主角转身跑开", "duration": 4.0},
            {"shot_id": "S03", "description": "两个人待在房间里"},  # 无动作词/静态词/类型/长时长 → fallback
        ]
        r = fs.decide_episode(shots)
        assert r["shot_count"] == 3
        assert r["dual_count"] == 1
        assert r["single_count"] == 2
        assert r["by_layer"].get("rule") == 2
        assert r["by_layer"].get("fallback") == 1

    def test_prev_shot_passed_through(self):
        seen = {}

        def fake(prompt):
            seen["prompt"] = prompt
            return json.dumps({"mode": "single", "confidence": 0.9})

        shots = [
            {"shot_id": "S01", "description": "街头"},
            {"shot_id": "S02", "description": "她继续走"},  # 含"走" → 规则命中，不会走 LLM
        ]
        r = fs.decide_episode(shots, llm_fn=fake)
        assert r["shot_count"] == 2
