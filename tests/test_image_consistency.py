"""ACOM-0.7.1 图像级角色一致性测试套件。

覆盖：pHash 图像级比对 / 立绘母版 CRUD / ComfyUI 锁脸工作流构建与可用性探测 /
漫剧单集产线一键化（mock 端到端产出 MP4）。
"""

from __future__ import annotations

import sqlite3

import pytest
from PIL import Image, ImageDraw

from aicomic.characters.database import connect_character_database, ensure_character_schema
from aicomic.image_consistency.comfyui_locks import (
    build_locked_workflow,
    probe_lock_models,
    validate_locked_workflow,
)
from aicomic.image_consistency.image_consistency import (
    ImageConsistencyService,
    face_approx_crop,
    image_dhash,
    similarity,
)
from aicomic.image_consistency.master_sheet import (
    MasterSheetEntry,
    default_lock_config,
    ensure_master_sheet_schema,
    get_master_by_name,
    list_masters,
    mark_locked,
    register_master,
)
from aicomic.image_consistency.one_shot_pipeline import (
    OneShotPipeline,
    ShotSpec,
    synth_master_image,
)


# ── 辅助：生成测试图 ───────────────────────────────────────────────────


def _solid_image(path, color: tuple[int, int, int], size=(64, 64)):
    Image.new("RGB", size, color).save(str(path))
    return path


def _structural_image(path, kind: str):
    """生成带结构信息的测试图（dHash 基于灰度结构，纯色图会趋同故需结构图）。"""
    img = Image.new("RGB", (128, 128), (0, 0, 0))
    d = ImageDraw.Draw(img)
    if kind == "vsplit":        # 左白右黑（纵向分半）
        d.rectangle([0, 0, 63, 127], fill=(255, 255, 255))
    elif kind == "hsplit":      # 上白下黑（横向分半）
        d.rectangle([0, 0, 127, 63], fill=(255, 255, 255))
    else:
        raise ValueError(f"未知结构图类型: {kind}")
    img.save(str(path))
    return path


def _master_fixture(tmp_path):
    return synth_master_image(tmp_path / "master.png", "测试角色")


# ── 1. pHash 图像级比对 ────────────────────────────────────────────────


def test_dhash_deterministic(tmp_path):
    img = _solid_image(tmp_path / "a.png", (200, 40, 40))
    assert image_dhash(img) == image_dhash(img)


def test_similarity_same_image():
    a = image_dhash(_solid_image("/tmp/_t_a1.png", (100, 150, 200)))
    b = image_dhash(_solid_image("/tmp/_t_a2.png", (100, 150, 200)))
    assert similarity(a, b) == 1.0


def test_similarity_different_colors():
    # 纯色图在灰度 dHash 下无结构信息，红/蓝均趋同(相似度=1.0)→ 改用结构图断言可区分
    a = image_dhash(_structural_image("/tmp/_t_b1.png", "vsplit"))
    b = image_dhash(_structural_image("/tmp/_t_b2.png", "hsplit"))
    assert similarity(a, b) < 0.9


def test_face_approx_crop():
    x0, y0, x1, y1 = face_approx_crop(540, 960)
    assert x1 > x0 and y1 > y0
    assert x1 <= 540 and y1 <= 960


def test_face_approx_crop_tiny_nonempty(tmp_path):
    # 回归：红队发现 1x1 图裁剪出空框 (0,0,0,0) 会让 ImageOps.fit 除零崩溃
    img = Image.new("L", (1, 1), 5)
    crop = face_approx_crop(1, 1)
    assert crop[2] > crop[0] and crop[3] > crop[1]
    assert image_dhash(img, crop=crop) == image_dhash(img)


# ── 2. 立绘母版图像级门禁 ─────────────────────────────────────────────


def test_compare_frame_vs_master_locked(tmp_path):
    master = _master_fixture(tmp_path)
    frame = tmp_path / "frame.png"
    img = Image.open(str(master)).point(lambda px: min(255, int(px * 0.97)))
    img.save(str(frame))
    svc = ImageConsistencyService(threshold=0.80)
    check = svc.compare_frame_vs_master(frame, master, character_name="测试角色")
    assert check.verdict == "LOCKED"
    assert check.similarity >= 0.80


def test_compare_frame_vs_master_face_skip(tmp_path):
    master = _master_fixture(tmp_path)
    frame = _solid_image(tmp_path / "skip.png", (0, 120, 220), size=(540, 960))
    svc = ImageConsistencyService(threshold=0.80)
    check = svc.compare_frame_vs_master(frame, master, character_name="测试角色")
    assert check.verdict == "FACE_SKIP"


def test_compare_frame_vs_master_no_master(tmp_path):
    frame = _solid_image(tmp_path / "f.png", (10, 20, 30))
    svc = ImageConsistencyService()
    check = svc.compare_frame_vs_master(frame, tmp_path / "missing.png", "测试角色")
    assert check.verdict == "NO_MASTER"


