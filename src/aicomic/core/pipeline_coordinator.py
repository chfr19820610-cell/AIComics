"""管线协调器 — ACOM-0.6.0 P0-1/2/3.

把"管线是什么"从 Python 硬编码提升为声明式清单（config/pipelines/*.yaml），
阶段流转、人工审核门、checkpoint 自检、断点续跑全部由本协调器统一驱动。
episode_lifecycle / 外部调用方通过本协调器读清单决定下一步，改管线只改 YAML。

不变量：
  - 阶段顺序来自清单（stages 数组顺序），非硬编码。
  - 门禁阶段（human_approval_default=true）未批准前无法推进。
  - 每阶段完成写 checkpoint；断点续跑基于 checkpoint。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from aicomic.core.approval_gate import (
    HumanApprovalRequiredError,
    approve_stage,
    complete_stage,
    is_stage_approved,
    mark_awaiting_human,
    require_stage_approved,
)
from aicomic.core.checkpoint_store import (
    CHECKPOINT_AWAITING_HUMAN,
    CHECKPOINT_COMPLETED,
    checkpoint_status,
    write_checkpoint,
)
from aicomic.core.episode_lifecycle import stage_to_episode_status
from aicomic.core.pipeline_manifest import (
    CHECKPOINT_IN_PROGRESS,
    PipelineManifest,
    PipelineManifestError,
    get_pipeline_manifest,
)


@dataclass
class StageAdvanceResult:
    episode_code: str
    current_stage: str
    next_stage: str | None
    status: str
    required_human_approval: bool = False
    warnings: list[str] = field(default_factory=list)
    episode_status: str | None = None  # synced from episode_lifecycle mapping


class PipelineCoordinator:
    """基于声明式清单的漫剧单集管线协调器。"""

    def __init__(self, state_dir: Path, manifest: PipelineManifest | None = None) -> None:
        self.state_dir = state_dir
        self.manifest = manifest or get_pipeline_manifest()
        self.step_ids = self.manifest.step_ids

    # ---- 查询 ----

    def stage_status(self, episode_code: str, stage_id: str) -> str:
        return checkpoint_status(self.state_dir, episode_code, stage_id) or "not_started"

    def stage_approved(self, episode_code: str, stage_id: str) -> bool:
        return is_stage_approved(self.state_dir, episode_code, stage_id)

    def current_stage(self, episode_code: str) -> str | None:
        """返回下一个应处理的阶段（第一个非 completed，或 completed 但门禁未批准的阶段）。全完成返回 None。"""
        for stage_id in self.step_ids:
            status = self.stage_status(episode_code, stage_id)
            if status != CHECKPOINT_COMPLETED:
                return stage_id
            # 门禁阶段 completed 但 human_approved 未置位 → 视为未完成（防直写绕过）
            if (
                self.manifest.stage(stage_id).requires_human_approval
                and not self.stage_approved(episode_code, stage_id)
            ):
                return stage_id
        return None

    # ---- 推进 ----

    def begin_stage(self, episode_code: str, stage_id: str) -> StageAdvanceResult:
        """标记阶段开始（in_progress）。"""
        stage = self.manifest.stage(stage_id)
        write_checkpoint(
            self.state_dir,
            episode_code,
            stage_id,
            CHECKPOINT_IN_PROGRESS,
            review_focus=stage.review_focus,
            success_criteria_met=None,
            metadata={"pipeline": self.manifest.pipeline_id},
        )
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=stage_id,
            next_stage=self._next_of(stage_id),
            status=CHECKPOINT_IN_PROGRESS,
        )

    def complete_stage(
        self,
        episode_code: str,
        stage_id: str,
        *,
        self_review: dict[str, object] | None = None,
    ) -> StageAdvanceResult:
        """完成一个阶段（写 checkpoint）。门禁阶段自动锁 awaiting_human。"""
        try:
            complete_stage(
                self.state_dir,
                episode_code,
                stage_id,
                manifest=self.manifest,
                self_review=self_review,
            )
        except HumanApprovalRequiredError as exc:
            return StageAdvanceResult(
                episode_code=episode_code,
                current_stage=stage_id,
                next_stage=None,
                status=CHECKPOINT_AWAITING_HUMAN,
                required_human_approval=True,
                warnings=[str(exc)],
            )
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=stage_id,
            next_stage=self._next_of(stage_id),
            status=CHECKPOINT_COMPLETED,
            episode_status=stage_to_episode_status(stage_id),
        )

    def approve_stage(
        self,
        episode_code: str,
        stage_id: str,
        *,
        reviewer: str,
        notes: str = "",
    ) -> StageAdvanceResult:
        """人工批准门禁阶段，放行到下一阶段。每门独立批准。"""
        approve_stage(
            self.state_dir,
            episode_code,
            stage_id,
            reviewer=reviewer,
            notes=notes,
        )
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=stage_id,
            next_stage=self._next_of(stage_id),
            status=CHECKPOINT_COMPLETED,
            episode_status=stage_to_episode_status(stage_id),
        )

    def advance(self, episode_code: str) -> StageAdvanceResult:
        """自动推进：校验门禁并给出下一步。

        若当前阶段已被锁定为 awaiting_human（门禁阶段完成但未人工批准），
        抛 HumanApprovalRequiredError（硬门禁：未批准任何路径都无法推进）。
        若当前阶段是尚未开始的下一阶段，直接放行进入。
        """
        current = self.current_stage(episode_code)
        if current is None:
            return StageAdvanceResult(
                episode_code=episode_code,
                current_stage="",
                next_stage=None,
                status="all_completed",
            )
        status = self.stage_status(episode_code, current)
        # 硬门禁：门禁阶段若已产出（awaiting_human 或 被直写 completed 绕过），
        # 只要 human_approved 标志未置位即拦截——不依赖 status 值（防 B3/R2 绕过）。
        if self.manifest.stage(current).requires_human_approval and status in (
            CHECKPOINT_AWAITING_HUMAN,
            CHECKPOINT_COMPLETED,
        ) and not self.stage_approved(episode_code, current):
            require_stage_approved(self.state_dir, episode_code, current, self.manifest)
        return StageAdvanceResult(
            episode_code=episode_code,
            current_stage=current,
            next_stage=self._next_of(current),
            status=status,
        )

    def require_ready_to_proceed(self, episode_code: str, stage_id: str) -> None:
        """外部调用：试图进入/处理某阶段前，校验前置门禁已放行。"""
        require_stage_approved(self.state_dir, episode_code, stage_id, self.manifest)

    def execute_shot_breakdown(
        self, episode_code: str, blueprint: dict[str, object], template_name: str = "", project_id: str = ""
    ) -> dict[str, object]:
        """执行 SOP shot_breakdown 阶段：从蓝图生成完整分镜 manifest。"""
        from aicomic.core.template_engine import build_manifest_from_template

        manifest = build_manifest_from_template(blueprint, template_name, project_id)
        return {"episode_code": episode_code, "shot_manifest": manifest, "status": "generated"}

    def execute_asset_generation(
        self, episode_code: str, episode_manifest: dict[str, object], providers_config_path: str, output_root: str
    ) -> dict[str, object]:
        """执行 SOP asset_generation 阶段：生成 provider API requests + 角色四视图 prompts (v4.0 P0-1)."""
        from aicomic.providers.request_builder import build_provider_requests

        result = build_provider_requests(
            manifest=episode_manifest,
            jobs=[],
            providers_config_path=Path(providers_config_path),
            output_root=Path(output_root),
        )

        # v4.0 P0-1: Generate four-view prompts for each character
        four_view_prompts = self._build_four_view_prompts(episode_manifest)

        return {
            "episode_code": episode_code,
            "provider_requests": result,
            "four_view_prompts": four_view_prompts,
            "status": "generated",
        }

    def _build_four_view_prompts(self, episode_manifest: dict[str, object]) -> list[dict[str, object]]:
        """P0-1: Build four-view (front/three_quarter/side/back) prompts for each character."""
        try:
            from aicomic.characters.character_views import (
                FourViewGenerator,
                ViewAngle,
                generate_view_prompt,
            )
        except ImportError:
            return []

        characters = episode_manifest.get("characters", [])
        if not characters:
            return []

        prompts: list[dict[str, object]] = []
        for char in characters:
            if not isinstance(char, dict):
                continue
            char_id = char.get("character_id", char.get("id", ""))
            char_name = char.get("name", "")
            char_desc = char.get("description", "")
            views: list[dict[str, object]] = []
            for angle in ViewAngle.ordered():
                prompt_text = generate_view_prompt(
                    character_description=char_desc,
                    angle=angle.value,
                    character_name=char_name,
                )
                views.append({"angle": angle.value, "prompt": prompt_text})
            prompts.append({"character_id": char_id, "name": char_name, "views": views})
        return prompts

    def execute_tts_subtitle(self, episode_code: str, episode_manifest: dict[str, object]) -> dict[str, object]:
        """执行 SOP tts_subtitle 阶段：生成字幕条目 + TTS prompt + 多语言 (v4.0 P0-4)."""
        from aicomic.providers.request_builder import build_tts_prompt
        from aicomic.render.subtitle_audio import build_subtitle_entries

        subtitles = build_subtitle_entries(episode_manifest, episode_code)
        shots = episode_manifest.get("shots", [])
        tts_prompts: list[dict[str, object]] = []
        if isinstance(shots, list):
            for s in shots:
                if isinstance(s, dict):
                    tts_prompts.append({"shot_id": s.get("shot_id", ""), "tts_prompt": build_tts_prompt(s)})

        # v4.0 P0-4: Multi-language subtitles
        multilang_subtitles = self._build_multilang_subtitles(episode_manifest, subtitles)

        return {
            "episode_code": episode_code,
            "subtitles": subtitles,
            "tts_prompts": tts_prompts,
            "multilang_subtitles": multilang_subtitles,
            "status": "generated",
        }

    def _build_multilang_subtitles(
        self, episode_manifest: dict[str, object], base_subtitles: list[object]
    ) -> dict[str, list[object]]:
        """P0-4: Build multi-language subtitle sets (zh, en, ja, ko)."""
        output_langs = episode_manifest.get("output_languages", ["zh"])
        if not isinstance(output_langs, list):
            output_langs = ["zh"]

        result: dict[str, list[object]] = {}
        # Extract text strings from subtitle entries for translation
        base_texts: list[str] = []
        for sub in base_subtitles:
            if isinstance(sub, dict):
                base_texts.append(str(sub.get("text", sub.get("content", ""))))
            else:
                base_texts.append(str(sub))

        for lang in output_langs:
            if lang == "zh":
                result["zh"] = base_subtitles
            else:
                try:
                    from aicomic.video_synthesis.i18n import translate_subtitles

                    translated_texts = translate_subtitles(base_texts, target_lang=str(lang))
                    # Rebuild subtitle entries with translated text
                    translated_entries: list[object] = []
                    for orig, txt in zip(base_subtitles, translated_texts):
                        if isinstance(orig, dict):
                            entry = dict(orig)
                            entry["text"] = txt
                            entry["lang"] = str(lang)
                            translated_entries.append(entry)
                        else:
                            translated_entries.append(txt)
                    result[str(lang)] = translated_entries
                except (ImportError, Exception):
                    result[str(lang)] = base_subtitles
        if "zh" not in result:
            result["zh"] = base_subtitles
        return result

    def execute_drift_gate(
        self, episode_code: str, shots: list[dict[str, object]], character_references: dict[str, dict[str, object]]
    ) -> dict[str, object]:
        """执行 v4.0 P0-3 防偏移检查：对每个镜头生成 drift gate 结果。

        Args:
            episode_code: Episode identifier.
            shots: List of shot dicts with character_id and optional generated_features.
            character_references: {character_id: {feature: value}} reference features.

        Returns:
            Dict with per-shot gate results and overall pass/fail status.
        """
        from aicomic.image_consistency.drift_gate import DriftGate

        gate = DriftGate(threshold=60, warn_threshold=75)
        results: list[dict[str, object]] = []
        pass_count = 0
        warn_count = 0
        fail_count = 0

        for shot in shots:
            shot_id = shot.get("shot_id", "")
            char_id = shot.get("character_id", "")
            ref = character_references.get(char_id, {})
            gen = shot.get("generated_features", {})
            gate_result = gate.check(ref, gen)
            results.append({"shot_id": shot_id, "character_id": char_id, **gate_result})
            status = gate_result["status"]
            if status == "PASS":
                pass_count += 1
            elif status == "WARN":
                warn_count += 1
            else:
                fail_count += 1

        overall = "PASS" if fail_count == 0 else ("WARN" if warn_count > 0 else "FAIL")
        return {
            "episode_code": episode_code,
            "gate_results": results,
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "overall_status": overall,
        }

    def execute_preview_render(
        self, episode_code: str, render_plan: dict[str, object], output_path: str, report_path: str
    ) -> dict[str, object]:
        """执行 SOP preview_render 阶段：渲染预览视频。"""
        from aicomic.render.preview_renderer import render_preview_video

        result = render_preview_video(render_plan, Path(output_path), Path(report_path))
        return {"episode_code": episode_code, "render_result": result, "status": "rendered"}

    def execute_publish_pack(self, episode_code: str, episode_manifest: dict[str, object]) -> dict[str, object]:
        """执行 SOP publish_pack 阶段：调用 build_enhanced_publish_pack 生成发布材料。

        之前 publish_pack 阶段只写 checkpoint 但不产出任何文件（空壳）。
        此方法桥接 SOP 单集管线与 publish 模块，确保 checkpoint 完成时
        publish pack 文件实际生成。
        """
        from aicomic.publish.publish_pack import build_enhanced_publish_pack

        pack = build_enhanced_publish_pack(episode_manifest, episode_code)
        return {"episode_code": episode_code, "publish_pack": pack, "status": "generated"}

    # ---- 内部 ----

    def _next_of(self, stage_id: str) -> str | None:
        index = self.step_ids.index(stage_id)
        return self.step_ids[index + 1] if index + 1 < len(self.step_ids) else None
