"""render.subtitle_burn：PIL 字幕条/卡渲染 + overlay 烧制（绕开 fontconfig 框框坑）。"""
from pathlib import Path

import numpy as np
from PIL import Image


class TestFontStack:
    def test_chinese_mask_not_blank(self):
        """中文字 mask 必须 non-blank（tofu/缺字时 mask 接近空）。"""
        from aicomic.render.subtitle_burn import load_cjk_font

        font = load_cjk_font(26)
        mask = font.getmask("字幕测试")
        arr = np.asarray(mask, dtype=np.uint8).reshape(mask.size[1], mask.size[0])
        assert (arr > 100).sum() > 200, f"mask 太稀：{(arr > 100).sum()}"

    def test_missing_font_raises(self, monkeypatch):
        from aicomic.render import subtitle_burn as sb

        monkeypatch.setattr(sb, "_FONT_CANDIDATES", ["/nonexistent/font.ttc"])
        try:
            sb.load_cjk_font(26)
            raise AssertionError("should raise")
        except (FileNotFoundError, OSError):
            pass


class TestSubtitleBar:
    def test_render_bar(self, tmp_path):
        from aicomic.render.subtitle_burn import render_subtitle_bar

        out = tmp_path / "bar.png"
        render_subtitle_bar("测试字幕条", width=448, output=out)
        im = Image.open(out)
        arr = np.asarray(im.convert("L"))
        white = int((arr > 180).sum())
        assert white > 200, f"白色像素太少 {white}"
        assert im.size[0] == 448

    def test_bar_centered(self, tmp_path):
        from aicomic.render.subtitle_burn import render_subtitle_bar

        out = tmp_path / "bar.png"
        render_subtitle_bar("居中", width=448, output=out)
        arr = np.asarray(Image.open(out).convert("L"))
        ys, xs = np.where(arr > 180)
        assert 100 < xs.mean() < 348, f"x 中心 {xs.mean()}"


class TestBurnSubtitle:
    def test_burn_invokes_overlay(self, tmp_path, monkeypatch):
        from aicomic.render import subtitle_burn as sb

        bar = tmp_path / "bar.png"
        sb.render_subtitle_bar("字幕", output=bar)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 16)
        calls: list[list[str]] = []
        monkeypatch.setattr(sb, "_run_ffmpeg", lambda cmd: calls.append(list(cmd)) or 0)
        out = tmp_path / "v_sub.mp4"
        rc = sb.burn_subtitle(video, bar, output=out)
        assert rc == 0
        joined = " ".join(calls[0])
        assert "overlay" in joined
        assert str(video) in joined and str(bar) in joined

    def test_burn_failure_structured(self, tmp_path, monkeypatch):
        from aicomic.render import subtitle_burn as sb

        bar = tmp_path / "bar.png"
        sb.render_subtitle_bar("字幕", output=bar)
        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 16)
        monkeypatch.setattr(sb, "_run_ffmpeg", lambda cmd: 33)
        out = tmp_path / "v_sub.mp4"
        rc = sb.burn_subtitle(video, bar, output=out)
        assert rc == 33
