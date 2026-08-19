"""Phase 3+ tests — 定时发布 + 数据回收 + 翻译记忆库 + SaaS API key + 模板市场在线浏览."""
from __future__ import annotations

from pathlib import Path

import pytest


# === ④ 定时发布 + 数据回收 ===

class TestScheduledPublish:
    def test_create_scheduled_task(self):
        """Should create a scheduled publish task with datetime."""
        from aicomic.publish.publish_scheduler import create_scheduled_task, ScheduledTask
        task = create_scheduled_task(
            video_path="/tmp/v.mp4",
            platforms=["douyin", "bilibili"],
            scheduled_at="2026-08-20T18:00:00",
            title="定时发布测试",
        )
        assert isinstance(task, ScheduledTask)
        assert task.platforms == ["douyin", "bilibili"]
        assert task.scheduled_at == "2026-08-20T18:00:00"
        assert task.status == "pending"

    def test_list_pending_tasks(self, tmp_path):
        from aicomic.publish.publish_scheduler import create_scheduled_task, list_pending_tasks, save_tasks
        tasks = [
            create_scheduled_task("/tmp/v1.mp4", ["douyin"], "2026-08-20T18:00:00", "t1"),
            create_scheduled_task("/tmp/v2.mp4", ["bilibili"], "2026-08-21T12:00:00", "t2"),
        ]
        save_tasks(tasks, tmp_path / "scheduled.json")
        loaded = list_pending_tasks(tmp_path / "scheduled.json")
        assert len(loaded) == 2
        assert all(t.status == "pending" for t in loaded)

    def test_mark_task_done(self, tmp_path):
        from aicomic.publish.publish_scheduler import create_scheduled_task, save_tasks, mark_task_done, load_tasks
        task = create_scheduled_task("/tmp/v.mp4", ["douyin"], "2026-08-20T18:00:00", "t1")
        save_tasks([task], tmp_path / "scheduled.json")
        mark_task_done(tmp_path / "scheduled.json", task.task_id)
        loaded = load_tasks(tmp_path / "scheduled.json")
        assert loaded[0].status == "done"


class TestPublishAnalytics:
    def test_create_analytics_record(self):
        from aicomic.publish.publish_analytics import AnalyticsRecord, create_analytics_record
        rec = create_analytics_record(
            platform="douyin",
            video_id="vid123",
            title="测试视频",
        )
        assert isinstance(rec, AnalyticsRecord)
        assert rec.platform == "douyin"
        assert rec.views == 0
        assert rec.likes == 0

    def test_update_analytics(self, tmp_path):
        from aicomic.publish.publish_analytics import create_analytics_record, save_analytics, update_analytics, load_analytics
        rec = create_analytics_record("douyin", "vid123", "测试")
        save_analytics([rec], tmp_path / "analytics.json")
        update_analytics(tmp_path / "analytics.json", "vid123", views=1000, likes=50, comments=10)
        loaded = load_analytics(tmp_path / "analytics.json")
        assert loaded[0].views == 1000
        assert loaded[0].likes == 50
        assert loaded[0].comments == 10

    def test_analytics_summary(self, tmp_path):
        from aicomic.publish.publish_analytics import create_analytics_record, save_analytics, get_summary
        recs = [
            create_analytics_record("douyin", "v1", "t1"),
            create_analytics_record("bilibili", "v2", "t2"),
        ]
        recs[0].views = 500
        recs[1].views = 300
        save_analytics(recs, tmp_path / "analytics.json")
        summary = get_summary(tmp_path / "analytics.json")
        assert summary["total_views"] == 800
        assert summary["total_videos"] == 2


# === ③ 翻译记忆库 ===

