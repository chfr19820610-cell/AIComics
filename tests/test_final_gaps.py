"""Tests for final ROADMAP gaps — epub support, batch publish, multilang→platform routing."""
from __future__ import annotations

from pathlib import Path

import pytest


# === ② epub 格式支持 ===

class TestEpubSupport:
    def test_import_epub_exists(self):
        from aicomic.core.novel_pipeline import import_novel_file
        assert callable(import_novel_file)

    def test_import_txt(self, tmp_path):
        from aicomic.core.novel_pipeline import import_novel_file
        f = tmp_path / "novel.txt"
        f.write_text("第一章 测试\n这是测试内容。", encoding="utf-8")
        result = import_novel_file(f)
        assert "episodes" in result
        assert result["episode_count"] >= 0

    def test_import_md(self, tmp_path):
        from aicomic.core.novel_pipeline import import_novel_file
        f = tmp_path / "novel.md"
        f.write_text("# 第一章 测试\n\n这是测试内容。", encoding="utf-8")
        result = import_novel_file(f)
        assert "episodes" in result

    def test_import_epub_format(self, tmp_path):
        """epub is a zip — test that import_novel_file detects .epub and handles it."""
        from aicomic.core.novel_pipeline import import_novel_file
        import zipfile
        epub_path = tmp_path / "novel.epub"
        with zipfile.ZipFile(epub_path, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("OEBPS/content.opf", '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf"/>')
            zf.writestr("OEBPS/chapter1.xhtml",
                        '<html xmlns="http://www.w3.org/1999/xhtml"><body>'
                        '<h1>第一章 测试</h1><p>这是测试内容。</p></body></html>')
        result = import_novel_file(epub_path)
        assert "episodes" in result

    def test_unsupported_format_raises(self, tmp_path):
        from aicomic.core.novel_pipeline import import_novel_file
        f = tmp_path / "novel.pdf"
        f.write_text("not a real pdf")
        with pytest.raises(ValueError, match="unsupported"):
            import_novel_file(f)


# === ② 批量发布 ===

class TestBatchPublish:
    def test_publish_batch_exists(self):
        from aicomic.publish.domestic_publisher import publish_batch
        assert callable(publish_batch)

    def test_publish_batch_returns_per_episode_results(self, tmp_path):
        from aicomic.publish.domestic_publisher import publish_batch
        # Create fake video files
        videos = []
        for i in range(3):
            v = tmp_path / f"E0{i+1}.mp4"
            v.write_bytes(b"fake")
            videos.append(v)
        result = publish_batch(
            videos=videos,
            platforms=["douyin"],
            config={"platforms": {"douyin": {"enabled": True, "cookie_path": str(tmp_path / "douyin.json")}}},
        )
        assert len(result) == 3
        for ep_result in result:
            assert "douyin" in ep_result

    def test_publish_batch_skips_disabled(self, tmp_path):
        from aicomic.publish.domestic_publisher import publish_batch
        v = tmp_path / "E01.mp4"
        v.write_bytes(b"fake")
        result = publish_batch(
            videos=[v],
            platforms=["douyin"],
            config={"platforms": {"douyin": {"enabled": False}}},
        )
        assert result[0]["douyin"]["success"] is False


# === ③ 多语言→平台地区路由 ===

class TestMultilangPlatformRouting:
    def test_lang_to_platform_map_exists(self):
        from aicomic.video_synthesis.i18n import get_lang_to_platform_map
        assert callable(get_lang_to_platform_map)

    def test_zh_routes_to_domestic(self):
        from aicomic.video_synthesis.i18n import get_lang_to_platform_map
        m = get_lang_to_platform_map()
        assert "zh" in m
        assert "douyin" in m["zh"] or "xiaohongshu" in m["zh"]

    def test_en_routes_to_international(self):
        from aicomic.video_synthesis.i18n import get_lang_to_platform_map
        m = get_lang_to_platform_map()
        assert "en" in m
        assert "youtube" in m["en"] or "tiktok" in m["en"]

    def test_ja_routes_to_tiktok(self):
        from aicomic.video_synthesis.i18n import get_lang_to_platform_map
        m = get_lang_to_platform_map()
        assert "ja" in m
        assert "tiktok" in m["ja"] or "youtube" in m["ja"]

    def test_publish_multilang_routing_exists(self):
        from aicomic.video_synthesis.i18n import publish_multilang_routing
        assert callable(publish_multilang_routing)

    def test_multilang_routing_returns_per_lang_platform(self):
        from aicomic.video_synthesis.i18n import publish_multilang_routing
        result = publish_multilang_routing(languages=["zh", "en", "ja"])
        assert "zh" in result
        assert "en" in result
        assert "ja" in result
        for lang, platforms in result.items():
            assert isinstance(platforms, list)
            assert len(platforms) > 0
