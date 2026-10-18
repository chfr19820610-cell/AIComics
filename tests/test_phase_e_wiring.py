"""Phase E 单元测试：金样评估库 / 审计 Agent / 缺陷看板（SOP §8.4、§4③、§12）。"""
from __future__ import annotations

import json
from pathlib import Path


def _shot(shot_id: str = "S01", *, black: float | None = None, duration: float | None = None, width: int | None = None) -> dict:
    report: dict = {"shot_id": shot_id}
    if black is not None:
        report["black_fraction"] = black
    if duration is not None:
        report["duration"] = duration
    if width is not None:
        report["width"] = width
    return report


class TestJudgeShotsRuleFusion:
    """E1：规则层融合 verdict——LLM 不可用时仍具备判别力（金样回归可红）。"""

    def test_no_issues_pass(self):
        from aicomic.core.self_review import judge_shots

        out = judge_shots([_shot("S01", black=0.02, duration=4.0, width=1080)])
        assert out["verdict"] == "pass"
        assert out["issues"] == []

    def test_black_frames_trigger_revise(self):
        from aicomic.core.self_review import judge_shots

        out = judge_shots([_shot("S01", black=0.97, duration=4.0, width=1080)])
        assert out["verdict"] == "revise"
        assert any("黑帧" in str(i) for i in out["issues"])

    def test_missing_metric_is_flagged_visible(self):
        from aicomic.core.self_review import judge_shots

        out = judge_shots([{"shot_id": "S02"}])  # 无任何指标——不可静默通过
        assert out["verdict"] == "revise"
        assert any("无质检" in str(i) or "missing" in str(i) for i in out["issues"])

    def test_verdict_error_on_empty(self):
        from aicomic.core.self_review import judge_shots

        out = judge_shots([])
        assert out["verdict"] == "error"


class TestGoldenEvaluate:
    """E1 runner：金样库回归（好过坏红；变异注入可反杀）。"""

    def _golden(self, tmp_path: Path) -> Path:
        from aicomic.video_synthesis.quality_check import BLACK_FRACTION_MAX

        cases = [
            {"name": "good_pass_1", "expected": "pass", "shots": [_shot("S01", black=0.01, duration=3.0, width=1080)]},
            {"name": "good_pass_2", "expected": "pass", "shots": [_shot("S02", black=0.05, duration=4.5, width=1080)]},
            {"name": "bad_blackframe", "expected": "revise", "shots": [_shot("S03", black=BLACK_FRACTION_MAX + 0.05, duration=3.0, width=1080)]},
            {"name": "bad_no_metrics", "expected": "revise", "shots": [{"shot_id": "S04"}]},
        ]
        path = tmp_path / "golden.json"
        path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_all_cases_match_expected(self, tmp_path):
        from aicomic.core.self_review import review_with_golden

        report = review_with_golden(self._golden(tmp_path))
        assert report["skipped"] == []
        assert report["passed"] == 4 and report["failed"] == []
        assert report["total"] == 4

    def test_mutation_injection_turns_red(self, tmp_path):
        from aicomic.core.self_review import review_with_golden
        from aicomic.video_synthesis.quality_check import BLACK_FRACTION_MAX

        cases = [
            {"name": "good_should_pass", "expected": "pass", "shots": [_shot("S01", black=0.0, duration=3.0, width=1080)]},
            {"name": "bad_should_fire", "expected": "revise", "shots": [_shot("S01", black=BLACK_FRACTION_MAX + 0.3, duration=3.0, width=1080)]},
        ]
        path = tmp_path / "golden_mut.json"
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        assert review_with_golden(path)["passed"] == 2
        # 变异注入：好样本黑帧爆炸 → judge 必须红（Eval-Driven 红线）
        mutated = [
            {"name": "good_should_pass", "expected": "pass", "shots": [_shot("S01", black=0.9, duration=3.0, width=1080)]},
            {"name": "bad_should_fire", "expected": "revise", "shots": [_shot("S01", black=BLACK_FRACTION_MAX + 0.3, duration=3.0, width=1080)]},
        ]
        path.write_text(json.dumps(mutated, ensure_ascii=False), encoding="utf-8")
        report = review_with_golden(path)
        assert report["passed"] == 1 and len(report["failed"]) == 1
        assert report["failed"][0]["name"] == "good_should_pass"