class TestTranslationMemory:
    def test_add_term(self, tmp_path):
        from aicomic.video_synthesis.translation_memory import TranslationMemory
        tm = TranslationMemory(tmp_path / "tm.json")
        tm.add_term("井口", "well opening", lang="en")
        assert tm.lookup("井口", "en") == "well opening"

    def test_lookup_missing_returns_none(self, tmp_path):
        from aicomic.video_synthesis.translation_memory import TranslationMemory
        tm = TranslationMemory(tmp_path / "tm.json")
        assert tm.lookup("不存在的词", "en") is None

    def test_add_and_lookup_multiple_languages(self, tmp_path):
        from aicomic.video_synthesis.translation_memory import TranslationMemory
        tm = TranslationMemory(tmp_path / "tm.json")
        tm.add_term("回头", "look back", lang="en")
        tm.add_term("回头", "振り返る", lang="ja")
        assert tm.lookup("回头", "en") == "look back"
        assert tm.lookup("回头", "ja") == "振り返る"

    def test_persist_and_reload(self, tmp_path):
        from aicomic.video_synthesis.translation_memory import TranslationMemory
        tm = TranslationMemory(tmp_path / "tm.json")
        tm.add_term("禁忌", "taboo", lang="en")
        # Reload
        tm2 = TranslationMemory(tmp_path / "tm.json")
        assert tm2.lookup("禁忌", "en") == "taboo"

    def test_apply_to_entries(self, tmp_path):
        from aicomic.video_synthesis.translation_memory import TranslationMemory
        tm = TranslationMemory(tmp_path / "tm.json")
        tm.add_term("井口", "well opening", lang="en")
        entries = [
            {"index": 1, "start": 0, "end": 3, "text": "井口有声音"},
        ]
        result = tm.apply_to_entries(entries, lang="en")
        assert "well opening" in result[0]["text"]


# === ⑤ SaaS API key ===

class TestAPIKeySystem:
    def test_generate_api_key(self):
        from aicomic.providers.saas_api_key import generate_api_key
        key = generate_api_key()
        assert key.startswith("aic_")
        assert len(key) > 20

    def test_validate_api_key(self, tmp_path):
        from aicomic.providers.saas_api_key import APIKeyManager
        mgr = APIKeyManager(tmp_path / "keys.json")
        key = mgr.create_key(tenant="tenant1", plan="free")
        assert mgr.validate(key) is True
        assert mgr.validate("aic_invalid") is False

    def test_revoke_api_key(self, tmp_path):
        from aicomic.providers.saas_api_key import APIKeyManager
        mgr = APIKeyManager(tmp_path / "keys.json")
        key = mgr.create_key(tenant="tenant1", plan="free")
        mgr.revoke(key)
        assert mgr.validate(key) is False

    def test_tenant_isolation(self, tmp_path):
        from aicomic.providers.saas_api_key import APIKeyManager
        mgr = APIKeyManager(tmp_path / "keys.json")
        key1 = mgr.create_key(tenant="t1", plan="free")
        key2 = mgr.create_key(tenant="t2", plan="pro")
        info1 = mgr.get_tenant(key1)
        info2 = mgr.get_tenant(key2)
        assert info1["tenant"] == "t1"
        assert info2["tenant"] == "t2"
        assert info1 != info2


# === ⑥ 模板市场在线浏览 ===

class TestTemplateMarketBrowse:
    def test_browse_all_templates(self):
        from aicomic.core.template_market import browse_templates
        result = browse_templates()
        assert "templates" in result
        assert len(result["templates"]) >= 6
        for t in result["templates"]:
            assert "id" in t
            assert "genre" in t
            assert "acts_count" in t
            assert "locations_count" in t

    def test_browse_with_genre_filter(self):
        from aicomic.core.template_market import browse_templates
        result = browse_templates(genre="恐怖")
        assert len(result["templates"]) == 1
        assert result["templates"][0]["id"] == "horror"

    def test_preview_template(self):
        from aicomic.core.template_market import preview_template
        preview = preview_template("horror")
        assert "genre" in preview
        assert "acts" in preview
        assert "sample_blueprint" in preview
        assert len(preview["acts"]) == 5
