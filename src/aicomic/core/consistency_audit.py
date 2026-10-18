"""资产馆一致性审计 Agent 输出（SOP §4③：判拒/判过 + 报告，无改写权）。

复用 image_consistency 的 dHash/similarity 底座，不在本层重造 hash；
缺图/读不开 → 结构化 error（不静默假绿）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from aicomic.image_consistency.image_consistency import image_dhash, similarity


def audit_character_assets(
    refs: list[str | Path],
    assets: list[str | Path],
    *,
    threshold: float = 0.80,
) -> dict[str, Any]:
    """两两比对 reference × asset：`{verdict, pairs:[{ref, asset, similarity, below_threshold}], threshold}`。"""
    pairs: list[dict[str, Any]] = []
    ref_hashes: list[tuple[str, int]] = []
    for ref in refs:
        try:
            ref_hashes.append((Path(ref).name, image_dhash(Path(ref))))
        except Exception as exc:
            return {"verdict": "error", "pairs": [], "threshold": threshold, "reason": f"reference 不可读: {Path(ref).name}: {exc}"}
    for asset in assets:
        try:
            asset_hash = image_dhash(Path(asset))
        except Exception as exc:
            return {"verdict": "error", "pairs": [], "threshold": threshold, "reason": f"asset 不可读: {Path(asset).name}: {exc}"}
        best = max((similarity(h, asset_hash), name) for name, h in ref_hashes) if ref_hashes else None
        if best is None:
            return {"verdict": "error", "pairs": [], "threshold": threshold, "reason": "无 reference 可比对"}
        score, ref_name = best
        pairs.append({
            "ref": ref_name,
            "asset": Path(asset).name,
            "similarity": score,
            "below_threshold": score < threshold,
        })
    verdict = "accept" if pairs and all(not p["below_threshold"] for p in pairs) else "reject"
    return {"verdict": verdict, "pairs": pairs, "threshold": threshold}