class TestGoldenFixtureInRepo:
    """SOP §8.4：入库 20 好 + 20 坏指标样本（Phase F 扩充后）。"""

    def test_repo_golden_suite(self):
        fixture = Path(__file__).resolve().parents[1] / "evals" / "golden" / "workplace_E01.json"
        assert fixture.is_file(), f"金样库 fixture 不存在: {fixture}"
        from aicomic.core.self_review import review_with_golden

        report = review_with_golden(fixture)
        assert report["total"] == 40 and report["passed"] == 40 and report["failed"] == []
        assert report["skipped"] == []


class TestConsistencyAudit:
    """E2：资产馆审计 Agent 输出（dHash 相似度 + 阈值，复用 image_consistency 底座）。"""

    def _render(self, tmp_path, name: str, mode: str) -> Path:
        from PIL import Image, ImageDraw

        path = Path(tmp_path) / f"{name}.png"
        img = Image.new("RGB", (128, 128))
        draw = ImageDraw.Draw(img)
        if mode == "same":
            for y in range(0, 128, 8):
                draw.line([(0, y), (128, y)], fill=(200, 180, 160), width=1)
        elif mode == "different":
            for x in range(0, 128, 4):
                draw.line([(x, 0), (x, 128)], fill=(40, 80, 200), width=1)
        else:
            draw.rectangle([16, 16, 112, 112], fill=(60, 60, 60))
        img.save(path, format="PNG")
        return path

    def test_same_reference_pass(self, tmp_path):
        from aicomic.core.consistency_audit import audit_character_assets

        ref = self._render(tmp_path, "ref", "same")
        a1 = self._render(tmp_path, "asset1", "same")
        out = audit_character_assets([ref], [a1])
        assert out["verdict"] == "accept"
        assert out["pairs"][0]["similarity"] >= out["threshold"]

    def test_different_reference_rejects(self, tmp_path):
        from aicomic.core.consistency_audit import audit_character_assets

        ref = self._render(tmp_path, "ref", "same")
        a2 = self._render(tmp_path, "asset_wild", "different")
        out = audit_character_assets([ref], [a2], threshold=0.80)
        assert out["verdict"] == "reject"
        assert out["pairs"][0]["below_threshold"] is True

    def test_missing_file_structured(self, tmp_path):
        from aicomic.core.consistency_audit import audit_character_assets

        out = audit_character_assets([tmp_path / "absent_ref.png"], [tmp_path / "absent_asset.png"])
        assert out["verdict"] == "error"
        assert out["pairs"] == []


class TestDefectBoard:
    """E3：checkpoint 失败/待审 → 看板（SOP §12 缺陷反哺）。"""

    def test_board_counts_failed_and_gates(self, tmp_path):
        from aicomic.core.checkpoint_store import write_checkpoint
        from aicomic.core.pipeline_manifest import CHECKPOINT_AWAITING_HUMAN, CHECKPOINT_FAILED
        from aicomic.core.defect_board import build_defect_board

        write_checkpoint(tmp_path, "E01", "asset_generation", CHECKPOINT_FAILED, metadata={"error": "boom"})
        write_checkpoint(tmp_path, "E01", "shot_breakdown", CHECKPOINT_AWAITING_HUMAN)
        write_checkpoint(tmp_path, "E02", "tts_subtitle", "completed")
        board = build_defect_board(tmp_path)
        assert board["total_defects"] == 2
        entries = {item["stage_id"]: item for item in board["entries"]}
        assert entries["asset_generation"]["status"] == "failed"
        assert "boom" in json.dumps(entries["asset_generation"]["failures"], ensure_ascii=False)

    def test_bad_checkpoint_ignored_visible(self, tmp_path):
        from aicomic.core.defect_board import build_defect_board

        (tmp_path / "checkpoints").mkdir()
        (tmp_path / "checkpoints" / "broken_episode_stage.json").write_text("<not-json>", encoding="utf-8")
        board = build_defect_board(tmp_path)
        assert board["total_defects"] == 0
        assert board["skipped"] == 1

    def test_write_board_markdown(self, tmp_path):
        from aicomic.core.checkpoint_store import write_checkpoint
        from aicomic.core.pipeline_manifest import CHECKPOINT_FAILED
        from aicomic.core.defect_board import write_defect_board

        write_checkpoint(tmp_path, "E01", "asset_generation", CHECKPOINT_FAILED, metadata={"error": "超预算 stopped"})
        out = tmp_path / "reports" / "defect_board.json"
        path, board = write_defect_board(tmp_path, out)
        assert path.exists() and board["total_defects"] == 1
        assert (out.parent / "defect_board.md").exists()


