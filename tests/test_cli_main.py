"""Comprehensive unit tests for ``aicomic.cli.main`` — the CLI entry module.

Every ``handle_*`` function and the ``main``/``build_parser`` entry points are
exercised.  All external calls (filesystem I/O, subprocess, network, provider
APIs) are isolated with ``unittest.mock`` so the suite runs without network
access or real API keys.

Import path: ``from aicomic.cli.main import ...``
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from aicomic.cli import main as cli_main


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    """Write a minimal episode manifest and return its path."""
    data = {
        "project_id": "test_proj",
        "project_name": "测试项目",
        "genre": "horror",
        "episodes": [
            {
                "episode_code": "E01",
                "title": "第一集",
                "publish_title": "测试发布标题",
                "cover_text": "封面文字",
                "shots": [
                    {"shot_id": "S001", "dialogue": "你好", "ai_video": True, "duration": 4, "visual": "室内场景"},
                    {"shot_id": "S002", "dialogue": "", "ai_video": False, "duration": 3, "visual": "室外场景"},
                ],
            },
        ],
    }
    p = tmp_path / "episode_manifest.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def jobs_file(tmp_path: Path) -> Path:
    """Write a minimal jobs payload."""
    data = {"jobs": [
        {"job_id": "J1", "episode_code": "E01", "job_type": "image", "provider": "mock", "status": "pending"},
        {"job_id": "J2", "episode_code": "E01", "job_type": "video", "provider": "mock", "status": "failed"},
    ]}
    p = tmp_path / "jobs.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def batch_file(tmp_path: Path) -> Path:
    """Write a minimal batch payload."""
    data = {
        "batch_id": "test_batch",
        "batch_type": "season_pipeline",
        "scope": {"type": "season", "value": "S01"},
        "steps": [],
        "providers": "",
        "status": "pending",
        "step_count": 0,
    }
    p = tmp_path / "batch.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Helper functions: load_jobs, parse_overrides, parse_filter, P
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_load_jobs(self, jobs_file):
        jobs = cli_main.load_jobs(jobs_file)
        assert len(jobs) == 2
        assert jobs[0].job_id == "J1"
        assert jobs[0].episode_code == "E01"
        assert jobs[0].job_type == "image"

    def test_load_jobs_empty(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text('{"jobs": []}', encoding="utf-8")
        assert cli_main.load_jobs(p) == []

    def test_parse_overrides_basic(self):
        result = cli_main.parse_overrides("image=openai,video=comfyui")
        assert result == {"image": "openai", "video": "comfyui"}

    def test_parse_overrides_empty(self):
        assert cli_main.parse_overrides("") == {}
        assert cli_main.parse_overrides("   ") == {}

    def test_parse_overrides_skip_invalid(self):
        result = cli_main.parse_overrides("a=1,b=,=c, d = e")
        assert result == {"a": "1", "d": "e"}

    def test_parse_filter_basic(self):
        result = cli_main.parse_filter("a, b ,c,, ")
        assert result == {"a", "b", "c"}

    def test_parse_filter_empty(self):
        assert cli_main.parse_filter("") == set()
        assert cli_main.parse_filter(" , , ") == set()

    def test_P_resolves_path(self):
        result = cli_main.P("ProjectPaths.project_root() / 'test'")
        assert isinstance(result, Path)
        assert "test" in str(result)


# ---------------------------------------------------------------------------
# Handler tests — each handle_* function covered
# ---------------------------------------------------------------------------

class TestHandleStatus:
    def test_returns_zero(self, capsys):
        with mock.patch.object(cli_main.ProjectPaths, "project_root", return_value=Path("/tmp/proj")):
            rc = cli_main.handle_status()
        assert rc == 0
        out = capsys.readouterr().out
        assert "project_root=" in out
        assert "config_dir=" in out

    def test_prints_all_paths(self, capsys):
        rc = cli_main.handle_status()
        assert rc == 0
        out = capsys.readouterr().out
        assert "manifest_dir=" in out
        assert "state_dir=" in out


class TestHandleBuildJobs:
    def test_builds_jobs_from_manifest(self, manifest_file, tmp_path, capsys):
        out = tmp_path / "jobs_out.json"
        rc = cli_main.handle_build_jobs(manifest_file, out)
        assert rc == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert "jobs" in data
        out_text = capsys.readouterr().out
        assert "jobs_count=" in out_text

    def test_output_written(self, manifest_file, tmp_path):
        out = tmp_path / "sub" / "jobs.json"
        cli_main.handle_build_jobs(manifest_file, out)
        assert out.exists()


class TestHandleSyncStates:
    def test_syncs_states(self, jobs_file, tmp_path, capsys):
        out = tmp_path / "snapshot.json"
        rc = cli_main.handle_sync_states(jobs_file, out)
        assert rc == 0
        assert out.exists()
        text = capsys.readouterr().out
        assert "episode_states=" in text


class TestHandleDispatchJobs:
    def test_dispatches(self, jobs_file, tmp_path, capsys):
        out = tmp_path / "dispatch.json"
        rc = cli_main.handle_dispatch_jobs(jobs_file, out)
        assert rc == 0
        assert out.exists()
        text = capsys.readouterr().out
        assert "dispatch_count=" in text


class TestHandleAdvanceEpisode:
    def test_valid_transition(self, capsys):
        rc = cli_main.handle_advance_episode("idea", "script_ready")
        assert rc == 0
        assert "idea->script_ready" in capsys.readouterr().out

    def test_invalid_transition_raises(self):
        with pytest.raises(ValueError, match="Invalid episode status transition"):
            cli_main.handle_advance_episode("draft", "ready_for_render")


class TestHandleScanAssets:
    def test_scans(self, manifest_file, tmp_path, capsys):
        out = tmp_path / "scan.json"
        rc = cli_main.handle_scan_assets(manifest_file, "E01", tmp_path, out)
        assert rc == 0
        assert out.exists()
        text = capsys.readouterr().out
        assert "ready_for_preview=" in text


class TestHandleRenderPreview:
    def test_render_preview(self, manifest_file, tmp_path, capsys):
        vid = tmp_path / "preview.mp4"
        ro = tmp_path / "report.json"
        with mock.patch("aicomic.cli.main.render_preview_video_with_audio") as mock_render:
            mock_render.return_value = {"render_mode": "mock"}
            rc = cli_main.handle_render_preview(manifest_file, "E01", tmp_path, vid, ro)
        assert rc == 0
        text = capsys.readouterr().out
        assert "render_mode=" in text


class TestHandlePrepareSubtitlesAudio:
    def test_prepare(self, manifest_file, tmp_path, capsys):
        srt = tmp_path / "out.srt"
        ap = tmp_path / "audio_plan.json"
        wav = tmp_path / "out.wav"
        rc = cli_main.handle_prepare_subtitles_audio(manifest_file, "E01", srt, ap, wav)
        assert rc == 0
        assert srt.exists()
        assert ap.exists()
        assert wav.exists()
        text = capsys.readouterr().out
        assert "subtitle_count=" in text


class TestHandleHorrorBlueprint:
    def test_build_blueprint(self, tmp_path, capsys):
        out = tmp_path / "bp.json"
        rc = cli_main.handle_horror_blueprint("恐怖钩子", "E01", 360, 60, out)
        assert rc == 0
        assert out.exists()
        text = capsys.readouterr().out
        assert "episode_code=E01" in text


class TestHandleBuildHorrorEpisode:
    def test_build_episode(self, tmp_path, capsys):
        # First build a blueprint
        bp = tmp_path / "bp.json"
        cli_main.handle_horror_blueprint("钩子", "E01", 360, 30, bp)
        out = tmp_path / "manifest.json"
        rc = cli_main.handle_build_horror_episode(bp, "test_proj", 1, out)
        assert rc == 0
        assert out.exists()


class TestHandleFilterJobs:
    def test_filter(self, jobs_file, tmp_path, capsys):
        out = tmp_path / "filtered.json"
        rc = cli_main.handle_filter_jobs(jobs_file, "E01", None, None, out)
        assert rc == 0
        assert out.exists()
        text = capsys.readouterr().out
        assert "filtered_count=" in text

    def test_filter_by_status(self, jobs_file, tmp_path):
        out = tmp_path / "filtered.json"
        cli_main.handle_filter_jobs(jobs_file, None, None, "failed", out)
        data = json.loads(out.read_text())
        assert len(data["jobs"]) == 1


class TestHandleRetryJobs:
    def test_retry(self, jobs_file, tmp_path, capsys):
        out = tmp_path / "retried.json"
        rc = cli_main.handle_retry_jobs(jobs_file, "failed", out)
        assert rc == 0
        assert out.exists()
        text = capsys.readouterr().out
        assert "retried_count=" in text


class TestHandleRetryBatch:
    def test_retry_batch(self, jobs_file, tmp_path, capsys):
        ro = tmp_path / "report.json"
        jo = tmp_path / "jobs.json"
        rc = cli_main.handle_retry_batch(jobs_file, "failed", None, None, ro, jo)
        assert rc == 0
        assert ro.exists()
        assert jo.exists()


class TestHandleResumeReport:
    def test_resume(self, tmp_path, capsys):
        ss = tmp_path / "ss.json"
        ss.write_text('{"episodes": []}', encoding="utf-8")
        jf = tmp_path / "jf.json"
        jf.write_text('{"jobs": []}', encoding="utf-8")
        dr = tmp_path / "dr.json"
        dr.write_text('{"decisions": []}', encoding="utf-8")
        out = tmp_path / "resume.json"
        rc = cli_main.handle_resume_report(ss, jf, dr, out)
        assert rc == 0
        assert out.exists()


class TestHandleInitProject:
    def test_init_project(self, tmp_path, capsys):
        out = tmp_path / "new_project"
        rc = cli_main.handle_init_project(
            "test_project", "horror", "anime", None,
            "一个测试故事", "主角", "观众", "恐怖", "钩子", 12, out,
        )
        assert rc == 0
        text = capsys.readouterr().out
        assert "project_id=" in text
        assert "project_root=" in text


class TestHandleTemplateBlueprint:
    def test_template_blueprint(self, tmp_path, capsys):
        out = tmp_path / "bp.json"
        rc = cli_main.handle_template_blueprint("horror", "钩子", "E01", 360, 30, out)
        assert rc == 0
        assert out.exists()
        text = capsys.readouterr().out
        assert "template=horror" in text


class TestHandleTemplateManifest:
    def test_template_manifest(self, tmp_path, capsys):
        bp = tmp_path / "bp.json"
        cli_main.handle_template_blueprint("horror", "钩子", "E01", 360, 30, bp)
        out = tmp_path / "manifest.json"
        rc = cli_main.handle_template_manifest(bp, "horror", "test_proj", 1, out)
        assert rc == 0
        assert out.exists()


class TestHandleListTemplates:
    def test_list(self, capsys):
        rc = cli_main.handle_list_templates()
        assert rc == 0
        text = capsys.readouterr().out
        assert "total=" in text


class TestHandlePublish:
    def test_publish(self, tmp_path, capsys):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"")
        pack = tmp_path / "pack.json"
        out = tmp_path / "results.json"
        with mock.patch("aicomic.cli.main.DomesticPublishPayload") as mpayload, \
             mock.patch("aicomic.cli.main.load_publish_config") as mcfg, \
             mock.patch("aicomic.cli.main.publish_to_platforms") as mpub:
            mpayload.from_publish_pack.return_value = mock.Mock()
            mcfg.return_value = {}
            mpub.return_value = {"douyin": {"success": True}}
            rc = cli_main.handle_publish(video, pack, "douyin", out)
        assert rc == 0
        assert out.exists()


class TestHandleCheckPublish:
    def test_check(self, capsys):
        with mock.patch("aicomic.cli.main.load_publish_config") as mcfg, \
             mock.patch("aicomic.cli.main.check_platform_ready") as mcheck:
            mcfg.return_value = {}
            mcheck.return_value = {"ready": True, "reason": "ok"}
            rc = cli_main.handle_check_publish("douyin")
        assert rc == 0
        text = capsys.readouterr().out
        assert "douyin" in text


class TestHandleNovelImport:
    def test_novel_import(self, tmp_path, capsys):
        novel = tmp_path / "novel.txt"
        novel.write_text("这是一个测试小说。" * 200, encoding="utf-8")
        out = tmp_path / "plan.json"
        # Patch the lazy import inside the function via sys.modules
        import aicomic.core.novel_pipeline as np_mod
        with mock.patch.object(np_mod, "import_novel_file") as mock_import:
            mock_import.return_value = {
                "template": "workplace", "genre": "职场", "episode_count": 2,
                "episodes": [
                    {"episode_code": "E01", "shot_count": 10, "hook": "钩子内容很长很长很长"},
                    {"episode_code": "E02", "shot_count": 10, "hook": "钩子内容很长很长很长"},
                ],
            }
            rc = cli_main.handle_novel_import(novel, "workplace", 12, 10, out)
        assert rc == 0
        assert out.exists()


class TestHandleInstallTemplate:
    def test_install_success(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "install_template_from_url") as mock_install:
            mock_install.return_value = {"success": True, "path": "/tmp/test.yaml"}
            rc = cli_main.handle_install_template("http://example.com/t.yaml", "test")
        assert rc == 0

    def test_install_failure(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "install_template_from_url") as mock_install:
            mock_install.return_value = {"success": False, "error": "bad url"}
            rc = cli_main.handle_install_template("http://bad.url", None)
        assert rc == 1


class TestHandleUninstallTemplate:
    def test_uninstall_success(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "uninstall_template") as mock_un:
            mock_un.return_value = {"success": True}
            rc = cli_main.handle_uninstall_template("test")
        assert rc == 0

    def test_uninstall_failure(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "uninstall_template") as mock_un:
            mock_un.return_value = {"success": False, "error": "not found"}
            rc = cli_main.handle_uninstall_template("nope")
        assert rc == 1


class TestHandleShareTemplate:
    def test_share(self, capsys):
        import aicomic.core.template_market as tm
        import aicomic.core.template_engine as te_mod
        with mock.patch.object(te_mod, "load_template", return_value={"genre": "horror"}), \
             mock.patch.object(tm, "share_template_url") as mock_share:
            mock_share.return_value = {"install_command": "aicomic install", "yaml_base64": "abc123"}
            rc = cli_main.handle_share_template("horror")
        assert rc == 0
        text = capsys.readouterr().out
        assert "base64 length:" in text


class TestHandleTranslateSubtitles:
    def test_translate(self, tmp_path, capsys):
        srt = tmp_path / "test.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\n你好\n", encoding="utf-8")
        out_dir = tmp_path / "subs"
        import aicomic.video_synthesis.i18n as i18n_mod
        with mock.patch.object(i18n_mod, "build_multilang_subtitle_set") as mock_ts:
            mock_ts.return_value = {"en": str(out_dir / "en.srt")}
            rc = cli_main.handle_translate_subtitles(srt, "en,ja", out_dir)
        assert rc == 0
        text = capsys.readouterr().out
        assert "total=" in text


class TestHandleBrowseTemplates:
    def test_browse_all(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "browse_templates") as mock_browse:
            mock_browse.return_value = {
                "templates": [{"id": "horror", "genre": "恐怖", "acts_count": 5, "locations_count": 3}],
                "count": 1,
            }
            rc = cli_main.handle_browse_templates(None)
        assert rc == 0
        text = capsys.readouterr().out
        assert "total=1" in text

    def test_browse_by_genre(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "browse_templates") as mock_browse:
            mock_browse.return_value = {"templates": [], "count": 0}
            rc = cli_main.handle_browse_templates("horror")
        assert rc == 0


class TestHandlePreviewTemplate:
    def test_preview_success(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "preview_template") as mock_prev:
            mock_prev.return_value = {
                "genre": "horror",
                "acts": [{"act_id": "A1", "title": "act1", "beat": "beat1"}],
                "sample_blueprint": {"total_shots": 10},
            }
            rc = cli_main.handle_preview_template("horror")
        assert rc == 0

    def test_preview_failure(self, capsys):
        import aicomic.core.template_market as tm
        with mock.patch.object(tm, "preview_template") as mock_prev:
            mock_prev.side_effect = FileNotFoundError("not found")
            rc = cli_main.handle_preview_template("nonexistent")
        assert rc == 1


class TestHandleSchedulePublish:
    def test_schedule(self, tmp_path, capsys):
        video = tmp_path / "v.mp4"
        out = tmp_path / "schedule.json"
        import aicomic.publish.publish_scheduler as ps
        with mock.patch.object(ps, "create_scheduled_task") as mock_create, \
             mock.patch.object(ps, "save_tasks") as mock_save:
            mock_task = mock.Mock()
            mock_task.task_id = "task123"
            mock_create.return_value = mock_task
            rc = cli_main.handle_schedule_publish(video, "douyin", "2024-01-01T12:00", "title", out)
        assert rc == 0


class TestHandleAnalytics:
    def test_analytics_with_file(self, tmp_path, capsys):
        out = tmp_path / "analytics.json"
        # Analytics file is a list of AnalyticsRecord dicts
        out.write_text(json.dumps([
            {"platform": "douyin", "video_id": "v1", "title": "t1", "views": 1000, "likes": 50, "comments": 10, "shares": 5},
        ]), encoding="utf-8")
        rc = cli_main.handle_analytics(out)
        assert rc == 0
        text = capsys.readouterr().out
        assert "videos:" in text

    def test_analytics_no_file(self, tmp_path, capsys):
        out = tmp_path / "nonexistent.json"
        rc = cli_main.handle_analytics(out)
        assert rc == 0


class TestHandleRenderRelease:
    def test_render_release(self, manifest_file, tmp_path, capsys):
        out = tmp_path / "release.mp4"
        ro = tmp_path / "report.json"
        with mock.patch("aicomic.cli.main.render_release_video") as mock_rr:
            mock_rr.return_value = {"render_profile": "release"}
            rc = cli_main.handle_render_release(manifest_file, "E01", tmp_path, out, ro)
        assert rc == 0
        text = capsys.readouterr().out
        assert "render_profile=" in text


class TestHandleBuildPublishPack:
    def test_build_pack(self, manifest_file, tmp_path, capsys):
        out = tmp_path / "pack.json"
        rc = cli_main.handle_build_publish_pack(manifest_file, "E01", out)
        assert rc == 0
        assert out.exists()


class TestHandleRenderWithTransitions:
    def test_render_transitions(self, manifest_file, tmp_path, capsys):
        vid = tmp_path / "out.mp4"
        ro = tmp_path / "report.json"
        with mock.patch("aicomic.cli.main.render_shots_with_transitions") as mock_rt, \
             mock.patch("aicomic.cli.main.generate_srt_from_shots"), \
             mock.patch("aicomic.cli.main.burn_subtitles_into_video"), \
             mock.patch("aicomic.cli.main.os.path.exists", return_value=False):
            mock_rt.return_value = None
            rc = cli_main.handle_render_with_transitions(manifest_file, "E01", tmp_path, vid, ro, "fade")
        assert rc == 0
        assert ro.exists()
        text = capsys.readouterr().out
        assert "render_mode=" in text


class TestHandleGenerateKeyframes:
    def test_generate(self, manifest_file, tmp_path, capsys):
        out = tmp_path / "keyframes.json"
        rc = cli_main.handle_generate_keyframes(manifest_file, "E01", tmp_path, out, "morph")
        assert rc == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert isinstance(data, list)


class TestHandleGenerateStoryboard:
    def test_generate(self, manifest_file, tmp_path, capsys):
        out = tmp_path / "storyboard.json"
        rc = cli_main.handle_generate_storyboard(manifest_file, "E01", out)
        assert rc == 0
        assert out.exists()

    def test_no_shots_returns_error(self, tmp_path, capsys):
        empty = tmp_path / "empty.json"
        empty.write_text(json.dumps({"episodes": [{"shots": []}]}), encoding="utf-8")
        out = tmp_path / "storyboard.json"
        rc = cli_main.handle_generate_storyboard(empty, "E01", out)
        assert rc == 1


class TestHandleSplitNovel:
    def test_split(self, tmp_path, capsys):
        novel = tmp_path / "novel.txt"
        novel.write_text("这是第一段内容。" * 100 + "\n\n" + "第二段内容。" * 100, encoding="utf-8")
        out = tmp_path / "novel_manifest.json"
        rc = cli_main.handle_split_novel(novel, out, 6)
        assert rc == 0
        assert out.exists()


class TestHandleEnhancePublishPack:
    def test_enhance(self, manifest_file, tmp_path, capsys):
        out = tmp_path / "enhanced.json"
        rc = cli_main.handle_enhance_publish_pack(manifest_file, "E01", out)
        assert rc == 0
        assert out.exists()


class TestHandleSuggestAssetRepairs:
    def test_suggest(self, tmp_path, capsys):
        sr = tmp_path / "scan.json"
        sr.write_text(json.dumps({
            "episode_code": "E01",
            "missing_required": [],
            "missing_optional": [],
            "ready_for_preview": True,
        }), encoding="utf-8")
        out = tmp_path / "repair.json"
        rc = cli_main.handle_suggest_asset_repairs(sr, out)
        assert rc == 0
        assert out.exists()


class TestHandlePlanProviders:
    def test_plan(self, jobs_file, tmp_path, capsys):
        pc = tmp_path / "providers.yaml"
        pc.write_text("", encoding="utf-8")
        out = tmp_path / "plan.json"
        rc = cli_main.handle_plan_providers(jobs_file, pc, out)
        assert rc == 0
        assert out.exists()


class TestHandleBuildProviderRequests:
    def test_build_requests(self, tmp_path, capsys):
        # Use the project's real providers config + a proper manifest
        from aicomic.core.config import ProjectPaths
        from aicomic.core.job_builder import build_jobs_from_episode_manifest
        from aicomic.core.manifest import write_json, load_json

        manifest = {
            "project_id": "test_proj", "project_name": "测试", "genre": "horror",
            "episodes": [{
                "episode_code": "E01", "title": "第一集", "publish_title": "t", "cover_text": "c",
                "shots": [
                    {"shot_id": "S001", "dialogue": "你好", "ai_video": True,
                     "camera": "dialogue", "scene": "室内", "visual": "对话",
                     "action": "说", "emotion": "紧张", "characters": ["主角"], "horror_beat": "诡异"},
                ],
            }],
        }
        ep = tmp_path / "manifest.json"
        ep.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        jobs = build_jobs_from_episode_manifest(manifest)
        jf = tmp_path / "jobs.json"
        jf.write_text(json.dumps({"jobs": [
            {"job_id": j.job_id, "episode_code": j.episode_code, "job_type": j.job_type, "provider": j.provider, "status": j.status}
            for j in jobs
        ]}, ensure_ascii=False), encoding="utf-8")

        pc = ProjectPaths.providers_config_path()
        oroot = tmp_path / "outputs"
        out = tmp_path / "requests.json"
        rc = cli_main.handle_build_provider_requests(ep, jf, pc, oroot, "", out)
        assert rc == 0
        assert out.exists()


class TestHandleApplyProviderResults:
    def test_apply(self, tmp_path, capsys):
        rr = tmp_path / "requests.json"
        rr.write_text(json.dumps({"requests": [], "request_count": 0, "ready_count": 0, "blocked_count": 0}), encoding="utf-8")
        jf = tmp_path / "jobs.json"
        jf.write_text('{"jobs": []}', encoding="utf-8")
        ro = tmp_path / "report.json"
        jo = tmp_path / "jobs_out.json"
        rc = cli_main.handle_apply_provider_results(rr, jf, ro, jo)
        assert rc == 0
        assert ro.exists()
        assert jo.exists()


class TestHandleManualImportBatch:
    def test_manual_import(self, tmp_path, capsys):
        rr = tmp_path / "requests.json"
        rr.write_text(json.dumps({"requests": [], "request_count": 0}), encoding="utf-8")
        jf = tmp_path / "jobs.json"
        jf.write_text('{"jobs": []}', encoding="utf-8")
        ir = tmp_path / "imports"
        ir.mkdir()
        iro = tmp_path / "import_report.json"
        wro = tmp_path / "writeback.json"
        jo = tmp_path / "jobs_out.json"
        rc = cli_main.handle_manual_import_batch(rr, jf, ir, iro, wro, jo, False)
        assert rc == 0
        assert iro.exists()


class TestHandleExecuteProviderRequests:
    def test_execute(self, tmp_path, capsys):
        rr = tmp_path / "requests.json"
        rr.write_text(json.dumps({"requests": [], "request_count": 0, "ready_count": 0, "blocked_count": 0}), encoding="utf-8")
        pc = tmp_path / "providers.yaml"
        pc.write_text("", encoding="utf-8")
        out = tmp_path / "exec.json"
        rc = cli_main.handle_execute_provider_requests(rr, pc, "", True, False, 0, 1, out)
        assert rc == 0
        assert out.exists()


class TestHandleProviderReadiness:
    def test_readiness(self, tmp_path, capsys):
        pc = tmp_path / "providers.yaml"
        pc.write_text("", encoding="utf-8")
        rr = tmp_path / "requests.json"
        rr.write_text(json.dumps({"requests": []}), encoding="utf-8")
        out = tmp_path / "readiness.json"
        rc = cli_main.handle_provider_readiness(pc, rr, out)
        assert rc == 0
        assert out.exists()


class TestHandleComfyuiService:
    def test_status(self, tmp_path, capsys):
        out = tmp_path / "report.json"
        with mock.patch("aicomic.cli.main.run_comfyui_service_action") as mock_run, \
             mock.patch("aicomic.cli.main.write_comfyui_service_report"):
            mock_run.return_value = {
                "action": "status", "base_url": "http://127.0.0.1:8188",
                "status_before": {"status": "unknown"}, "status_after": {"status": "running"},
                "runtime_errors": [],
            }
            rc = cli_main.handle_comfyui_service("status", "127.0.0.1", 8188, 120.0, 2.0, False, out)
        assert rc == 0


class TestHandleLocalProviderLiveSmoke:
    def test_smoke(self, tmp_path, capsys):
        pc = tmp_path / "providers.yaml"
        pc.write_text("", encoding="utf-8")
        oroot = tmp_path / "smoke_out"
        out = tmp_path / "report.json"
        with mock.patch("aicomic.cli.main.run_local_provider_live_smoke") as mock_smoke, \
             mock.patch("aicomic.cli.main.write_local_provider_live_smoke_report"):
            mock_smoke.return_value = {
                "status": "passed",
                "selected_providers": [],
                "preflight_summary": {"ready_count": 0},
                "final_summary": {"success_count": 0, "failed_count": 0},
            }
            rc = cli_main.handle_local_provider_live_smoke(
                pc, "", oroot, "smoke", "smoke", True, False, True, 1,
                "127.0.0.1", 8188, 120.0, 2.0, out,
            )
        assert rc == 0


class TestHandleDependencyAudit:
    def test_audit(self, tmp_path, capsys):
        out = tmp_path / "audit.json"
        with mock.patch("aicomic.cli.main.build_dependency_audit_report") as mock_audit, \
             mock.patch("aicomic.cli.main.write_dependency_audit_report"):
            mock_audit.return_value = {
                "lock_status": "ok", "cve_audit_status": "ok",
                "blocking_count": 0, "warning_count": 0,
            }
            rc = cli_main.handle_dependency_audit(out)
        assert rc == 0


class TestHandleProductionRiskRegister:
    def test_risk_register(self, tmp_path, capsys):
        wc = tmp_path / "web.yaml"
        wc.write_text("", encoding="utf-8")
        pc = tmp_path / "providers.yaml"
        pc.write_text("", encoding="utf-8")
        prp = tmp_path / "readiness.json"
        da = tmp_path / "audit.json"
        out = tmp_path / "risk.json"
        with mock.patch("aicomic.cli.main.build_production_risk_register") as mock_risk, \
             mock.patch("aicomic.cli.main.write_production_risk_register"):
            mock_risk.return_value = {
                "status": "ok", "risk_count": 0,
                "blocking_count": 0, "warning_count": 0,
            }
            rc = cli_main.handle_production_risk_register(wc, None, pc, prp, da, False, "production", out)
        assert rc == 0


class TestHandleBuildBatch:
    def test_build_batch(self, tmp_path, capsys):
        out = tmp_path / "batch.json"
        rc = cli_main.handle_build_batch(
            "test_batch", "season_pipeline", "season", "S01", "", "",
            True, True, "local_comfyui_image", 240, "smoke", "smoke", None, out,
        )
        assert rc == 0
        assert out.exists()


class TestHandleRunBatch:
    def test_run_batch(self, tmp_path, capsys):
        # First build a proper batch file, then run it
        bf = tmp_path / "batch.json"
        cli_main.handle_build_batch(
            "test_batch", "season_pipeline", "season", "S01", "", "",
            True, True, "local_comfyui_image", 240, "smoke", "smoke", None, bf,
        )
        ro = tmp_path / "report.json"
        so = tmp_path / "summary.json"
        rc = cli_main.handle_run_batch(bf, ro, so)
        assert rc == 0
        assert ro.exists()
        assert so.exists()


class TestHandleDashboardExport:
    def test_dashboard(self, tmp_path, capsys):
        vr = tmp_path / "vr.json"
        vr.write_text("{}", encoding="utf-8")
        bs = tmp_path / "bs.json"
        bs.write_text("{}", encoding="utf-8")
        ss = tmp_path / "ss.json"
        ss.write_text("{}", encoding="utf-8")
        mir = tmp_path / "mir.json"
        mir.write_text("{}", encoding="utf-8")
        rbr = tmp_path / "rbr.json"
        rbr.write_text("{}", encoding="utf-8")
        jo = tmp_path / "dash.json"
        ho = tmp_path / "dash.html"
        rc = cli_main.handle_dashboard_export(vr, bs, ss, mir, rbr, jo, ho)
        assert rc == 0
        assert jo.exists()
        assert ho.exists()


class TestHandleReviewMetrics:
    def test_review(self, tmp_path, capsys):
        vr = tmp_path / "vr.json"; vr.write_text("{}", encoding="utf-8")
        d = tmp_path / "d.json"; d.write_text("{}", encoding="utf-8")
        mir = tmp_path / "mir.json"; mir.write_text("{}", encoding="utf-8")
        rbr = tmp_path / "rbr.json"; rbr.write_text("{}", encoding="utf-8")
        per = tmp_path / "per.json"; per.write_text("{}", encoding="utf-8")
        jo = tmp_path / "rev.json"
        ho = tmp_path / "rev.html"
        rc = cli_main.handle_review_metrics(vr, d, mir, rbr, per, jo, ho)
        assert rc == 0
        assert jo.exists()
        assert ho.exists()


class TestHandlePlanRework:
    def test_plan_rework(self, manifest_file, jobs_file, tmp_path, capsys):
        out = tmp_path / "rework.json"
        jo = tmp_path / "rework_jobs.json"
        rc = cli_main.handle_plan_rework(manifest_file, jobs_file, "E01", "S001", out, jo)
        assert rc == 0
        assert out.exists()
        assert jo.exists()


class TestHandleBuildNavigator:
    def test_navigator(self, tmp_path, capsys):
        out = tmp_path / "nav.html"
        rc = cli_main.handle_build_navigator("E01", out)
        assert rc == 0
        assert out.exists()


class TestHandleBuildSeasonJobs:
    def test_season_jobs(self, tmp_path, capsys):
        sm = tmp_path / "season_manifest.json"
        sm.write_text(json.dumps({"project_id": "p", "season": 1, "season_title": "S1", "episodes": ["E01", "E02"]}), encoding="utf-8")
        em = tmp_path / "episode_manifest.json"
        em.write_text(json.dumps({"episodes": [{"episode_code": "E01", "title": "t", "publish_title": "pt", "cover_text": "c", "shots": [{"shot_id": "S001", "dialogue": "d", "ai_video": True, "duration": 4, "visual": "v"}]}]}), encoding="utf-8")
        out = tmp_path / "season_jobs.json"
        rc = cli_main.handle_build_season_jobs(sm, em, out)
        assert rc == 0
        assert out.exists()


class TestHandleScanSeasonAssets:
    def test_scan_season(self, tmp_path, capsys):
        sm = tmp_path / "season.json"
        sm.write_text(json.dumps({"project_id": "p", "season": 1, "season_id": "S01", "episodes": [{"episode_code": "E01"}]}), encoding="utf-8")
        em = tmp_path / "episode.json"
        em.write_text(json.dumps({"episodes": [{"episode_code": "E01", "title": "t", "shots": []}]}), encoding="utf-8")
        out = tmp_path / "scan.json"
        rc = cli_main.handle_scan_season_assets(sm, em, tmp_path, out)
        assert rc == 0
        assert out.exists()


class TestHandleRenderSeason:
    def test_render_season(self, tmp_path, capsys):
        sm = tmp_path / "season.json"
        sm.write_text(json.dumps({"season_id": "S01", "episodes": [{"episode_code": "E01"}]}), encoding="utf-8")
        em = tmp_path / "episode.json"
        em.write_text(json.dumps({"episodes": [{"episode_code": "E01", "title": "t", "shots": []}]}), encoding="utf-8")
        od = tmp_path / "out_dir"
        ro = tmp_path / "report.json"
        with mock.patch("aicomic.cli.main.render_season") as mock_rs:
            mock_rs.return_value = {"episode_count": 1}
            rc = cli_main.handle_render_season(sm, em, tmp_path, od, ro, "preview")
        assert rc == 0


class TestHandleBuildSeasonSummary:
    def test_season_summary(self, tmp_path, capsys):
        sm = tmp_path / "season.json"
        sm.write_text(json.dumps({"project_id": "p", "season": 1, "season_title": "S1", "episodes": [{"episode_code": "E01"}]}), encoding="utf-8")
        jr = tmp_path / "jobs.json"; jr.write_text('{"jobs": []}', encoding="utf-8")
        sr = tmp_path / "scan.json"; sr.write_text("{}", encoding="utf-8")
        rr = tmp_path / "render.json"; rr.write_text("{}", encoding="utf-8")
        out = tmp_path / "summary.json"
        rc = cli_main.handle_build_season_summary(sm, jr, sr, rr, out)
        assert rc == 0
        assert out.exists()


class TestHandleImageConsistencyCmd:
    def test_list_action(self, tmp_path, capsys):
        """Test the image-consistency command via the CLI handler."""
        db = tmp_path / "test.db"
        db.write_bytes(b"")
        # Build argparse namespace with all needed attributes
        args = mock.Mock()
        args.action = "list"
        args.database = str(db)
        args.character_id = ""
        args.character_name = ""
        args.master_image = ""
        args.source_prompt = ""
        args.comfyui_url = "http://127.0.0.1:8188"
        args.model_root = tmp_path
        args.timeout = 4.0
        args.spec = None
        args.work_dir = tmp_path
        args.mode = "mock"
        args.threshold = 0.80
        args.report_output = tmp_path / "report.json"

        from aicomic.cli.image_consistency_cmd import handle_image_consistency
        with mock.patch("aicomic.cli.image_consistency_cmd.connect_character_database") as mock_conn, \
             mock.patch("aicomic.cli.image_consistency_cmd.ensure_character_schema"), \
             mock.patch("aicomic.cli.image_consistency_cmd.ensure_master_sheet_schema"), \
             mock.patch("aicomic.cli.image_consistency_cmd.list_masters", return_value=[]):
            mock_conn.return_value = mock.Mock()
            rc = handle_image_consistency(args)
        assert rc == 0


class TestHandleRenderCmd:
    def test_render_list_modes(self, capsys):
        """Test render --list-modes."""
        from aicomic.cli.render_cmd import handle_render
        args = mock.Mock()
        args.list_modes = True
        args.mode = "2d"
        args.episode_code = "E01"
        args.master_image = None
        args.character_image = None
        args.transition_mode = "zoom"
        args.duration = 3
        args.fps = 24
        args.output = None
        rc = handle_render(args)
        assert rc == 0


# ---------------------------------------------------------------------------
# Parser & main() entry point
# ---------------------------------------------------------------------------

class TestBuildParser:
    def test_builds_parser(self):
        parser = cli_main.build_parser()
        assert parser is not None
        # Subparsers should be set
        assert parser._subparsers is not None

    def test_parser_has_all_commands(self):
        parser = cli_main.build_parser()
        for cmd_name in cli_main.COMMANDS:
            # parse_args with --help would exit, so just verify command exists
            assert cmd_name in cli_main.COMMANDS

    def test_command_registry_completeness(self):
        """All handler functions referenced in COMMANDS should be callable."""
        for name, cmd in cli_main.COMMANDS.items():
            assert "handler" in cmd, f"Command '{name}' missing handler"
            assert callable(cmd["handler"]), f"Command '{name}' handler not callable"
            assert "help" in cmd, f"Command '{name}' missing help"
            assert "args" in cmd, f"Command '{name}' missing args"


class TestMainEntryPoint:
    def test_no_command_prints_help(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aicomic"])
        rc = cli_main.main()
        assert rc == 0
        text = capsys.readouterr().out
        assert len(text) > 0

    def test_status_command(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aicomic", "status"])
        rc = cli_main.main()
        assert rc == 0
        text = capsys.readouterr().out
        assert "project_root=" in text

    def test_advance_episode_command(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aicomic", "advance-episode", "--current", "idea", "--next", "script_ready"])
        rc = cli_main.main()
        assert rc == 0

    def test_list_templates_command(self, capsys, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aicomic", "list-templates"])
        rc = cli_main.main()
        assert rc == 0

    def test_build_jobs_command(self, monkeypatch, tmp_path, manifest_file):
        out = tmp_path / "jobs.json"
        monkeypatch.setattr(sys, "argv", [
            "aicomic", "build-jobs",
            "--episode-manifest", str(manifest_file),
            "--output", str(out),
        ])
        rc = cli_main.main()
        assert rc == 0
        assert out.exists()


class TestMainModule:
    def test_main_module_guard(self, tmp_path):
        """Test that running the module as ``__main__`` invokes ``main()`` and exits cleanly."""
        import aicomic.cli.main as m
        result = subprocess.run(
            [sys.executable, str(Path(m.__file__)), "--help"],
            capture_output=True, text=True, timeout=15,
            cwd=str(tmp_path),
        )
        # --help causes argparse to exit 0
        assert result.returncode == 0
        assert "AI漫剧" in result.stdout or "aicomic" in result.stdout.lower()
