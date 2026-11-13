"""分镜督导（全集连续性审核/批量重写）测试。"""
from __future__ import annotations

import json

from aicomic.intelligence import storyboard_supervisor as sv


SHOTS = [
    {"shot_id": "S01", "scene": "雨夜街道，女人撑伞", "character": "女主角"},
    {"shot_id": "S02", "scene": "雨夜街道，女人转身", "character": "女主角"},
    {"shot_id": "S03", "scene": "下雨的街，男人出现", "character": "男主角"},
]


class TestCollectTerms:
    def test_counts_scene_and_char_terms(self):
        terms = sv.collect_terms(SHOTS)
        assert terms["shot_count"] == 3
        assert any(t["count"] >= 2 for t in terms["scene_terms"])
        assert {c["term"] for c in terms["char_terms"]} == {"女主角", "男主角"}

    def test_empty_shots(self):
        terms = sv.collect_terms([])
        assert terms["shot_count"] == 0


class TestRuleBasedIssues:
    def test_reports_missing_visual_text(self):
        shots = [{"shot_id": "S01"}, {"shot_id": "S02", "scene": "街头"}]
        issues = sv.rule_based_issues(shots)
        codes = [i["code"] for i in issues]
        assert "shot_without_visual_text" in codes

    def test_no_issue_when_clean(self):
        issues = sv.rule_based_issues(SHOTS)
        assert all(i["code"] != "shot_without_visual_text" for i in issues)


class TestParseReply:
    def test_parses_plain_json(self):
        reply = json.dumps({"issues": [{"shot_id": "S02", "code": "x", "message": "m"}],
                            "rewrites": [{"shot_id": "S02", "visual": "统一描述"}]})
        r = sv.parse_supervisor_reply(reply, SHOTS)
        assert r["ok"] is True
        assert len(r["issues"]) == 1
        assert r["rewrites"][0]["visual"] == "统一描述"

    def test_tolerates_code_fence(self):
        reply = '```json\n{"issues": [], "rewrites": [{"shot_id": "S01", "visual": "v"}]}\n```'
        r = sv.parse_supervisor_reply(reply, SHOTS)
        assert r["ok"] is True
        assert len(r["rewrites"]) == 1

    def test_drops_unknown_shot_ids(self):
        reply = json.dumps({"rewrites": [{"shot_id": "S99", "visual": "ghost"},
                                         {"shot_id": "S01", "visual": "ok"}]})
        r = sv.parse_supervisor_reply(reply, SHOTS)
        assert r["ok"] is True
        assert len(r["rewrites"]) == 1
        assert r["dropped_rewrites"] == 1

    def test_non_json_is_fail_soft(self):
        r = sv.parse_supervisor_reply("不是 JSON", SHOTS)
        assert r["ok"] is False
        assert "no json object" in r["error"]

    def test_empty_reply(self):
        r = sv.parse_supervisor_reply("   ", SHOTS)
        assert r["ok"] is False


class TestReviewEpisode:
    def test_rule_only_when_no_llm(self):
        r = sv.review_episode(SHOTS, episode_code="E01")
        assert r["ok"] is True
        assert r["llm_used"] is False
        assert r["rewrites"] == []
        assert r["terms"]["shot_count"] == 3

    def test_llm_path_applies_rewrite(self):
        def fake_llm(prompt: str) -> str:
            assert "全部分镜" in prompt
            return json.dumps({"issues": [{"shot_id": "S03", "code": "scene_drift", "message": "场景词不统一"}],
                               "rewrites": [{"shot_id": "S03", "visual": "雨夜街道，男人出现"}]})

        r = sv.review_episode(SHOTS, episode_code="E01", llm_fn=fake_llm)
        assert r["ok"] is True
        assert r["llm_used"] is True
        assert len(r["rewrites"]) == 1
        merged = sv.apply_rewrites(SHOTS, r["rewrites"])
        assert merged[2]["scene"] == "雨夜街道，男人出现"
        assert merged[0]["scene"] == SHOTS[0]["scene"]  # 未受影响

    def test_llm_exception_is_structured(self):
        def boom(_p: str) -> str:
            raise RuntimeError("network down")

        r = sv.review_episode(SHOTS, llm_fn=boom)
        assert r["ok"] is False
        assert "llm error" in r["error"]

    def test_empty_shots(self):
        r = sv.review_episode([])
        assert r["ok"] is False
        assert "no shots" in r["error"]


class TestApplyRewrites:
    def test_does_not_mutate_input(self):
        original = json.loads(json.dumps(SHOTS))
        sv.apply_rewrites(SHOTS, [{"shot_id": "S01", "visual": "新描述"}])
        assert SHOTS == original

    def test_writes_to_existing_field(self):
        merged = sv.apply_rewrites(SHOTS, [{"shot_id": "S01", "visual": "新描述"}])
        assert merged[0]["scene"] == "新描述"
