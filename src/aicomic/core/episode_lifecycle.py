from __future__ import annotations


ALLOWED_EPISODE_TRANSITIONS = {
    "idea": {"script_ready"},
    "script_ready": {"shotlist_ready", "prompt_ready"},
    "shotlist_ready": {"prompt_ready"},
    "prompt_ready": {"jobs_ready"},
    "jobs_ready": {"assets_partial", "assets_ready"},
    "assets_partial": {"assets_ready", "preview_rendered"},
    "assets_ready": {"preview_rendered"},
    "preview_rendered": {"release_rendered", "publish_pack_ready"},
    "release_rendered": {"publish_pack_ready"},
    "publish_pack_ready": {"archived"},
    "archived": set(),
}

# ── SOP 8-stage → EpisodeState mapping ──
# Explicit mapping so pipeline_coordinator can sync episode status
# whenever a SOP stage checkpoint is completed.
STAGE_TO_STATUS: dict[str, str] = {
    "project_setup": "idea",
    "story_bible": "script_ready",
    "episode_outline": "script_ready",
    "shot_breakdown": "shotlist_ready",
    "asset_generation": "assets_ready",
    "tts_subtitle": "assets_ready",
    "preview_render": "preview_rendered",
    "publish_pack": "publish_pack_ready",
}


def stage_to_episode_status(stage_id: str) -> str | None:
    """Map a SOP pipeline stage_id to the corresponding EpisodeState.

    Returns None for stages that don't have a direct state counterpart.
    """
    return STAGE_TO_STATUS.get(stage_id)


def can_transition(current_status: str, next_status: str) -> bool:
    return next_status in ALLOWED_EPISODE_TRANSITIONS.get(current_status, set())


def advance_status(current_status: str, next_status: str) -> str:
    if not can_transition(current_status, next_status):
        raise ValueError(f"Invalid episode status transition: {current_status} -> {next_status}")
    return next_status

