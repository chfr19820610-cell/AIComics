"""Silent failure trap library — 漫剧专属"渲染没报错但成片有问题"检测器。

Based on godogen methodology: "编译能过但运行时静默崩"的坑沉淀成指南。
漫剧的silent failures不同于通用AI伪影——它们是"管线无异常但成片有暗病"。

Trap categories (漫剧专属):
  1. lip_sync     — 唇音不同步(TTS音频和角色嘴型对不上)
  2. subtitle_occlusion — 字幕压住关键画面/角色面部
  3. jump_cut     — 镜头跳切违和(相邻shot场景不连续)
  4. ken_burns    — Ken Burns运镜穿帮(缩放超出画面边界/方向矛盾)
  5. color_drift  — 跨镜头色调不一致(同一场景不同shot色温突变)
  6. aspect_error — 画幅/比例错(竖屏变横屏/分辨率不匹配平台)
  7. timing_drift — 字幕时间轴偏移(SRT和音频对不上)
  8. face_stiff   — 角色表情僵硬(有脸但没表情变化/全程木脸)

Usage:
    checker = SilentFailureChecker()
    report = checker.check(episode_metadata)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Trap definitions ─────────────────────────────────────────────────────

TRAP_CATEGORIES: dict[str, dict[str, str]] = {
    "lip_sync": {
        "name": "唇音不同步",
        "description": "TTS音频与角色嘴型/节奏对不上，渲染无报错但观感违和",
        "severity": "major",
        "detection": "Compare audio duration vs shot duration; check if dialogue timestamps fall within shot boundaries",
    },
    "subtitle_occlusion": {
        "name": "字幕遮挡",
        "description": "字幕位置压住角色面部或关键画面元素",
        "severity": "minor",
        "detection": "Check subtitle Y-position against character face bounding box in same frame",
    },
    "jump_cut": {
        "name": "跳切违和",
        "description": "相邻shot场景/角色位置不连续，无转场但视觉断裂",
        "severity": "major",
        "detection": "Compare consecutive shot scene_ids, location, and character positions",
    },
    "ken_burns": {
        "name": "运镜穿帮",
        "description": "Ken Burns缩放超出画面边界或运镜方向与构图矛盾",
        "severity": "minor",
        "detection": "Check zoom factor vs image resolution; verify pan direction doesn't exceed frame bounds",
    },
    "color_drift": {
        "name": "色调漂移",
        "description": "同一场景不同shot色温/亮度突变，跨镜头视觉不连贯",
        "severity": "minor",
        "detection": "Compare color_histogram stats between consecutive shots in same scene",
    },
    "aspect_error": {
        "name": "画幅错误",
        "description": "输出画幅与目标平台不匹配(竖屏9:16变横屏16:9)",
        "severity": "critical",
        "detection": "Check output resolution aspect ratio vs target platform spec",
    },
    "timing_drift": {
        "name": "时间轴偏移",
        "description": "SRT字幕时间轴与实际音频/画面对不上",
        "severity": "major",
        "detection": "Compare SRT entry timestamps against TTS audio segment boundaries",
    },
    "face_stiff": {
        "name": "表情僵硬",
        "description": "角色有面部但全程无表情变化/木脸，AI生成痕迹",
        "severity": "minor",
        "detection": "Check face expression variance across shots; low variance = stiff",
    },
}


@dataclass
class TrapHit:
    """A single silent failure trap hit."""
    trap_type: str
    severity: str  # critical / major / minor
    description: str
    shot_index: int = -1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SilentFailureReport:
    """Report of silent failure checks on an episode."""
    status: str  # CLEAN / SUSPECT / FAIL
    score: int  # 0-100, higher = cleaner
    traps_hit: list[TrapHit] = field(default_factory=list)
    traps_checked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "traps_hit": [vars(t) for t in self.traps_hit],
            "traps_checked": self.traps_checked,
        }


class SilentFailureChecker:
    """漫剧专属沉默失败检测器。

    Checks episode metadata against known silent-failure traps.
    Each trap is a heuristic check on episode/shot metadata.

    Usage:
        checker = SilentFailureChecker()
        report = checker.check(episode_metadata)
    """

    # Scoring weights by severity
    SEVERITY_DEDUCTIONS = {"critical": 30, "major": 15, "minor": 5}

    def __init__(
        self,
        fail_threshold: int = 40,
        suspect_threshold: int = 70,
    ) -> None:
        self.fail_threshold = fail_threshold
        self.suspect_threshold = suspect_threshold

    def check(self, episode_metadata: dict[str, Any]) -> SilentFailureReport:
        """Run all silent failure checks on episode metadata.

        Expected metadata structure:
            {
                "shots": [
                    {
                        "shot_index": int,
                        "scene_id": str,
                        "duration_seconds": float,
                        "audio_duration": float,       # TTS audio length
                        "has_dialogue": bool,
                        "subtitle_y_pct": float,       # subtitle position (0-1)
                        "face_bbox_y": list[float],    # face bounding box y-range
                        "location": str,
                        "resolution": str,             # e.g. "1080x1920"
                        "target_aspect": str,          # e.g. "9:16"
                        "ken_burns_zoom": float,       # zoom factor
                        "ken_burns_pan": str,          # pan direction
                        "color_histogram": dict,       # {r_mean, g_mean, b_mean}
                        "face_expression": str,        # detected expression
                    }
                ],
                "srt_entries": [{"start": float, "end": float, "text": str}],
                "audio_segments": [{"start": float, "end": float}],
                "target_platform": str,  # "douyin" / "youtube" etc
            }

        Returns:
            SilentFailureReport with status and trap hits.
        """
        traps_hit: list[TrapHit] = []
        traps_checked: list[str] = []
        shots = episode_metadata.get("shots", [])

        # Check each trap
        for trap_type in TRAP_CATEGORIES:
            traps_checked.append(trap_type)
            method = getattr(self, f"_check_{trap_type}", None)
            if method:
                hits = method(shots, episode_metadata)
                traps_hit.extend(hits)

        return self._build_report(traps_hit, traps_checked)

    def _check_lip_sync(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check lip-sync: audio duration vs shot duration mismatch."""
        hits = []
        for shot in shots:
            audio_dur = shot.get("audio_duration", 0)
            shot_dur = shot.get("duration_seconds", 0)
            has_dialogue = shot.get("has_dialogue", False)
            if has_dialogue and audio_dur > 0 and shot_dur > 0:
                diff = abs(audio_dur - shot_dur) / max(audio_dur, shot_dur)
                if diff > 0.15:  # >15% mismatch
                    hits.append(TrapHit(
                        trap_type="lip_sync",
                        severity="major",
                        description=f"Shot {shot.get('shot_index', '?')}: audio {audio_dur:.1f}s vs shot {shot_dur:.1f}s ({diff*100:.0f}% mismatch)",
                        shot_index=shot.get("shot_index", -1),
                        metadata={"audio_duration": audio_dur, "shot_duration": shot_dur},
                    ))
        return hits

    def _check_subtitle_occlusion(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check subtitle covering character face."""
        hits = []
        for shot in shots:
            sub_y = shot.get("subtitle_y_pct", 0)
            face_y = shot.get("face_bbox_y", [])
            if sub_y > 0 and face_y and len(face_y) >= 2:
                # Subtitle at bottom (y > 0.8) overlapping face (face extends below 0.75)
                if sub_y > 0.8 and face_y[1] > 0.75:
                    hits.append(TrapHit(
                        trap_type="subtitle_occlusion",
                        severity="minor",
                        description=f"Shot {shot.get('shot_index', '?')}: subtitle at {sub_y:.0%} overlaps face at {face_y[1]:.0%}",
                        shot_index=shot.get("shot_index", -1),
                    ))
        return hits

    def _check_jump_cut(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check discontinuous adjacent shots."""
        hits = []
        for i in range(1, len(shots)):
            prev = shots[i - 1]
            curr = shots[i]
            # Same scene but location changed without transition
            if (prev.get("scene_id") == curr.get("scene_id")
                    and prev.get("location") != curr.get("location")
                    and prev.get("location") and curr.get("location")):
                hits.append(TrapHit(
                    trap_type="jump_cut",
                    severity="major",
                    description=f"Shots {prev.get('shot_index', '?')}→{curr.get('shot_index', '?')}: same scene, location '{prev.get('location')}'→'{curr.get('location')}'",
                    shot_index=curr.get("shot_index", -1),
                ))
        return hits

    def _check_ken_burns(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check Ken Burns zoom exceeding bounds."""
        hits = []
        for shot in shots:
            zoom = shot.get("ken_burns_zoom", 1.0)
            if zoom > 2.0:  # zoom > 2x likely to show artifacts
                hits.append(TrapHit(
                    trap_type="ken_burns",
                    severity="minor",
                    description=f"Shot {shot.get('shot_index', '?')}: zoom {zoom:.1f}x exceeds safe 2x",
                    shot_index=shot.get("shot_index", -1),
                    metadata={"zoom": zoom},
                ))
        return hits

    def _check_color_drift(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check color inconsistency between consecutive shots in same scene."""
        hits = []
        for i in range(1, len(shots)):
            prev = shots[i - 1].get("color_histogram", {})
            curr = shots[i].get("color_histogram", {})
            if not prev or not curr:
                continue
            if shots[i - 1].get("scene_id") != shots[i].get("scene_id"):
                continue  # different scenes — color change expected
            # Compare RGB means
            diff = sum(
                abs(prev.get(k, 0) - curr.get(k, 0))
                for k in ("r_mean", "g_mean", "b_mean")
            ) / 3
            if diff > 40:  # RGB mean delta > 40 = noticeable shift
                hits.append(TrapHit(
                    trap_type="color_drift",
                    severity="minor",
                    description=f"Shots {shots[i-1].get('shot_index', '?')}→{shots[i].get('shot_index', '?')}: color delta {diff:.0f} in same scene",
                    shot_index=shots[i].get("shot_index", -1),
                    metadata={"color_diff": diff},
                ))
        return hits

    def _check_aspect_error(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check output aspect ratio matches target platform."""
        hits = []
        target = meta.get("target_aspect", "9:16")
        target_ratio = self._parse_aspect(target)
        for shot in shots:
            res = shot.get("resolution", "")
            if "x" not in res:
                continue
            w, h = res.split("x")
            actual_ratio = int(w) / int(h) if int(h) != 0 else 0
            if abs(actual_ratio - target_ratio) > 0.05:
                hits.append(TrapHit(
                    trap_type="aspect_error",
                    severity="critical",
                    description=f"Shot {shot.get('shot_index', '?')}: {res} (ratio {actual_ratio:.2f}) vs target {target} (ratio {target_ratio:.2f})",
                    shot_index=shot.get("shot_index", -1),
                    metadata={"resolution": res, "target": target},
                ))
        return hits

    def _check_timing_drift(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check SRT timestamps align with audio segments."""
        hits = []
        srt_entries = meta.get("srt_entries", [])
        audio_segments = meta.get("audio_segments", [])
        if not srt_entries or not audio_segments:
            return hits
        for i, (srt, audio) in enumerate(zip(srt_entries, audio_segments)):
            srt_mid = (srt.get("start", 0) + srt.get("end", 0)) / 2
            audio_mid = (audio.get("start", 0) + audio.get("end", 0)) / 2
            if abs(srt_mid - audio_mid) > 0.5:  # >500ms drift
                hits.append(TrapHit(
                    trap_type="timing_drift",
                    severity="major",
                    description=f"Entry {i}: SRT mid={srt_mid:.2f}s vs audio mid={audio_mid:.2f}s (drift {abs(srt_mid - audio_mid)*1000:.0f}ms)",
                    metadata={"srt_mid": srt_mid, "audio_mid": audio_mid},
                ))
        return hits

    def _check_face_stiff(self, shots: list[dict], meta: dict) -> list[TrapHit]:
        """Check character face expression variance — stiff if too uniform."""
        hits = []
        expressions = [s.get("face_expression", "") for s in shots if s.get("face_expression")]
        if len(expressions) < 5:
            return hits  # not enough shots to judge
        unique = set(expressions)
        if len(unique) == 1:
            hits.append(TrapHit(
                trap_type="face_stiff",
                severity="minor",
                description=f"All {len(expressions)} shots have same expression '{expressions[0]}' — likely stiff",
                metadata={"unique_expressions": len(unique), "total": len(expressions)},
            ))
        return hits

    @staticmethod
    def _parse_aspect(aspect: str) -> float:
        """Parse '9:16' → 0.5625."""
        parts = aspect.split(":")
        if len(parts) == 2:
            try:
                return int(parts[0]) / int(parts[1])
            except (ValueError, ZeroDivisionError):
                pass
        return 0.5625  # default 9:16

    def _build_report(self, traps_hit: list[TrapHit], traps_checked: list[str]) -> SilentFailureReport:
        """Build report from trap hits."""
        if not traps_hit:
            return SilentFailureReport(
                status="CLEAN",
                score=100,
                traps_hit=[],
                traps_checked=traps_checked,
            )

        has_critical = any(t.severity == "critical" for t in traps_hit)
        score = 100
        for trap in traps_hit:
            score -= self.SEVERITY_DEDUCTIONS.get(trap.severity, 5)
        score = max(0, score)

        if has_critical or score < self.fail_threshold:
            status = "FAIL"
        elif score < self.suspect_threshold:
            status = "SUSPECT"
        else:
            status = "CLEAN"

        return SilentFailureReport(
            status=status,
            score=score,
            traps_hit=traps_hit,
            traps_checked=traps_checked,
        )

    @staticmethod
    def get_trap_catalog() -> list[dict[str, str]]:
        """Get the full trap catalog for documentation/display."""
        return [
            {"type": k, **v}
            for k, v in TRAP_CATEGORIES.items()
        ]