class TestGoldenScale40:
    """F2：金样库 20 好+20 坏（SOP §8.4 字面量）合成指标级。"""

    def test_expanded_fixture_40_green(self):
        fixture = Path(__file__).resolve().parents[1] / "evals" / "golden" / "workplace_E01.json"
        import json as j

        cases = j.loads(fixture.read_text(encoding="utf-8"))["cases"]
        assert len(cases) == 40
        from aicomic.core.self_review import review_with_golden

        report = review_with_golden(fixture)
        assert report["passed"] == 40 and report["failed"] == [], report["failed"][:3]


class TestShotThresholdOverrides:
    """F3：金样 case 级阈值覆盖（线可动，不 hardcode）。"""

    def test_case_level_override(self):
        from aicomic.core.self_review import judge_shots

        shots = [{"shot_id": "S01", "black_fraction": 0.12, "duration": 4.0, "width": 1080}]
        base = judge_shots(shots)
        assert base["verdict"] == "revise"  # 默认线 0.10 → 黑
        strict = judge_shots(shots, threshold_overrides={"black_fraction_max": 0.05})
        assert strict["verdict"] == "revise" and "黑帧" in strict["issues"][0]
        relaxed = judge_shots(shots, threshold_overrides={"black_fraction_max": 0.20})
        assert relaxed["verdict"] == "pass"

    def test_golden_case_threshold_field(self):
        fixture = Path(__file__).resolve().parents[1] / "evals" / "golden" / "workplace_E01.json"
        from aicomic.core.self_review import review_with_golden

        report = review_with_golden(fixture)
        assert report["passed"] == 40  # 含 2 条 override 样本正常评估


class TestEpisodeEfficiency:
    """F4：成片有效率回归（pass-rate ≥ min_pass_rate 才算绿）。"""

    def test_full_pass_green(self):
        from aicomic.core.self_review import evaluate_episode_efficiency

        shots = [{"shot_id": "S01", "black_fraction": 0.02, "duration": 4.0, "width": 1080}] * 10
        out = evaluate_episode_efficiency(shots)
        assert out["pass_rate"] == 1.0 and out["ok"] is True
        assert out["passed"] == 10 and out["revise"] == 0

    def test_below_threshold_red(self):
        from aicomic.core.self_review import evaluate_episode_efficiency

        shots = [{"shot_id": f"S{i}", "black_fraction": 0.02, "duration": 4.0, "width": 1080} for i in range(9)]
        shots.append({"shot_id": "S10"})  # 无指标 → revise
        out = evaluate_episode_efficiency(shots, min_pass_rate=1.0)
        assert out["pass_rate"] == 0.9 and out["ok"] is False and out["revise"] == 1

    def test_empty_structured(self):
        from aicomic.core.self_review import evaluate_episode_efficiency

        out = evaluate_episode_efficiency([])
        assert out["ok"] is False and out["pass_rate"] == 0.0 and "error" in out
