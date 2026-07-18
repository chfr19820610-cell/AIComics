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


def can_transition(current_status: str, next_status: str) -> bool:
    return next_status in ALLOWED_EPISODE_TRANSITIONS.get(current_status, set())


def advance_status(current_status: str, next_status: str) -> str:
    if not can_transition(current_status, next_status):
        raise ValueError(f"Invalid episode status transition: {current_status} -> {next_status}")
    return next_status

