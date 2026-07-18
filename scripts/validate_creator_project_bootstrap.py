from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aicomic.core.manifest import load_json
from aicomic.core.project_initializer import initialize_project


def main() -> int:
    run_at = datetime.now().astimezone().isoformat()
    with tempfile.TemporaryDirectory(prefix="aicomic_creator_bootstrap_") as temp_dir:
        output_root = Path(temp_dir)
        payload = initialize_project(
            output_root,
            "Creator 验证项目",
            "都市反转短剧",
            "动漫漫剧",
            "creator_validation_project",
            logline="一个普通女孩在高压公司中完成身份反转。",
            protagonist_name="林夏",
            target_audience="短剧用户",
            tone="反转强、情绪快",
            season_hook="每集结尾都要把身份悬念往前推一格。",
            episode_target_count=8,
        )
        project_root = Path(str(payload["project_root"]))
        project_manifest = load_json(project_root / "manifests" / "project_manifest.json")
        season_manifest = load_json(project_root / "manifests" / "season_manifest.json")
        episode_blueprint = load_json(project_root / "docs" / "episode_blueprint.json")
        prompt_pack = load_json(project_root / "prompts" / "prompt_pack_template.json")

        checks = {
            "project_root_exists": project_root.exists(),
            "story_bible_exists": (project_root / "docs" / "creator_story_bible.json").exists(),
            "character_bible_exists": (project_root / "docs" / "character_bible.json").exists(),
            "style_bible_exists": (project_root / "docs" / "style_bible.json").exists(),
            "episode_blueprint_exists": (project_root / "docs" / "episode_blueprint.json").exists(),
            "prompt_pack_exists": (project_root / "prompts" / "prompt_pack_template.json").exists(),
            "release_checklist_exists": (project_root / "publish" / "release_checklist.md").exists(),
            "creator_profile_written": bool(project_manifest.get("creator_profile")),
            "season_hook_written": str(season_manifest.get("creator_plan", {}).get("season_hook", "")) != "",
            "episode_target_count_written": int(episode_blueprint.get("episode_target_count", 0)) == 8,
            "prompt_pack_image_template_written": str(prompt_pack.get("image_prompt_template", "")) != "",
        }

        payload = {
            "run_at": run_at,
            "project_root": str(project_root),
            "checks": checks,
            "passed": all(checks.values()),
        }

    report_path = PROJECT_ROOT / "reports" / "creator_project_bootstrap_validation_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
