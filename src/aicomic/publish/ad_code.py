"""投流编号自动生成（SOP §10.4/§11：剧名-角色-卖点-版本-渠道-投放日期-审核人）。

七段全部必填、段内禁 `-`（劈段失明必红）；日期合法化 YYYYMMDD；可回溯是红线。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def build_ad_code(
    series: str,
    character: str,
    selling_point: str,
    version: str,
    channel: str,
    publish_date: str,
    auditor: str,
) -> str:
    raw = [series, character, selling_point, version, channel, auditor]
    for i, seg in enumerate(raw):
        if not str(seg).strip() or "-" in str(seg):
            raise ValueError(f"投流编号段{i + 1}非法（空/含劈段符）——可回溯红线: {seg!r}")
    try:
        d = datetime.strptime(str(publish_date), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"投放日期非法（需 YYYY-MM-DD）: {publish_date!r}") from exc
    return "-".join([str(s) for s in raw[:5]] + [d.strftime("%Y%m%d"), raw[5]])


def attach_to_compliance(pack: dict[str, Any], ad_code: str) -> dict[str, Any]:
    """compliance.json 联接：编号可回溯 + pack 内容保全。"""
    return {"ad_code": ad_code, "pack": dict(pack), "regulation": "AI漫剧投放编号可回溯校验（SOP §10.4）"}
