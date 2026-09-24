"""Tests for video thumbnail extractor."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest


class TestThumbnail:
    def test_extract_no_ffmpeg(self, tmp_path):
        """Should return empty list if ffmpeg unavailable or file missing."""
        from aicomic.video_synthesis.thumbnail import extract_key_frames
        # Nonexistent file — should return empty list, not crash
        results = extract_key_frames(tmp_path / "nope.mp4", tmp_path)
        assert isinstance(results, list)

    def test_extract_nonexistent_video(self, tmp_path):
        from aicomic.video_synthesis.thumbnail import extract_key_frames
        # File doesn't exist — should return empty list
        results = extract_key_frames(tmp_path / "nope.mp4", tmp_path)
        assert isinstance(results, list)
        assert len(results) == 0

    def test_get_duration_no_file(self, tmp_path):
        from aicomic.video_synthesis.thumbnail import _get_duration
        assert _get_duration(tmp_path / "nope.mp4") == 0.0

    def test_build_grid_empty(self, tmp_path):
        from aicomic.video_synthesis.thumbnail import build_thumbnail_grid
        result = build_thumbnail_grid([], tmp_path / "grid.jpg")
        assert result is None

    def test_build_grid_no_pillow(self, tmp_path):
        """If Pillow is available this returns a path; if not, returns None."""
        from aicomic.video_synthesis.thumbnail import build_thumbnail_grid
        # Create a dummy image
        try:
            from PIL import Image
            img = Image.new("RGB", (100, 100), (255, 0, 0))
            thumb = tmp_path / "thumb.jpg"
            img.save(str(thumb))
            result = build_thumbnail_grid([str(thumb)], tmp_path / "grid.jpg")
            assert result is not None
            assert Path(result).exists()
        except ImportError:
            result = build_thumbnail_grid(["fake.jpg"], tmp_path / "grid.jpg")
            assert result is None
