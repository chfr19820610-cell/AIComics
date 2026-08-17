"""图像级角色一致性锁定（ACOM-0.7.1）。

立绘母版(Master Sheet) + 图像级 pHash 比对锁脸 + ComfyUI IPAdapter/ControlNet/LoRA
工作流编排 + 漫剧单集产线一键化。
"""

from aicomic.image_consistency.comfyui_locks import (
    LockModelStatus,
    build_locked_workflow,
    probe_lock_models,
    validate_locked_workflow,
)
from aicomic.image_consistency.image_consistency import (
    FrameCheck,
    ImageConsistencyService,
    face_approx_crop,
    image_dhash,
    similarity,
)
from aicomic.image_consistency.master_sheet import (
    MasterSheetEntry,
    default_lock_config,
    ensure_master_sheet_schema,
    get_master_by_character,
    get_master_by_name,
    list_masters,
    mark_locked,
    register_master,
    update_master_dna,
)
from aicomic.image_consistency.one_shot_pipeline import (
    OneShotPipeline,
    ShotSpec,
    synth_master_image,
    write_pipeline_report,
)

__all__ = [
    "MasterSheetEntry", "default_lock_config", "ensure_master_sheet_schema",
    "get_master_by_character", "get_master_by_name", "list_masters",
    "mark_locked", "register_master", "update_master_dna",
    "FrameCheck", "ImageConsistencyService", "face_approx_crop", "image_dhash",
    "similarity",
    "LockModelStatus", "build_locked_workflow", "probe_lock_models",
    "validate_locked_workflow",
    "OneShotPipeline", "ShotSpec", "synth_master_image", "write_pipeline_report",
]
