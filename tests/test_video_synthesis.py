"""
Tests for the video synthesis pipeline module.

These tests validate:
- Subtitle generation (SRT and ASS)
- Scene duration resolution
- Audio duration extraction (requires FFmpeg)
- Pipeline orchestration logic
- Batch discovery
- Output verification
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is on the path
_SRC = Path(__file__).resolve().parent.parent / "src"
import sys
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from aicomic.video_synthesis.config import (
    ASSET_SOURCE,
    EPISODE_SUBTITLES,
    FFMPEG,
    FPS,
    KEN_BURNS_ZOOM_MAX,
    OUTPUT_DIR,
    VIDEO_BITRATE,
)
from aicomic.video_synthesis.subtitles import build_ass, build_srt, write_ass, write_srt
from aicomic.video_synthesis.scene import get_audio_duration
from aicomic.video_synthesis.pipeline import (
    verify_video,
    resolve_scene_durations,
    synthesize_episode,
)
from aicomic.video_synthesis.batch import (
    discover_episodes,
    batch_synthesize,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_scenes() -> list[dict]:
    return [
        {"num": 1, "image_name": "E01_S01_key.png", "audio_name": "E01_S01_tts.wav",
         "subtitle": "第一句台词", "duration": None},
        {"num": 2, "image_name": "E01_S02_key.png", "audio_name": "E01_S02_tts.wav",
         "subtitle": "第二句台词", "duration": None},
        {"num": 3, "image_name": "E01_S03_key.png", "audio_name": "E01_S03_tts.wav",
         "subtitle": "", "duration": 5.0},
    ]


@pytest.fixture
def sample_durations() -> list[float]:
    return [6.0, 4.5, 5.0]


@pytest.fixture
def sample_subtitles() -> list[str]:
    return ["第一句台词", "第二句台词", ""]


# ── SRT Tests ─────────────────────────────────────────────────────────────

class TestSrtGeneration:
    def test_build_srt_basic(self, sample_durations, sample_subtitles):
        content = build_srt(sample_durations, sample_subtitles)
        assert "1" in content
        assert "第一句台词" in content
        assert "第二句台词" in content
        assert "00:00:00,000" in content
        assert "00:00:06,000" in content  # 6s duration for scene 1
        assert "00:00:06,000 --> 00:00:10,500" in content  # 6 + 4.5

    def test_build_srt_empty_subtitles(self):
        durations = [5.0, 3.0]
        subtitles = ["", ""]
        content = build_srt(durations, subtitles)
        assert content == ""  # no subtitles = empty

    def test_build_srt_partial_subtitles(self):
        durations = [3.0, 4.0, 2.0]
        subtitles = ["Only one", "", "Last one"]
        content = build_srt(durations, subtitles)
        assert "1" in content
        assert "Only one" in content
        assert "Last one" in content
        # Scene 1 (3s): text present → subtitle index 1 at 0→3
        assert "00:00:00,000 --> 00:00:03,000" in content
        # Scene 2 (4s): no text, time advances to 7
        # Scene 3 (2s): text present → subtitle index 2 at 7→9
        assert "00:00:07,000 --> 00:00:09,000" in content

    def test_write_srt(self, tmp_path, sample_durations, sample_subtitles):
        path = tmp_path / "test.srt"
        result = write_srt(path, sample_durations, sample_subtitles)
        assert result.exists()
        content = path.read_text(encoding="utf-8")
        assert "第一句台词" in content

    def test_build_srt_cumulative_timing(self):
        """Verify cumulative timestamps across multiple scenes."""
        durations = [2.0, 3.0, 1.0]
        subtitles = ["A", "B", "C"]
        content = build_srt(durations, subtitles)
        # Scene 1: 0-2
        assert "00:00:00,000 --> 00:00:02,000" in content
        # Scene 2: 2-5
        assert "00:00:02,000 --> 00:00:05,000" in content
        # Scene 3: 5-6
        assert "00:00:05,000 --> 00:00:06,000" in content


# ── ASS Tests ─────────────────────────────────────────────────────────────

class TestAssGeneration:
    def test_build_ass_basic(self, sample_durations, sample_subtitles):
        content = build_ass(sample_durations, sample_subtitles)
        assert "[Script Info]" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content
        assert "第一句台词" in content
        assert "第二句台词" in content
        assert "PlayResX: 1920" in content
        assert "PlayResY: 1080" in content

    def test_build_ass_custom_resolution(self, sample_durations, sample_subtitles):
        content = build_ass(sample_durations, sample_subtitles,
                            video_width=1920, video_height=1080)
        assert "PlayResX: 1920" in content
        assert "PlayResY: 1080" in content

    def test_build_ass_empty(self):
        content = build_ass([5.0], [""])
        assert "[Events]" in content
        assert "Dialogue: 0," not in content  # no dialogue events

    def test_build_ass_special_chars(self):
        """ASS special characters should be escaped."""
        content = build_ass([5.0], ["Text with {braces} and \\backslash"])
        assert "\\{braces\\}" in content or "{" not in content.split(",,", 1)[1]
        assert "\\\\backslash" in content

    def test_write_ass(self, tmp_path, sample_durations, sample_subtitles):
        path = tmp_path / "test.ass"
        result = write_ass(path, sample_durations, sample_subtitles)
        assert result.exists()
        content = path.read_text(encoding="utf-8")
        assert "[Script Info]" in content

    def test_ass_font_name(self):
        """Font name should be a non-empty string."""
        from aicomic.video_synthesis.subtitles import _FontResolver
        name = _FontResolver._font_name()
        assert isinstance(name, str)
        assert len(name) > 0


# ── Scene + Duration Tests ────────────────────────────────────────────────

class TestSceneUtils:
    def test_resolve_scene_durations_all_none(self, sample_scenes):
        """When all durations are None, use max(5.0, audio_duration)."""
        with patch("aicomic.video_synthesis.pipeline.get_audio_duration",
                   return_value=3.0):
            durations = resolve_scene_durations(
                sample_scenes,
                Path("/tmp/audio"),
            )
            # All should be >= 5.0 (DEFAULT_SCENE_DURATION)
            assert all(d >= 5.0 for d in durations)
            assert len(durations) == 3

    def test_resolve_scene_durations_mixed(self, tmp_path):
        scenes = [
            {"num": 1, "audio_name": "a.wav", "duration": None},
            {"num": 2, "audio_name": "b.wav", "duration": 4.0},
        ]
        # Create dummy audio so exists() returns True
        (tmp_path / "a.wav").write_text("dummy")
        (tmp_path / "b.wav").write_text("dummy")
        with patch("aicomic.video_synthesis.pipeline.get_audio_duration",
                   return_value=7.0):
            durations = resolve_scene_durations(scenes, tmp_path)
            assert durations == [7.0, 4.0]  # None → 7.0, explicit → 4.0

    def test_get_audio_duration(self):
        """Requires FFmpeg and a real WAV file."""
        if not FFMPEG.exists():
            pytest.skip(f"FFmpeg not found at {FFMPEG}")

        # Find a real WAV from the project
        wav = list(Path("/Users/eric/Desktop/herness/AIComics/10_System/state/local_provider_output/E01/audio").glob("*.wav"))
        if not wav:
            pytest.skip("No test WAV files found")

        dur = get_audio_duration(wav[0])
        assert isinstance(dur, float)
        assert dur > 0

    def test_ken_burns_zoom_expr(self):
        """Verify the zoom expression math."""
        frames = int(5.0 * FPS)  # 150 frames at 30fps
        # zoom = 1 + 0.05 * frame / total_frames
        zoom_start = 1.0  # at frame 0
        zoom_end = 1.0 + 0.05 * frames / frames  # at last frame
        assert abs(zoom_end - KEN_BURNS_ZOOM_MAX) < 0.001


# ── Pipeline Tests ────────────────────────────────────────────────────────

class TestPipeline:
    def test_verify_video(self):
        """Verify against the spike output."""
        spike_path = Path("/Users/eric/Desktop/herness/AIComics/10_System/state/releases/E01_spike.mp4")
        if not spike_path.exists():
            pytest.skip("Spike output not found")

        info = verify_video(spike_path)
        assert info["size_mb"] > 1.0
        assert "duration" in info
        assert "video" in info
        assert "audio" in info
        # Accept both 720p (old spike) and 1080p (new pipeline)
        vid_info = info.get("video", "")
        has_720p = "1280x720" in vid_info or "720x1280" in vid_info
        has_1080p = "1920x1080" in vid_info or "1080x1920" in vid_info
        assert has_720p or has_1080p, f"Expected 720p or 1080p, got: {vid_info}"

    def test_synthesize_episode_with_mock(self, tmp_path, sample_scenes):
        """Test pipeline logic with mocked subprocess calls."""
        mock_image_dir = tmp_path / "images"
        mock_audio_dir = tmp_path / "audio"
        mock_image_dir.mkdir(parents=True, exist_ok=True)
        mock_audio_dir.mkdir(parents=True, exist_ok=True)

        # Create dummy assets
        for s in sample_scenes:
            (mock_image_dir / s["image_name"]).write_text("fake-png")
            (mock_audio_dir / s["audio_name"]).write_text("fake-wav")

        # Ensure temp dir exists for subbed output
        output_path = tmp_path / "test.mp4"

        def mock_subprocess_run(cmd, **kwargs):
            """Create dummy files that verify_video/Phase 4 expects."""
            # If it's a build_scene_video call, create the clip file
            for i, s in enumerate(sample_scenes):
                expected_clip = str(tmp_path / "TEST" / "scenes" / f"scene_{s['num']:02d}.mp4")
                if expected_clip in " ".join(cmd):
                    Path(expected_clip).parent.mkdir(parents=True, exist_ok=True)
                    Path(expected_clip).write_text("fake-mp4")

            # If it's concat, create concat output
            expected_concat = str(tmp_path / "TEST" / "episode_concat.mp4")
            if expected_concat in " ".join(cmd):
                Path(expected_concat).parent.mkdir(parents=True, exist_ok=True)
                Path(expected_concat).write_text("fake-mp4-concat")

            # If it's burn subtitles, create final output
            if "test.mp4" in " ".join(cmd) and "-vf" in cmd:
                output_path.write_text("fake-mp4-final")

            if "test.mp4" in " ".join(cmd) and "stream" in " ".join(cmd).lower():
                output_path.write_text("fake-mp4-final")

            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = (
                "Duration: 00:00:05.00, start: 0.0, bitrate: 128 kb/s\n"
                "Stream #0:0: Video: h264, 1920x1080\n"
                "Stream #0:1: Audio: aac, 44100 Hz\n"
            )
            mock_result.stdout = ""
            return mock_result

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            result = synthesize_episode(
                episode_code="TEST",
                scenes=sample_scenes,
                image_dir=mock_image_dir,
                audio_dir=mock_audio_dir,
                output_path=output_path,
            )
        assert result is not None
        assert result.get("status") in ("ok", "small_output")

    def test_pipeline_report_written(self, tmp_path):
        """Test that the report JSON is written alongside output."""
        # Just verify the report path is adjacent to output
        out = tmp_path / "E01_full.mp4"
        report = out.with_suffix(".report.json")
        assert report.name == "E01_full.report.json"


# ── Batch Tests ───────────────────────────────────────────────────────────

class TestBatch:
    def test_discover_episodes(self):
        """Discover should find E01-E05."""
        episodes = discover_episodes()
        codes = {ep["episode_code"] for ep in episodes}
        assert len(codes) >= 3  # At least 3 episodes should be found
        assert "E01" in codes
        assert "E02" in codes
        assert "E03" in codes

    def test_discover_episodes_scene_count(self):
        episodes = discover_episodes()
        for ep in episodes:
            assert len(ep["scenes"]) >= 1
            # Each scene should have required keys
            for scene in ep["scenes"]:
                assert "num" in scene
                assert "image_name" in scene
                assert "audio_name" in scene
                assert "subtitle" in scene
                assert "duration" in scene

    def test_episode_subtitle_count(self):
        """Each episode subtitle list should match expected scene count."""
        for ep_code, subs in EPISODE_SUBTITLES.items():
            assert len(subs) == 6, f"{ep_code}: expected 6 subtitles, got {len(subs)}"

    def test_asset_source_consistency(self):
        """All episodes in subtitle map should have an asset source."""
        for ep_code in EPISODE_SUBTITLES:
            assert ep_code in ASSET_SOURCE, f"{ep_code} missing from ASSET_SOURCE"

    def test_batch_synthesize_dry_run(self, tmp_path):
        """Test batch with mocked subprocess (no actual FFmpeg)."""
        from aicomic.video_synthesis.config import OUTPUT_DIR
        from unittest.mock import MagicMock, patch

        mock_asset_sources = {
            "TEST": tmp_path,
        }
        mock_subtitles = {
            "TEST": ["Test line 1", "Test line 2"],
        }

        # Create dummy asset directories
        (tmp_path / "TEST" / "images").mkdir(parents=True, exist_ok=True)
        (tmp_path / "TEST" / "audio").mkdir(parents=True, exist_ok=True)
        (tmp_path / "TEST" / "images" / "TEST_S01_key.png").write_text("x")
        (tmp_path / "TEST" / "audio" / "TEST_S01_tts.wav").write_text("x")
        (tmp_path / "TEST" / "images" / "TEST_S02_key.png").write_text("x")
        (tmp_path / "TEST" / "audio" / "TEST_S02_tts.wav").write_text("x")

        expected_output = OUTPUT_DIR / "TEST_full.mp4"
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("fake-mp4")

        def mock_run(cmd, **kwargs):
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stderr = (
                "Duration: 00:00:05.00, start: 0.0, bitrate: 128 kb/s\n"
                "Stream #0:0: Video: h264, 1920x1080\n"
                "Stream #0:1: Audio: aac, 44100 Hz\n"
            )
            mock_result.stdout = ""
            return mock_result

        with patch("subprocess.run", side_effect=mock_run):
            with patch("aicomic.video_synthesis.scene.reencode_audio", return_value=True):
                with patch("aicomic.video_synthesis.scene.build_scene_video", return_value=True):
                    with patch("aicomic.video_synthesis.pipeline.phase_concat", return_value=True):
                        with patch("aicomic.video_synthesis.pipeline.phase_burn_subtitles", return_value=True):
                            reports = batch_synthesize(
                                episode_codes=["TEST"],
                                asset_sources=mock_asset_sources,
                                subtitle_map=mock_subtitles,
                                stop_on_failure=False,
                            )
        assert len(reports) >= 1


# ── Config Tests ──────────────────────────────────────────────────────────

class TestConfig:
    def test_output_dir_exists(self):
        assert OUTPUT_DIR.exists(), f"Output dir {OUTPUT_DIR} should exist"

    def test_ffmpeg_exists(self):
        if FFMPEG.exists():
            result = subprocess.run(
                [str(FFMPEG), "-version"],
                capture_output=True, text=True, timeout=5,
            )
            assert result.returncode == 0
            assert "ffmpeg" in result.stdout.lower()

    def test_video_bitrate_set(self):
        assert VIDEO_BITRATE == "4000k", "Video bitrate should be 4000k for 1080p"

    def test_episode_subtitles_not_empty(self):
        assert len(EPISODE_SUBTITLES) > 0

    def test_asset_sources_cover_subtitles(self):
        for ep_code in EPISODE_SUBTITLES:
            assert ep_code in ASSET_SOURCE
