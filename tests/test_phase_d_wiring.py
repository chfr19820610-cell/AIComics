"""D1（Phase D）规则层质检单元测试——SOP §8.1 规则层（黑帧/时长/分辨率）。"""
from __future__ import annotations

import json
from pathlib import Path


class TestCheckAssetPreflight:
    def test_missing_file(self, tmp_path):
        from aicomic.video_synthesis.quality_check import check_asset

        report = check_asset(tmp_path / "absent.mp4")
        assert report["ok"] is False
        assert any("not_found" in issue["code"] for issue in report["issues"])

    def test_probe_unavailable_not_silent(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import quality_check as qc

        video = tmp_path / "a.mp4"
        video.write_bytes(b"0" * 32)
        monkeypatch.setattr(qc, "_run_probe", lambda cmd: (127, ""))  # ENOENT/坏架构
        monkeypatch.setattr(qc, "_run_ffmpeg", lambda cmd: 1)
        report = qc.check_asset(video)
        assert report["ok"] is False
        assert any(i["code"] == "probe_unavailable" for i in report["issues"])

    def test_duration_rule(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import quality_check as qc

        def probe_stream(duration_s: float):
            def impl(cmd):
                streams = [{"codec_type": "video", "width": 1080, "height": 1920, "duration": str(duration_s)}]
                return 0, json.dumps({"streams": streams})
            return impl

        video = tmp_path / "a.mp4"
        video.write_bytes(b"0" * 32)
        monkeypatch.setattr(qc, "_run_probe", probe_stream(1.2))
        monkeypatch.setattr(qc, "_run_blackdetect", lambda video: (1, ""))  # 工具不可用 → 单列 issue 不静默
        report = qc.check_asset(video, min_duration=5.0)
        assert report["ok"] is False
        assert any(i["code"] == "duration_too_short" for i in report["issues"])
        report_ok = qc.check_asset(video, min_duration=1.0)
        assert any(i["code"] == "blackdetect_unavailable" for i in report_ok["issues"])  # 黑帧检查不静默丢

    def test_resolution_rule(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import quality_check as qc

        def impl(cmd):
            streams = [{"codec_type": "video", "width": 720, "height": 1280, "duration": "8.0"}]
            return 0, json.dumps({"streams": streams})

        video = tmp_path / "a.mp4"
        video.write_bytes(b"0" * 32)
        monkeypatch.setattr(qc, "_run_probe", impl)
        monkeypatch.setattr(qc, "_run_blackdetect", lambda video: (1, ""))
        report = qc.check_asset(video, min_width=1080, min_height=1920)
        assert any(i["code"] == "resolution_too_small" for i in report["issues"])

    def test_blackdetect_flags_black_frames(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import quality_check as qc

        def impl(cmd):
            streams = [{"codec_type": "video", "width": 1080, "height": 1920, "duration": "8.0"}]
            return 0, json.dumps({"streams": streams})

        def fake_bd(video):
            return 0, "[blackdetect @ 0x1] black_start:0 black_end:3.2 black_duration:3.2"

        video = tmp_path / "a.mp4"
        video.write_bytes(b"0" * 32)
        monkeypatch.setattr(qc, "_run_probe", impl)
        monkeypatch.setattr(qc, "_run_blackdetect", fake_bd)
        report = qc.check_asset(video)
        assert report["ok"] is False
        assert any(i["code"] == "black_frames_excess" for i in report["issues"])

    def test_gate_ok_golden_case(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import quality_check as qc

        def impl(cmd):
            streams = [{"codec_type": "video", "width": 1080, "height": 1920, "duration": "8.0"}]
            return 0, json.dumps({"streams": streams})

        def fake_bd(video):
            return 0, "[blackdetect @ 0x1] black_start:0 black_end:0.4 black_duration:0.4"

        video = tmp_path / "a.mp4"
        video.write_bytes(b"0" * 32)
        monkeypatch.setattr(qc, "_run_probe", impl)
        monkeypatch.setattr(qc, "_run_blackdetect", fake_bd)
        report = qc.check_asset(video)
        assert report["ok"] is True and report["issues"] == [] and report["black_fraction"] == 0.05


class TestSelfReviewShots:
    """D2/D3/D4 红测试：LLM 自审薄壳 + ShowAgent 注入 + 发布联检。"""

    def _fake_http(self, monkeypatch, content, *, rc=0, model="aicomic-self-review"):
        from aicomic.core import self_review as sr

        calls: list[dict] = []

        class _Resp:
            status = rc

            def read(self):
                body = json.dumps(
                    {"choices": [{"message": {"content": content}}]}
                ).encode("utf-8")
                return body.encode("utf-8") if False else body

            def close(self):
                pass

        def fake_request(url, data_bytes, headers, timeout):
            calls.append({"url": url, "data": json.loads(data_bytes.decode("utf-8")), "headers": headers})
            return _Resp().read()

        monkeypatch.setattr(sr, "_request", fake_request)
        monkeypatch.setenv("AICOMIC_OPENAI_API_KEY", "test-key")
        return calls

    def test_llm_review_parses_verdict(self, tmp_path, monkeypatch):
        from aicomic.core import self_review as sr

        calls = self._fake_http(monkeypatch, json.dumps({"verdict": "revise", "issues": ["第2镜 黑帧超阈"]}))
        out = sr.review_assets([{"shot_id": "S01", "duration": 8.0}], episode_code="E01")
        assert out["verdict"] == "revise"
        assert out["issues"] == ["第2镜 黑帧超阈"]
        assert out["model"] == "aicomic-self-review"
        req = calls[0]
        assert "chat/completions" in req["url"]
        assert "Authorization" in req["headers"]
        assert "messages" in req["data"]

    def test_llm_error_fail_soft(self, tmp_path, monkeypatch):
        from aicomic.core import self_review as sr

        calls = self._fake_http(monkeypatch, "不是JSON的回复")
        out = sr.review_assets([])
        assert out["verdict"] == "error"

    def test_http_fail_fail_soft(self, tmp_path, monkeypatch):
        from aicomic.core import self_review as sr

        class _Boom(Exception):
            pass

        monkeypatch.setenv("AICOMIC_OPENAI_API_KEY", "test-key")

        def fake_request(url, data_bytes, headers, timeout):
            raise _Boom("connection refused")

        monkeypatch.setattr(sr, "_request", fake_request)
        out = sr.review_assets([{"shot_id": "S01"}])
        assert out["verdict"] == "error"
        assert "connection refused" in out["issues"][0]["message"]


class TestShowAgentSelfReview:
    """D3：preview_render 分发后注入 self_reviewer（fail-soft），结果可读。"""

    def _agent(self, tmp_path, reviewer):
        from aicomic.core.show_agent import ShowAgent
        from aicomic.core.pipeline_coordinator import PipelineCoordinator

        coordinator = PipelineCoordinator(tmp_path)
        # 预推进到 preview_render（scripted：前 7 stage 完成+门前两道已批）
        for sid in ("project_setup", "story_bible", "episode_outline", "tts_subtitle"):
            coordinator.begin_stage("E01", sid)
            coordinator.complete_stage("E01", sid)
        for sid in ("shot_breakdown", "asset_generation"):
            coordinator.begin_stage("E01", sid)
            coordinator.complete_stage("E01", sid)
            coordinator.approve_stage("E01", sid, reviewer="t")
        coordinator.execute_preview_render = lambda ep, plan, out, rp: {"video": "v.mp4"}
        return ShowAgent(state_dir=tmp_path, coordinator=coordinator, self_reviewer=reviewer)

    def test_preview_render_triggers_review(self, tmp_path):
        calls: list[list] = []

        def reviewer(shots):
            calls.append(list(shots))
            return {"verdict": "revise", "issues": ["第2镜 构图失衡"], "model": "m"}

        agent = self._agent(tmp_path, reviewer)
        result = agent.run_until_human(
            "E01", {"preview_render": {"render_plan": {"shots": [{"shot_id": "S01", "image": "x"}]}}}
        )
        assert calls and calls[0][0]["shot_id"] == "S01"
        assert agent.last_self_review["verdict"] == "revise"
        assert result.stop_reason in {"needs_input", "awaiting_human", "all_completed"}

    def test_reviewer_error_fail_soft(self, tmp_path):
        def reviewer(shots):
            raise RuntimeError("boom")

        agent = self._agent(tmp_path, reviewer)
        agent.run_until_human("E01", {"preview_render": {"render_plan": {"shots": [{"shot_id": "S01"}]}}})
        assert agent.last_self_review["verdict"] == "error"
        assert "boom" in agent.last_self_review["issues"][0]["message"]

    def test_no_reviewer_keeps_none(self, tmp_path):
        agent = self._agent(tmp_path, None)
        result = agent.run_until_human("E01", {"preview_render": {"render_plan": {"shots": [{"shot_id": "S01"}]}}})
        assert agent.last_self_review is None
        assert result.stop_reason in {"needs_input", "awaiting_human", "all_completed"}


class TestPublishMetadataGang:
    """D4：发布前 metadata 联检（SOP §10 #7 | #2 shim）——缺 AI 标签拒绝发。"""

    def _cfg(self, tmp_path):
        (tmp_path / "ck").write_text("ck", encoding="utf-8")
        return {
            "platforms": {"douyin": {"enabled": True, "cookie_path": str(tmp_path / "ck")}},
            "social_auto_upload_path": str(tmp_path / "sau"),
        }

    def _payload(self, tmp_path):
        from aicomic.publish.domestic_publisher import PublishPayload

        video = tmp_path / "episode.mp4"
        video.write_bytes(b"0" * 16)
        return PublishPayload(video_path=video, title="T")

    def test_missing_label_blocks(self, tmp_path, monkeypatch):
        from aicomic.publish import domestic_publisher as dp

        monkeypatch.setattr(dp, "ai_label_present", lambda v, **k: False)
        results = dp.publish_to_platforms(self._payload(tmp_path), ["douyin"], self._cfg(tmp_path))
        assert results["douyin"]["success"] is False
        assert "ai_label" in results["douyin"]["error"]

    def test_label_present_allows(self, tmp_path, monkeypatch):
        from aicomic.publish import domestic_publisher as dp

        monkeypatch.setattr(dp, "ai_label_present", lambda v, **k: True)
        monkeypatch.setattr(dp, "_run_sau_upload", lambda *a, **k: {"success": True, "platform": "douyin"})
        results = dp.publish_to_platforms(self._payload(tmp_path), ["douyin"], self._cfg(tmp_path))
        assert results["douyin"]["success"] is True

    def test_require_ai_label_false_opts_out(self, tmp_path, monkeypatch):
        from aicomic.publish import domestic_publisher as dp

        monkeypatch.setattr(dp, "ai_label_present", lambda v, **k: False)
        monkeypatch.setattr(dp, "_run_sau_upload", lambda *a, **k: {"success": True, "platform": "douyin"})
        cfg = self._cfg(tmp_path)
        cfg["require_ai_label"] = False
        results = dp.publish_to_platforms(self._payload(tmp_path), ["douyin"], cfg)
        assert results["douyin"]["success"] is True


class TestQualityFfmpegFallback:
    def test_ffprobe_unavailable_ffmpeg_banner_fallback(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import quality_check as qc

        video = tmp_path / "a.mp4"
        video.write_bytes(b"0" * 32)

        def fake_bd(video_path):
            return 0, "[blackdetect] black_start:0 black_end:0.1 black_duration:0.1"

        def fake_bd_unavailable(video_path):
            return 1, ""

        banner_json = json.dumps(
            {"streams": [{"codec_type": "video", "width": 1080, "height": 1920, "duration": "8.0"}]}
        )

        monkeypatch.setattr(qc, "_run_probe", lambda cmd: (127, ""))  # ffprobe 不可用
        monkeypatch.setattr(qc, "_run_ffmpeg_banner", lambda video_path: (0, banner_json))
        monkeypatch.setattr(qc, "_run_blackdetect", fake_bd)
        report = qc.check_asset(video)
        assert report["ok"] is True and report["issues"] == []
        monkeypatch.setattr(qc, "_run_ffmpeg_banner", lambda video_path: (1, ""))
        report2 = qc.check_asset(video)
        assert any(i["code"] == "probe_unavailable" for i in report2["issues"])
