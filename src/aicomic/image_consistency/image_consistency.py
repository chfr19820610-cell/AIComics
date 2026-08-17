"""图像级一致性比对 — 立绘母版 vs 分镜帧的锁脸检测（ACOM-0.7.1）。

基于感知哈希（dHash），纯 PIL 实现，无 numpy 依赖（本机 numpy 损坏，见报告）。
similarity ∈ [0,1]；阈值 threshold 判定是否「跳脸 / FACE_SKIP」。

诚实说明：dHash 是整图结构级感知哈希。脸部区域提取需要 DL 模型（联网下载），
本模块用「上部居中裁剪」作为人脸区域近似，作为可运行、确定性的锁脸代理。
当 ComfyUI 真实出图模型就位后可无缝切换为像素级人脸比对。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

# 默认阈值：similarity < THRESHOLD → 判定跳脸（需复核/重渲）
DEFAULT_THRESHOLD = 0.80


def _open(path_or_pil: Any) -> Image.Image:
    if isinstance(path_or_pil, Image.Image):
        return path_or_pil.convert("L")
    return Image.open(str(path_or_pil)).convert("L")


def image_dhash(path_or_pil: Any, size: int = 8, crop: tuple[int, int, int, int] | None = None) -> int:
    """计算 64 位感知哈希（dHash）。

    size=8 → 8×8 相邻差分 = 64 bit，与 similarity(bits=64) 的分母对齐。
    crop 用于框定关键区域（默认 None = 整图；人脸近似可传上部居中框）。
    返回值：0..2^64-1 的整数。
    """
    img = _open(path_or_pil)
    if crop is not None:
        # 防御：裁剪框非法/零面积时退化为整图，避免 ImageOps.fit 除零崩溃
        if len(crop) == 4 and crop[2] > crop[0] and crop[3] > crop[1]:
            img = img.crop(crop)
    img = ImageOps.fit(img, (size, size + 1), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    width = size
    bits = 0
    for y in range(size):  # size 行
        for x in range(size):  # size 个相邻列差分
            left = pixels[y * width + x]
            right = pixels[y * width + x + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming_distance(a: int, b: int) -> int:
    """两个 64 位哈希的海明距离。"""
    return bin(a ^ b).count("1")


def similarity(a: int, b: int, bits: int = 64) -> float:
    """归一化相似度 [0,1]：1 - 海明距离 / bits。"""
    return round(1.0 - hamming_distance(a, b) / bits, 4)


def face_approx_crop(width: int, height: int) -> tuple[int, int, int, int]:
    """人脸区域近似：上部居中 60% 宽度 × 上部 55% 高度。

    说明：立绘通常面部位于画面上部居中；此裁剪作为无 DL 模型时的锁脸代理。
    """
    cw = max(1, int(width * 0.60))
    ch = max(1, int(height * 0.55))
    x0 = max(0, (width - cw) // 2)
    y0 = max(0, int(height * 0.05))
    # 保证裁剪框非空（至少 1x1），否则 ImageOps.fit 遇 0x0 会除零崩溃
    return (x0, y0, min(x0 + cw, width), min(y0 + ch, height))


@dataclass
class FrameCheck:
    """单帧 vs 母版的图像级比对结果。"""
    frame_path: str
    master_path: str
    character_name: str = ""
    hash_a: int = 0
    hash_b: int = 0
    hamming: int = 0
    similarity: float = 0.0
    threshold: float = DEFAULT_THRESHOLD
    verdict: str = "NO_MASTER"  # LOCKED / FACE_SKIP / NO_MASTER
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_path": self.frame_path,
            "master_path": self.master_path,
            "character_name": self.character_name,
            "hamming": self.hamming,
            "similarity": self.similarity,
            "threshold": self.threshold,
            "verdict": self.verdict,
            "note": self.note,
        }


class ImageConsistencyService:
    """图像级角色一致性门禁：以立绘母版为基准比对分镜帧。"""

    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold

    def compare_frame_vs_master(
        self,
        frame_path: str | Path,
        master_path: str | Path,
        character_name: str = "",
        crop: tuple[int, int, int, int] | None = None,
    ) -> FrameCheck:
        """比对单帧 vs 立绘母版，返回 LOCKED / FACE_SKIP。"""
        fp = str(frame_path)
        mp = str(master_path)
        master_p = Path(mp)
        frame_p = Path(fp)
        if not master_p.exists():
            return FrameCheck(frame_path=fp, master_path=mp,
                              character_name=character_name, verdict="NO_MASTER",
                              note="母版图不存在，无法锁定")
        if not frame_p.exists():
            return FrameCheck(frame_path=fp, master_path=mp,
                              character_name=character_name, verdict="NO_MASTER",
                              note="分镜帧不存在")
        # 人脸近似裁剪
        if crop is None:
            with Image.open(mp) as im:
                crop = face_approx_crop(im.width, im.height)
        ha = image_dhash(mp, crop=crop)
        hb = image_dhash(fp, crop=crop)
        dist = hamming_distance(ha, hb)
        sim = similarity(ha, hb)
        passed = sim >= self.threshold
        return FrameCheck(
            frame_path=fp, master_path=mp, character_name=character_name,
            hash_a=ha, hash_b=hb, hamming=dist, similarity=sim,
            threshold=self.threshold,
            verdict="LOCKED" if passed else "FACE_SKIP",
            note="" if passed else "与立绘母版相似度低于阈值，疑似跳脸，需复核/重渲",
        )

    def check_episode_frames(
        self,
        frames_dir: str | Path,
        master_path: str | Path,
        character_name: str = "",
        frame_suffix: str = ".png",
    ) -> list[FrameCheck]:
        """比对某目录下所有分镜帧 vs 同一立绘母版。"""
        d = Path(frames_dir)
        if not d.exists():
            return []
        checks: list[FrameCheck] = []
        for p in sorted(d.glob(f"*{frame_suffix}")):
            checks.append(self.compare_frame_vs_master(p, master_path, character_name))
        return checks

    def lock_violations(self, checks: list[FrameCheck]) -> list[FrameCheck]:
        """筛选出未锁定的帧（FACE_SKIP）。"""
        return [c for c in checks if c.verdict == "FACE_SKIP"]

    def summarize(self, checks: list[FrameCheck]) -> dict[str, Any]:
        total = len(checks)
        locked = sum(1 for c in checks if c.verdict == "LOCKED")
        skipped = sum(1 for c in checks if c.verdict == "FACE_SKIP")
        no_master = sum(1 for c in checks if c.verdict == "NO_MASTER")
        sims = [c.similarity for c in checks if c.verdict in ("LOCKED", "FACE_SKIP")]
        avg_sim = round(sum(sims) / len(sims), 4) if sims else 0.0
        passed = no_master == 0 and skipped == 0
        return {
            "total": total,
            "locked": locked,
            "face_skip": skipped,
            "no_master": no_master,
            "avg_similarity": avg_sim,
            "threshold": self.threshold,
            "passed": passed,
        }
