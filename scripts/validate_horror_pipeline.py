from __future__ import annotations

import json
import tempfile
from pathlib import Path

from aicomic.core.horror_pipeline import build_horror_episode_manifest, build_horror_story_blueprint
from aicomic.core.job_builder import build_jobs_from_episode_manifest
from aicomic.providers.request_builder import build_image_prompt
from web.backend.services.creator_action_service import filter_provider_requests_by_id


def main() -> int:
    blueprint = build_horror_story_blueprint(
        "村里老人说，夜里不能回头看井口。",
        episode_code="E01",
        target_seconds=360,
        max_shots=60,
    )
    if len(blueprint["acts"]) != 5:
        raise RuntimeError(f"expected 5 acts, got {len(blueprint['acts'])}")
    if not 40 <= int(blueprint["shot_count"]) <= 60:
        raise RuntimeError(f"unexpected shot_count: {blueprint['shot_count']}")
    manifest = build_horror_episode_manifest(blueprint)
    episode = manifest["episodes"][0]
    shots = episode["shots"]
    total_duration = sum(int(shot["duration"]) for shot in shots)
    if len(shots) != int(blueprint["shot_count"]):
        raise RuntimeError("shot count mismatch between blueprint and manifest")
    if not 300 <= total_duration <= 420:
        raise RuntimeError(f"unexpected total duration: {total_duration}")
    if len({shot["shot_id"] for shot in shots}) != len(shots):
        raise RuntimeError("shot_id values are not unique")
    missing_horror_fields = [
        shot["shot_id"]
        for shot in shots
        if not all(shot.get(key) for key in ("act_id", "horror_beat", "continuity_anchor", "avoidance_strategy", "sound_cue"))
    ]
    if missing_horror_fields:
        raise RuntimeError(f"missing horror fields: {missing_horror_fields[:5]}")
    jobs = build_jobs_from_episode_manifest(manifest)
    if not jobs:
        raise RuntimeError("horror manifest did not produce jobs")
    filtered_requests = filter_provider_requests_by_id(
        {
            "request_count": 2,
            "requests": [
                {"request_id": "REQ_JOB_E01_S01_IMG"},
                {"request_id": "REQ_JOB_E01_S01_TTS"},
            ],
        },
        {"REQ_JOB_E01_S01_IMG"},
    )
    if filtered_requests["request_count"] != 1 or filtered_requests["requests"][0]["request_id"] != "REQ_JOB_E01_S01_IMG":
        raise RuntimeError("horror request id filter failed")
    prompt = build_image_prompt(str(episode["title"]), shots[0])
    if "Vertical 9:16 anime folk horror scene" not in prompt or "no subtitles" not in prompt:
        raise RuntimeError("horror visual prompt context missing from image prompt")
    if "talisman script" not in prompt or "posted sheets" not in prompt or "printed notices" not in prompt:
        raise RuntimeError("horror visual prompt anti-readable-marking guard missing")
    talisman_shot = next((shot for shot in shots if shot.get("continuity_anchor") == "符纸"), None)
    if talisman_shot is None:
        raise RuntimeError("expected at least one talisman shot in horror manifest")
    talisman_prompt = build_image_prompt(str(episode["title"]), talisman_shot)
    if "blank yellow ritual paper strip with torn edges and no writing" not in talisman_prompt:
        raise RuntimeError("talisman anchor prompt did not switch to blank ritual paper strip")
    if any("\u4e00" <= char <= "\u9fff" for char in prompt):
        raise RuntimeError("horror visual prompt must not contain CJK characters")

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "horror_validation_report.json"
        output_path.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "act_count": len(blueprint["acts"]),
                    "shot_count": len(shots),
                    "total_duration_seconds": total_duration,
                    "job_count": len(jobs),
                    "sample_prompt": prompt,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    print("horror_pipeline_validation=passed")
    print(f"shot_count={len(shots)}")
    print(f"total_duration_seconds={total_duration}")
    print(f"job_count={len(jobs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