# ── 3. 立绘母版 CRUD（SQLite） ─────────────────────────────────────────


def _db(tmp_path) -> sqlite3.Connection:
    conn = connect_character_database(tmp_path / "char.db")
    ensure_character_schema(conn)
    ensure_master_sheet_schema(conn)
    return conn


def _add_character(conn: sqlite3.Connection, cid: str, name: str) -> None:
    """母版表 master_sheets.character_id 外键引用 characters(id)，注册母版前必须先建角色行。"""
    from aicomic.characters.database import insert_character
    insert_character(conn, {
        "id": cid, "name": name, "tags": ["测试"],
        "created_at": "2026-08-02T00:00:00+00:00",
        "updated_at": "2026-08-02T00:00:00+00:00",
    })


def test_master_sheet_register_roundtrip(tmp_path):
    conn = _db(tmp_path)
    _add_character(conn, "c1", "女主")
    entry = register_master(
        conn, "c1", "女主", str(tmp_path / "m.png"),
        dna={"hair": "黑长直"}, source_prompt="参考prompt",
    )
    found = get_master_by_name(conn, "女主")
    assert found is not None
    assert found.character_id == "c1"
    assert found.dna["hair"] == "黑长直"
    assert found.locked is False


def test_master_sheet_lock(tmp_path):
    conn = _db(tmp_path)
    _add_character(conn, "c1", "女主")
    register_master(conn, "c1", "女主", str(tmp_path / "m.png"))
    master = get_master_by_name(conn, "女主")
    assert mark_locked(conn, master.id, True)
    assert get_master_by_name(conn, "女主").locked is True


def test_master_sheet_list(tmp_path):
    conn = _db(tmp_path)
    _add_character(conn, "c1", "女主")
    _add_character(conn, "c2", "反派")
    register_master(conn, "c1", "女主", "m1.png")
    register_master(conn, "c2", "反派", "m2.png")
    assert len(list_masters(conn)) == 2


# ── 4. ComfyUI 锁脸工作流构建 ─────────────────────────────────────────


def test_build_locked_workflow_nodes():
    master = MasterSheetEntry(
        id="ms1", character_id="c1", character_name="女主",
        master_image_path="/tmp/master.png", locked=True,
        lock_config=default_lock_config("/tmp/master.png"),
    )
    wf = build_locked_workflow(master, "正面prompt", "负面")
    res = validate_locked_workflow(wf)
    assert res["valid"] is True
    classes = [n["class_type"] for n in wf["prompt"].values()]
    assert "IPAdapterUnifiedLoaderFaceID" in classes
    assert "KSampler" in classes
    assert "SaveImage" in classes
    assert wf["extra"]["locked"] is True


def test_probe_lock_models_missing_reported(tmp_path):
    # 用不存在 model_root → 应如实报告缺失（待联网）
    status = probe_lock_models(
        comfyui_base_url="http://127.0.0.1:1", model_root=tmp_path / "models", timeout=1.0,
    )
    assert status.all_ready is False
    assert any("IPAdapter" in m or "ipadapter" in m.lower() or "ComfyUI" in m for m in status.missing)


# ── 5. 单集产线一键化（mock 端到端） ──────────────────────────────────


def test_one_shot_pipeline_mock(tmp_path):
    pipe = OneShotPipeline(tmp_path / "work", threshold=0.80)
    characters = [{"id": "c1", "name": "女主", "hair_color": (60, 40, 20)}]
    shots = [
        ShotSpec("S001", "女主", scene="雨夜街头", action="转身", emotion="紧张", dialogue="谁在那里？"),
        ShotSpec("S002", "女主", scene="雨夜街头", action="奔跑", emotion="恐惧", dialogue="别过来！"),
    ]
    report = pipe.run(characters, shots, mode="mock", output_name="ep.mp4")
    gate = report["consistency_gate"]["summary"]
    assert gate["total"] == 2
    assert gate["face_skip"] == 0
    assert gate["passed"] is True
    assert report["render"]
    assert (tmp_path / "work" / "ep.mp4").exists()
    assert (tmp_path / "work" / "masters" / "女主_master.png").exists()
    # 报告为合法 JSON
    import json
    json.dumps(report, ensure_ascii=False)


def test_one_shot_pipeline_gate_blocks_skip(tmp_path):
    pipe = OneShotPipeline(tmp_path / "work2", threshold=0.80)
    characters = [{"id": "c1", "name": "女主"}]
    # 手动构造一个 FACE_SKIP 帧，验证门禁拦截（不成片）
    masters = pipe.ensure_masters(characters)
    from aicomic.image_consistency.image_consistency import ImageConsistencyService
    svc = ImageConsistencyService(threshold=0.80)
    skip_frame = pipe._frames_dir / "S001.png"
    Image.new("RGB", (540, 960), (0, 255, 0)).save(str(skip_frame))
    check = svc.compare_frame_vs_master(skip_frame, masters["女主"].master_image_path)
    assert check.verdict == "FACE_SKIP"
