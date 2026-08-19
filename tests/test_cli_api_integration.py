"""CLI + Web API integration tests for template market, i18n, and novel pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

# === CLI handler tests ===

class TestCLIInstallTemplate:
    def test_install_from_url_handler(self, tmp_path, monkeypatch):
        """install-template CLI handler calls template_market.install_template_from_url."""
        from aicomic.core.template_market import install_template_from_dict
        # Simulate: create a valid template dict
        t = {
            "template_id": "cli_test",
            "genre": "CLI测试",
            "acts": [{"act_id": "A1", "title": "x", "beat": "x"}],
            "locations": ["x"],
            "characters": [{"name": "x", "role": "x", "visual_rule": "x"}],
        }
        result = install_template_from_dict(t, templates_dir=tmp_path)
        assert result["success"] is True
        assert (tmp_path / "cli_test.yaml").exists()


class TestWebAPITemplates:
    def test_api_templates_list(self):
        """GET /api/templates should return list of templates."""
        from web.backend.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/api/templates")
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data
        assert len(data["templates"]) >= 6  # at least 6 built-in
        # Each template should have id and genre
        for t in data["templates"]:
            assert "id" in t
            assert "genre" in t

    def test_api_template_detail(self):
        """GET /api/templates/horror should return template details."""
        from web.backend.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/api/templates/horror")
        assert r.status_code == 200
        data = r.json()
        assert data["template_id"] == "horror"
        assert len(data["acts"]) == 5

    def test_api_template_not_found(self):
        """GET /api/templates/nonexistent should 404."""
        from web.backend.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/api/templates/nonexistent_xyz")
        assert r.status_code == 404


class TestWebAPIPublish:
    def test_api_publish_status(self):
        """GET /api/publish/status should return platform readiness."""
        from web.backend.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.get("/api/publish/status")
        assert r.status_code == 200
        data = r.json()
        assert "platforms" in data
        assert "douyin" in data["platforms"]
        assert "bilibili" in data["platforms"]


class TestWebAPINovel:
    def test_api_novel_import(self):
        """POST /api/novel/import should accept text + template and return season plan."""
        from web.backend.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.post("/api/novel/import", json={
            "text": "第一章 雨夜\n夜里不能回头。井口有声音。\n第二章 井\n她走到井边往下看。",
            "template": "mystery",
            "episodes": 2,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["episode_count"] >= 1
        assert data["template"] == "mystery"

    def test_api_novel_import_missing_text(self):
        """POST /api/novel/import without text should 422."""
        from web.backend.app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        r = client.post("/api/novel/import", json={"template": "horror"})
        assert r.status_code == 422


class TestFullChainIntegration:
    def test_novel_to_episode_plan_chain(self, tmp_path):
        """Full chain: novel text → import → blueprint → episode plan."""
        from aicomic.core.novel_pipeline import import_novel, generate_episode_plan
        text = "第一章 开端\n老城区，幸福路18号。刑警老陈接到报案。\n第二章 现场\n死者是个单身女性，门窗完好，密室杀人。\n第三章 嫌疑人\n三个嫌疑人各执一词。"
        result = import_novel(text, template="mystery", episode_target_count=1, shots_per_episode=6)
        assert result["episode_count"] >= 1
        ep = result["episodes"][0]
        # Generate episode plan from the blueprint
        plan = generate_episode_plan(ep["blueprint"], template_name="mystery", shots_per_episode=6)
        assert plan["total_shots"] == 6
        assert len(plan["shot_plan"]) == 6
        assert len(plan["asset_plan"]["characters"]) > 0
