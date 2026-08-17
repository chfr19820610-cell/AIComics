"""漫剧单集产线一键化 — 从立绘母版到单集成片（ACOM-0.7.1）。

编排链路：
  立绘母版(图像级锁) → 分镜增强 prompt → 出帧(mock占位 或 ComfyUI真实)
  → 图像级一致性门禁(pHash vs 母版，锁脸) → Ken Burns + drawtext 字幕 + 音频 → 最终 MP4

诚实标注：
  - mock 模式：用 PIL 生成立绘母版派生帧（可运行、无需模型权重），
    图像级门禁照常执行并产出真实判定；真实出图依赖 ComfyUI 权重联网下载。
  - 产出物：母版 PNG、分镜帧、一致性报告、最终 MP4（ffmpeg 由 imageio_ffmpeg 内置）。
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from aicomic.image_consistency.comfyui_locks import (
    probe_lock_models,
    validate_locked_workflow,
)
from aicomic.image_consistency.image_consistency import ImageConsistencyService
from aicomic.image_consistency.master_sheet import MasterSheetEntry, default_lock_config

# 合成立绘母版：肤色底 + 头发/眼睛/嘴 特征块（无 DL 模型时的可运行基准图）
_MASTER_W, _MASTER_H = 540, 960
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
]


@dataclass
class ShotSpec:
    """单个分镜规格。"""
    shot_id: str
    character_name: str
    scene: str = ""
    action: str = ""
    emotion: str = ""
    dialogue: str = ""
    duration_s: float = 2.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id, "character_name": self.character_name,
            "scene": self.scene, "action": self.action, "emotion": self.emotion,
            "dialogue": self.dialogue, "duration_s": self.duration_s,
        }


# ── 立绘母版生成（合成基准图） ─────────────────────────────────────────


def synth_master_image(
    out_path: str | Path,
    character_name: str,
    hair_color: tuple[int, int, int] = (40, 32, 26),
    skin: tuple[int, int, int] = (232, 178, 138),
) -> Path:
    """生成一张合成的「立绘母版」基准图（含发型/脸/眼/嘴特征块）。"""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # JSON 反序列化会把颜色变 list，PIL fill 需 tuple → 统一强转
    hair_color = tuple(int(v) for v in hair_color)
    skin = tuple(int(v) for v in skin)
    img = Image.new("RGB", (_MASTER_W, _MASTER_H), (120, 130, 150))  # 背景
    draw = ImageDraw.Draw(img)
    # 头发（上部大色块）
    draw.rectangle([120, 60, 420, 340], fill=hair_color)
    # 脸（肤色椭圆）
    draw.ellipse([160, 180, 380, 520], fill=skin)
    # 眼睛（两枚深色）
    draw.ellipse([205, 300, 245, 340], fill=(30, 30, 30))
    draw.ellipse([295, 300, 335, 340], fill=(30, 30, 30))
    # 嘴（下方）
    draw.ellipse([240, 400, 300, 425], fill=(150, 60, 60))
    # 角色名水印
    font = _pick_font(24)
    draw.text((180, 600), character_name, fill=(255, 255, 255), font=font)
    img.save(p, "PNG")
    return p


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for f in _FONT_CANDIDATES:
        if Path(f).exists():
            try:
                return ImageFont.truetype(f, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _derive_mock_frame(master_path: str | Path, out_path: str | Path, seed: int) -> Path:
    """从母版派生一帧（微扰动，相似度高 → 应 LOCKED）。"""
    img = Image.open(str(master_path)).convert("RGB")
    factor = 0.95 + (seed % 10) * 0.01  # 0.95..1.04 轻微亮度扰动
    img = img.point(lambda px: max(0, min(255, int(px * factor))))
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, "PNG")
    return p


# ── 单集产线 ────────────────────────────────────────────────────────────


class OneShotPipeline:
    """漫剧单集产线一键化编排器。"""

    def __init__(
        self,
        work_dir: str | Path,
        comfyui_base_url: str = "http://127.0.0.1:8188",
        threshold: float = 0.80,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.comfyui_base_url = comfyui_base_url
        self.consistency = ImageConsistencyService(threshold=threshold)
        self._frames_dir = self.work_dir / "frames"
        self._masters_dir = self.work_dir / "masters"
        self._frames_dir.mkdir(parents=True, exist_ok=True)
        self._masters_dir.mkdir(parents=True, exist_ok=True)

    # ── 阶段1：母版就位 ────────────────────────────────────────────────
    def ensure_masters(self, characters: list[dict[str, Any]]) -> dict[str, MasterSheetEntry]:
        """为每个角色生成/返回立绘母版，锁定图像级基准。"""
        masters: dict[str, MasterSheetEntry] = {}
        for i, ch in enumerate(characters):
            name = str(ch.get("name", f"角色{i}"))
            master_path = synth_master_image(
                self._masters_dir / f"{name}_master.png", name,
                hair_color=ch.get("hair_color", (40, 32, 26)),
                skin=ch.get("skin", (232, 178, 138)),
            )
            entry = MasterSheetEntry(
                id=f"ms-{i}", character_id=str(ch.get("id", f"c{i}")),
                character_name=name, master_image_path=str(master_path),
                dna=ch.get("dna", {}),
                lock_config=default_lock_config(str(master_path)),
                locked=True,
                source_prompt=str(ch.get("reference_prompt", "")),
            )
            masters[name] = entry
        return masters

    # ── 阶段2：出帧 ────────────────────────────────────────────────────
    def generate_frames(
        self,
        shots: list[ShotSpec],
        masters: dict[str, MasterSheetEntry],
        mode: str = "mock",
        checkpoint_name: str = "animagineXL_v4.safetensors",
    ) -> list[dict[str, Any]]:
        """逐镜出帧。mode='mock' 用 PIL 占位（可运行）；'real' 走 ComfyUI 真实出图。"""
        produced: list[dict[str, Any]] = []
        if mode == "real":
            availability = probe_lock_models(self.comfyui_base_url)
            if not availability.all_ready:
                mode = "mock"
                produced.append({"warn": "真实出图依赖权重未就绪，降级为 mock",
                                 "missing": availability.missing})
        for idx, shot in enumerate(shots):
            master = masters.get(shot.character_name)
            if master is None:
                produced.append({"shot_id": shot.shot_id, "status": "NO_MASTER",
                                 "note": f"角色 {shot.character_name} 无立绘母版"})
                continue
            if mode == "real":
                frame_path = self._real_generate(shot, master, checkpoint_name)
            else:
                frame_path = _derive_mock_frame(master.master_image_path,
                                                self._frames_dir / f"{shot.shot_id}.png", idx)
            produced.append({"shot_id": shot.shot_id, "character_name": shot.character_name,
                             "frame_path": str(frame_path), "mode": mode, "status": "OK"})
        return produced

    def _real_generate(
        self, shot: ShotSpec, master: MasterSheetEntry, checkpoint_name: str
    ) -> Path:
        """向运行中 ComfyUI 提交锁脸工作流并取回图像（需权重联网就绪）。"""
        from aicomic.image_consistency.comfyui_locks import build_locked_workflow

        prompt_text = _build_shot_prompt(shot, master)
        workflow = build_locked_workflow(master, prompt_text, checkpoint_name=checkpoint_name,
                                         output_prefix=f"locked_{shot.shot_id}")
        body = json.dumps({"prompt": workflow["prompt"], "extra": workflow["extra"]}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.comfyui_base_url}/prompt", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            submit = json.loads(resp.read().decode("utf-8"))
        prompt_id = submit.get("prompt_id")
        # 轮询 history
        history: dict[str, Any] = {}
        for _ in range(60):
            time.sleep(1.0)
            try:
                with urllib.request.urlopen(
                        f"{self.comfyui_base_url}/history/{prompt_id}", timeout=5) as hr:
                    history = json.loads(hr.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                continue
            entry = history.get(prompt_id, {})
            if entry.get("outputs"):
                break
        if not history.get(prompt_id, {}).get("outputs"):
            raise RuntimeError("ComfyUI 未返回图像（可能权重未就绪）")
        out = history.get(prompt_id, {}).get("outputs", {})
        img_rel = None
        for node in out.values():
            for im in node.get("images", []):
                img_rel = im.get("filename")
        if not img_rel:
            raise RuntimeError("ComfyUI 未返回图像（可能权重未就绪）")
        with urllib.request.urlopen(f"{self.comfyui_base_url}/view?filename={img_rel}", timeout=15) as vr:
            data = vr.read()
        frame_path = self._frames_dir / f"{shot.shot_id}.png"
        frame_path.write_bytes(data)
        return frame_path

    # ── 阶段3：图像级一致性门禁 ────────────────────────────────────────
    def run_consistency_gate(
        self, produced: list[dict[str, Any]], masters: dict[str, MasterSheetEntry]
    ) -> dict[str, Any]:
        """以立绘母版为基准对每帧做 pHash 锁脸比对。"""
        checks = []
        for item in produced:
            if item.get("status") != "OK" or not item.get("frame_path"):
                continue
            name = item.get("character_name", "")
            master = masters.get(name)
            if master is None:
                continue
            checks.append(self.consistency.compare_frame_vs_master(
                item["frame_path"], master.master_image_path, character_name=name))
        summary = self.consistency.summarize(checks)
        violations = self.consistency.lock_violations(checks)
        return {"checks": [c.to_dict() for c in checks], "summary": summary,
                "violations": [c.to_dict() for c in violations]}

    # ── 阶段4：成片 ────────────────────────────────────────────────────
    def render_mp4(self, shots: list[ShotSpec], out_path: str | Path) -> Path:
        """Ken Burns(zoompan) 分镜 + concat + drawtext 字幕 + 音频 → 最终 MP4。"""
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            clip_paths: list[Path] = []
            frame_map: dict[str, str] = {}
            for item in self._frames_dir.glob("*.png"):
                frame_map[item.stem] = str(item)
            for i, shot in enumerate(shots):
                src = frame_map.get(shot.shot_id)
                if src is None:
                    continue
                clip = td / f"shot_{i:02d}.mp4"
                frames = max(1, int(shot.duration_s * 10))
                vf = (
                    f"zoompan=z='min(zoom+0.0008,1.05)':d={frames}:fps=10"
                    f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=540x960"
                )
                self._ff(ffmpeg, ["-y", "-loop", "1", "-i", src, "-vf", vf,
                                  "-t", str(shot.duration_s), "-pix_fmt", "yuv420p",
                                  "-c:v", "libx264", "-preset", "veryfast", str(clip)])
                clip_paths.append(clip)
            if not clip_paths:
                raise RuntimeError("无分镜帧可渲染")
            concat_file = td / "list.txt"
            concat_file.write_text("".join(f"file '{c.resolve()}'\n" for c in clip_paths),
                                   encoding="utf-8")
            concat_out = td / "concat.mp4"
            self._ff(ffmpeg, ["-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                              "-c", "copy", str(concat_out)])
            # drawtext 字幕
            font = _font_for_ffmpeg()
            vf_filters: list[str] = []
            t0 = 0.0
            for i, shot in enumerate(shots):
                if not shot.dialogue:
                    t0 += shot.duration_s
                    continue
                esc = shot.dialogue.replace("'", "\\'").replace(":", "\\:")
                vf_filters.append(
                    f"drawtext=fontfile='{font}':text='{esc}':fontsize=36:fontcolor=white:"
                    f"borderw=2:bordercolor=black:x=(w-text_w)/2:y=h-120:"
                    f"enable='between(t,{t0:.2f},{t0 + shot.duration_s:.2f})'")
                t0 += shot.duration_s
            # 音频：纯音垫底
            total = sum(s.duration_s for s in shots if s.dialogue or True)
            # aevalsrc 默认输出 u8 8bit 音频，AAC 原生编码器无法打开 → 显式转 s16 PCM
            self._ff(ffmpeg, ["-y", "-f", "lavfi", "-i",
                              f"aevalsrc=sin(130.81*t)*0.2:d={total:.2f}:c=2",
                              "-af", "volume=0.1",
                              "-ar", "44100", "-ac", "2", "-sample_fmt", "s16",
                              str(td / "bgm.wav")])
            if vf_filters:
                filter_str = ",".join(vf_filters)
                self._ff(ffmpeg, ["-y", "-i", str(concat_out), "-i", str(td / "bgm.wav"),
                                  "-vf", filter_str, "-c:v", "libx264", "-preset", "veryfast",
                                  "-ar", "44100", "-ac", "2", "-c:a", "aac",
                                  "-b:a", "96k", "-shortest", str(out)])
            else:
                self._ff(ffmpeg, ["-y", "-i", str(concat_out), "-i", str(td / "bgm.wav"),
                                  "-c:v", "copy",
                                  "-ar", "44100", "-ac", "2", "-c:a", "aac",
                                  "-b:a", "96k", "-shortest", str(out)])
        return out

    @staticmethod
    def _ff(ffmpeg: str, args: list[str]) -> None:
        proc = subprocess.run([ffmpeg, *args], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg 失败: {proc.stderr[-800:]}")

    # ── 一键入口 ────────────────────────────────────────────────────────
    def run(
        self,
        characters: list[dict[str, Any]],
        shots: list[ShotSpec],
        mode: str = "mock",
        output_name: str = "episode_out.mp4",
    ) -> dict[str, Any]:
        report: dict[str, Any] = {"mode": mode, "work_dir": str(self.work_dir)}
        masters = self.ensure_masters(characters)
        report["masters"] = [m.to_dict() for m in masters.values()]
        report["master_count"] = len(masters)
        produced = self.generate_frames(shots, masters, mode=mode)
        report["frames"] = produced
        gate = self.run_consistency_gate(produced, masters)
        report["consistency_gate"] = gate
        if gate["summary"]["passed"]:
            report["render"] = str(self.render_mp4(shots, self.work_dir / output_name))
        else:
            report["render"] = ""
            report["render_skipped"] = "图像级门禁未通过，未成片（需复核跳脸帧）"
        report["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        return report


def _build_shot_prompt(shot: ShotSpec, master: MasterSheetEntry) -> str:
    """把母版 DNA + 分镜字段拼成增强 prompt（图像级锁脸工作流正提示词）。"""
    parts: list[str] = []
    if master.source_prompt:
        parts.append(master.source_prompt)
    if shot.scene:
        parts.append(f"场景：{shot.scene}")
    if shot.action:
        parts.append(f"动作：{shot.action}")
    if shot.emotion:
        parts.append(f"情绪：{shot.emotion}")
    parts.append("高质量动漫插画，母版锁定保持一致")
    return "，".join(p for p in parts if p)


def _font_for_ffmpeg() -> str:
    for f in _FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return "/System/Library/Fonts/Hiragino Sans GB.ttc"


def write_pipeline_report(path: str | Path, report: dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
