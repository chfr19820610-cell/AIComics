"""AI 合规标识统一测试（SOP §10 #7 合规四向联测）。"""
from __future__ import annotations

import json
from pathlib import Path


def _stub_probe_video(tmp_path) -> Path:
    video = tmp_path / "dummy.mp4"
    video.write_bytes(b"0" * 64)
    return video


class TestEmbedAiLabel:
    def test_remux_carries_metadata_tags(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 64)
        recorded: list[list[str]] = []

        def fake_ffmpeg(cmd):
            recorded.append(cmd)
            Path(cmd[-1]).write_bytes(b"1" * 32)  # 模拟 ffmpeg 产出 tmp 输出
            return 0

        monkeypatch.setattr(ai, "_run_ffmpeg", fake_ffmpeg)
        out = ai.embed_ai_label(video, tmp_path / "out.mp4")
        cmd = recorded[0]
        assert out.name == "out.mp4"
        for frag in ("-c", "copy", "-map_metadata", "0", "-movflags", "use_metadata_tags+faststart"):
            assert frag in cmd, frag
        for tag in ("ai_generated=true", "ai_generator=AIComics"):
            assert tag in cmd
        assert "comment=" in " ".join(cmd)

    def test_missing_input_raises(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        try:
            ai.embed_ai_label(tmp_path / "nope.mp4")
        except (RuntimeError, FileNotFoundError) as exc:
            assert "不存在" in str(exc)
        else:
            raise AssertionError("应 raise：文件不存在必须显式失败")

    def test_watermark_mode_uses_drawtext(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 64)
        recorded: list[list[str]] = []

        def fake_ffmpeg(cmd):
            recorded.append(cmd)
            Path(cmd[-1]).write_bytes(b"1" * 32)  # 模拟 ffmpeg 产出 tmp 输出
            return 0

        monkeypatch.setattr(ai, "_run_ffmpeg", fake_ffmpeg)
        ai.embed_ai_label(video, watermark=True)
        assert "drawtext" in " ".join(recorded[0]) and "-vf" in recorded[0]

    def test_video_passthrough_default(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 64)
        recorded: list[list[str]] = []

        def fake_ffmpeg(cmd):
            recorded.append(cmd)
            Path(cmd[-1]).write_bytes(b"1" * 32)  # 模拟 ffmpeg 产出 tmp 输出
            return 0

        monkeypatch.setattr(ai, "_run_ffmpeg", fake_ffmpeg)
        result_path = ai.embed_ai_label(video)
        assert result_path == video.resolve() or result_path == video


class TestAiLabelPresent:
    def test_tags_and_negatives(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        def fake_probe(cmd):
            return 0, json.dumps({"format": {"tags": {"ai_generated": "true"}}})

        monkeypatch.setattr(ai, "_run_probe", fake_probe)
        assert ai.ai_label_present(_stub_probe_video(tmp_path)) is True

        monkeypatch.setattr(ai, "_run_probe", lambda cmd: (1, ""))
        assert ai.ai_label_present(_stub_probe_video(tmp_path)) is False

    def test_ffprobe_unavailable_ffmetadata_fallback(self, tmp_path, monkeypatch):
        import aicomic.video_synthesis.ai_label as ai

        cmds: list[list[str]] = []

        def fake_probe(cmd):
            cmds.append(cmd)
            if "ffmetadata" in cmd:
                return 0, ";FFMETADATA1\ncomment=xAiComics\nai_generated=true\n"
            return 127, ""  # ffprobe ENOENT/坏架构

        monkeypatch.setattr(ai, "_run_probe", fake_probe)
        assert ai.ai_label_present(_stub_probe_video(tmp_path)) is True
        assert len(cmds) == 2 and any("ffmetadata" in c for c in cmds)

        def fake_probe_missing(cmd):
            cmds.append(cmd)
            if "ffmetadata" in cmd:
                return 0, ";FFMETADATA1\ncomment=别的\n"
            return 127, ""

        cmds.clear()
        monkeypatch.setattr(ai, "_run_probe", fake_probe_missing)
        assert ai.ai_label_present(_stub_probe_video(tmp_path)) is False

        assert ai.ai_label_present(tmp_path / "missing.mp4") is False
