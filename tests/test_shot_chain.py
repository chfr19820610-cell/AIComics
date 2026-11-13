"""镜头承接（尾帧→首帧直拷）测试。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _ffmpeg() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover
        return "ffmpeg"


def _make_video(path: Path, color: str = "red", seconds: float = 1.0) -> bool:
    """用 ffmpeg 生成一段纯色测试视频；不可用环境跳过。"""
    cmd = [
        _ffmpeg(), "-y", "-f", "lavfi", "-i", f"color=c={color}:s=320x240:d={seconds}",
        "-pix_fmt", "yuv420p", str(path),
    ]
    try:
        rc = subprocess.run(cmd, capture_output=True, text=True).returncode
    except OSError:
        return False
    return rc == 0 and path.is_file() and path.stat().st_size > 0


@pytest.fixture()
def video(tmp_path):
    p = tmp_path / "clip.mp4"
    if not _make_video(p):
        pytest.skip("ffmpeg 不可用，跳过承接测试")
    return p


class TestExtractFrames:
    def test_extract_last_frame(self, video, tmp_path):
        from aicomic.core.shot_chain import extract_last_frame

        out = tmp_path / "last.png"
        r = extract_last_frame(video, out)
        assert r["ok"] is True
        assert out.is_file() and out.stat().st_size > 0
        assert r["bytes"] == out.stat().st_size

    def test_extract_first_frame(self, video, tmp_path):
        from aicomic.core.shot_chain import extract_first_frame

        out = tmp_path / "first.png"
        r = extract_first_frame(video, out)
        assert r["ok"] is True
        assert out.is_file()

    def test_missing_video_structured_error(self, tmp_path):
        from aicomic.core.shot_chain import extract_last_frame

        r = extract_last_frame(tmp_path / "nope.mp4", tmp_path / "x.png")
        assert r["ok"] is False
        assert "not found" in r["error"]


class TestCarryLastFrame:
    def test_carry_produces_frame(self, video, tmp_path):
        from aicomic.core.shot_chain import carry_last_frame

        target = tmp_path / "S02_start.png"
        r = carry_last_frame(video, target)
        assert r["ok"] is True
        assert target.is_file()
        assert r["source"] == str(video)
        assert r["target"] == str(target)

    def test_creates_parent_dirs(self, video, tmp_path):
        from aicomic.core.shot_chain import carry_last_frame

        target = tmp_path / "deep" / "nested" / "S02_start.png"
        r = carry_last_frame(video, target)
        assert r["ok"] is True
        assert target.is_file()


class TestChainShots:
    def test_chain_three_shots(self, tmp_path):
        from aicomic.core.shot_chain import chain_shots

        vids = []
        for i, color in enumerate(["red", "green", "blue"]):
            p = tmp_path / f"S{i+1:02d}.mp4"
            if not _make_video(p, color):
                pytest.skip("ffmpeg 不可用")
            vids.append(p)
        out = tmp_path / "starts"
        r = chain_shots(vids, out)
        assert r["ok"] is True
        assert r["chain_count"] == 2  # 3 个镜头 → 2 条承接
        assert r["failed_count"] == 0
        assert (out / "S02_start.png").is_file()
        assert (out / "S03_start.png").is_file()

    def test_single_shot_no_chain(self, video, tmp_path):
        from aicomic.core.shot_chain import chain_shots

        r = chain_shots([video], tmp_path / "starts")
        assert r["ok"] is True
        assert r["chain_count"] == 0
        assert r["chains"] == []

    def test_missing_source_reports_failure(self, tmp_path):
        from aicomic.core.shot_chain import chain_shots

        r = chain_shots([tmp_path / "a.mp4", tmp_path / "b.mp4"], tmp_path / "starts")
        assert r["ok"] is False
        assert r["failed_count"] == 1
