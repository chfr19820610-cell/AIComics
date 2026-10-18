"""Phase G 单元测试：文件总线 / 任务契约 / 投流编号 / 废片截帧（SOP §7.1、§6.3、§11、§4⑤）。"""
from __future__ import annotations

import json
from pathlib import Path


class TestBusLayout:
    """G1：§7.1 骨架担保与 gate 级「文件存在」验证。"""

    def test_ensure_creates_skeleton(self, tmp_path):
        from aicomic.core.bus_layout import ensure_series_layout, series_layout_targets

        series = tmp_path / "series-x"
        targets = ensure_series_layout(series, "E01")
        for t in targets:
            assert Path(t).exists(), t
            if t.suffix in {".json", ".md"}:
                assert t.is_file()
            else:
                assert t.is_dir()
        assert (series / "assets" / "bible.json").is_file()
        assert (series / "runs" / "E01" / "shots" / "E01S01" / "salvage").is_dir()

    def test_validate_missing_reports_visible(self, tmp_path):
        from aicomic.core.bus_layout import ensure_series_layout, validate_series_layout

        series = tmp_path / "series-x"
        ensure_series_layout(series, "E01")
        ok1 = validate_series_layout(series, "E01")
        assert ok1["ok"] is True and ok1["missing"] == []
        # 破坏一个 gate 坐标：runs/E01/compliance.json 移走（骨架只抬目录，文件按需补）
        file_target = series / "runs" / "E01" / "compliance.json"
        file_target.unlink()
        report = validate_series_layout(series, "E01")
        assert report["ok"] is False and str(report["missing"][0]).endswith("compliance.json")

    def test_validate_absent_series_all_missing(self, tmp_path):
        from aicomic.core.bus_layout import validate_series_layout

        report = validate_series_layout(tmp_path / "ghost", "E02")
        assert report["ok"] is False and len(report["missing"]) >= 8


class TestTaskContract:
    """G2：§6.3 任务级契约——机器可读、红线可执行。"""

    def _base(self, *, duration_s=4.0) -> dict:
        return {
            "from": "分镜师Agent", "to": "抽卡Agent",
            "artifact": "runs/E01/shots/E01S01/",
            "payload": {
                "shot_id": "E01S01", "duration_s": duration_s,
                "refs": {"char_front": "assets/anqi/front.png"},
                "style_tokens": "国漫/电影光影/…",
                "motion_prompt": "谁→动→终态；运镜：…",
                "budget": {"max_roll": 3, "model_route": "seedance2.0/i2v"},
            },
            "acceptance": [
                "人脸与 front 相似度 ≥ 阈值",
                "时长=4.0±0.3s；无黑帧；器具数量正确",
                "风格词全部命中",
            ],
            "failure_policy": "return reason + partial frames for salvage",
        }

    def test_valid_contract_passes(self):
        from aicomic.core.task_contract import validate_task_contract

        out = validate_task_contract(self._base())
        assert out["ok"] is True and out["violations"] == []

    def test_missing_field_rejected(self):
        from aicomic.core.task_contract import validate_task_contract

        c = self._base()
        del c["failure_policy"]
        out = validate_task_contract(c)
        assert out["ok"] is False
        assert any("failure_policy" in str(v) for v in out["violations"])

    def test_duration_over_eight_rejected(self):
        from aicomic.core.task_contract import validate_task_contract

        out = validate_task_contract(self._base(duration_s=8.5))
        assert out["ok"] is False and any("8" in str(v) for v in out["violations"])

    def test_budget_block_required(self):
        from aicomic.core.task_contract import validate_task_contract

        c = self._base()
        del c["payload"]["budget"]["max_roll"]
        out = validate_task_contract(c)
        assert out["ok"] is False and any("max_roll" in str(v) for v in out["violations"])


class TestAdCode:
    """G3：§11 投流编号（可回溯七段，劈段失明必红）。"""

    def test_canonical_code(self):
        from aicomic.publish.ad_code import build_ad_code

        code = build_ad_code("识婚", "安其", "身份反差", "v3", "douyin", "2026-10-18", "eric")
        parts = code.split("-")
        assert len(parts) == 7 and parts[5] == "20261018" and parts[6] == "eric"
        assert parts[0] == "识婚" and parts[1] == "安其" and parts[3] == "v3"

    def test_empty_segment_rejected(self):
        from aicomic.publish.ad_code import build_ad_code

        try:
            build_ad_code("", "安其", "s", "v1", "douyin", "2026-10-18", "a")
        except ValueError as exc:
            assert "可回溯" in str(exc) or "空" in str(exc)
        else:
            raise AssertionError("空段必须拒绝")

    def test_in_segment_dash_rejected(self):
        from aicomic.publish.ad_code import build_ad_code

        try:
            build_ad_code("识-婚", "a", "s", "v1", "douyin", "2026-10-18", "e")
        except ValueError:
            pass
        else:
            raise AssertionError("段内劈段符必须拒绝")

    def test_bad_date_rejected(self):
        from aicomic.publish.ad_code import build_ad_code

        try:
            build_ad_code("识婚", "a", "s", "v1", "douyin", "2026-13-99", "e")
        except ValueError:
            pass
        else:
            raise AssertionError("非法日期必须拒绝")

    def test_attach_to_compliance(self):
        from aicomic.publish.ad_code import build_ad_code, attach_to_compliance

        code = build_ad_code("识婚", "a", "s", "v1", "douyin", "2026-10-18", "e")
        record = attach_to_compliance({"publish_title": "x"}, code)
        assert record["ad_code"] == code and record["pack"]["publish_title"] == "x"



