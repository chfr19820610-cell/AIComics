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