def _fake_salvage_ffmpeg(calls, default=3):
    import re as _re

    def fake(cmd):
        calls.append(list(cmd))
        try:
            n = int(cmd[cmd.index("-frames:v") + 1])
        except (ValueError, IndexError):
            n = default
        out_template = Path(str(cmd[-1]))
        parent = out_template.parent
        match = _re.search(r"%0(\d+)d", out_template.name)
        width = int(match.group(1)) if match else 2
        parent.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (parent / f"frame_{i:0{width}d}.png").write_bytes(b"P1" + b"\x00" * 8)
        return 0
    return fake

class TestSalvageFrames:
    """G4：§4⑤ 废片截帧自动入库。"""

    def _fake_ffmpeg(self, calls, default=3):
        import re as _re

        def fake(cmd):
            calls.append(list(cmd))
            try:
                n = int(cmd[cmd.index("-frames:v") + 1])  # ffmpeg 语义：-frames:v 计数
            except (ValueError, IndexError):
                n = default
            out_template = Path(str(cmd[-1]))  # e.g. .../salvage/frame_%02d.png
            parent = out_template.parent
            match = _re.search(r"%0(\d+)d", out_template.name)
            width = int(match.group(1)) if match else 2
            parent.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                (parent / f"frame_{i:0{width}d}.png").write_bytes(b"P1" + b"\x00" * 8)
            return 0
        return fake

    def test_salvage_writes_frames(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import salvage as sv

        video = tmp_path / "bad.mp4"
        video.write_bytes(b"0" * 16)
        calls: list[list[str]] = []
        monkeypatch.setattr(sv, "_probe_duration", lambda v: 4.0)
        monkeypatch.setattr(sv, "_run_ffmpeg", _fake_salvage_ffmpeg(calls))
        out = sv.salvage_frames(video, tmp_path / "salvage", count=4)
        assert len(out["saved"]) == 4 and all(p.suffix == ".png" for p in out["saved"])
        assert "-vf" in " ".join(str(x) for x in calls[0])

    def test_missing_video_structured(self, tmp_path):
        from aicomic.video_synthesis.salvage import salvage_frames

        out = salvage_frames(tmp_path / "ghost.mp4", tmp_path / "s")
        assert out["saved"] == [] and "not_found" in out["error"]

    def test_ffmpeg_failure_structured(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import salvage as sv

        video = tmp_path / "bad.mp4"
        video.write_bytes(b"0" * 16)
        monkeypatch.setattr(sv, "_probe_duration", lambda v: 4.0)
        monkeypatch.setattr(sv, "_run_ffmpeg", lambda cmd: 33)
        out = sv.salvage_frames(video, tmp_path / "s")
        assert out["saved"] == [] and "rc=33" in out["error"]


class TestSalvageProbePath:
    def test_probe_duration_feeds_fps(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import salvage as sv

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 16)
        calls: list[list[str]] = []
        monkeypatch.setattr(sv, "_probe_duration", lambda v: 4.0)
        monkeypatch.setattr(sv, "_probe_duration", lambda v: 4.0)
        monkeypatch.setattr(sv, "_run_ffmpeg", _fake_salvage_ffmpeg(calls))
        out = sv.salvage_frames(video, tmp_path / "s", count=4)
        assert len(out["saved"]) == 4
        assert "fps=" in " ".join(str(x) for x in calls[0])

    def test_probe_unavailable_visible(self, tmp_path, monkeypatch):
        from aicomic.video_synthesis import salvage as sv

        video = tmp_path / "v.mp4"
        video.write_bytes(b"0" * 16)
        monkeypatch.setattr(sv, "_probe_duration", lambda v: None)
        out = sv.salvage_frames(video, tmp_path / "s", count=4)
        assert out["saved"] == [] and "probe" in out["error"]
