"""Consistency Service — cross-shot/single-panel character consistency checking.

Provides:
  - Description consistency analysis across multiple shots
  - Attribute-level consistency validation (clothing, hair color, etc.)
  - Consistency scoring and reporting
  - Auto-correction suggestions for detected inconsistencies
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from typing import Any

from aicomic.characters.database import list_characters
from aicomic.characters.models import Character, now_utc_iso

# ── Data models ──────────────────────────────────────────────────────────


@dataclass
class AttributeEntry:
    """A single character attribute extracted from a description."""
    category: str  # clothing, hair, eyes, accessory, build, other
    attribute: str  # e.g. "黑色长发", "蓝色衬衫"
    source_text: str = ""
    confidence: float = 1.0


@dataclass
class ShotCharacterState:
    """Character appearance state in a single shot."""
    character_name: str
    shot_id: str
    attributes: list[AttributeEntry] = field(default_factory=list)
    raw_prompt: str = ""
    source: str = ""


@dataclass
class ConsistencyIssue:
    """A detected inconsistency between two shots."""
    character_name: str
    attribute_category: str
    attribute_name: str
    shot_id_a: str
    value_a: str
    shot_id_b: str
    value_b: str
    severity: str = "warning"  # error, warning, info
    description: str = ""


@dataclass
class ConsistencyReport:
    """Full consistency report for a set of shots or an episode."""
    report_id: str
    project_id: str = ""
    episode_code: str = ""
    total_shots: int = 0
    total_characters: int = 0
    issues: list[ConsistencyIssue] = field(default_factory=list)
    overall_score: float = 1.0
    summary: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id, "project_id": self.project_id,
            "episode_code": self.episode_code, "total_shots": self.total_shots,
            "total_characters": self.total_characters,
            "issues": [{"character_name": i.character_name, "attribute_category": i.attribute_category,
                        "attribute_name": i.attribute_name, "shot_id_a": i.shot_id_a, "value_a": i.value_a,
                        "shot_id_b": i.shot_id_b, "value_b": i.value_b, "severity": i.severity,
                        "description": i.description} for i in self.issues],
            "overall_score": self.overall_score, "summary": self.summary, "created_at": self.created_at,
        }


@dataclass
class CorrectionSuggestion:
    """Suggested fix for an attribute inconsistency."""
    attribute_category: str
    attribute_name: str
    shot_ids: list[str]
    suggested_value: str
    reason: str = ""
    confidence: float = 0.0


# ── Attribute extraction ─────────────────────────────────────────────────

_ATTRIBUTE_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("clothing","上衣",re.compile(r"(?:穿|着|身着|身穿|穿着?)(?:了)?[\u4e00-\u9fff]*(?:衬衫|T恤|上衣|外套|夹克|西装|卫衣|毛衣|背心|马甲|汉服|和服|旗袍)")),
    ("clothing","下装",re.compile(r"(?:穿|着|身着|身穿|穿着?)(?:了)?[\u4e00-\u9fff]*(?:裤子|短裤|长裤|裙子|短裙|长裙|牛仔裤|西裤|百褶裙)")),
    ("clothing","鞋子",re.compile(r"(?:穿|着|脚穿|脚踏)(?:了)?[\u4e00-\u9fff]*(?:鞋|靴|运动鞋|皮鞋|高跟鞋|帆布鞋)")),
    ("clothing","配饰",re.compile(r"(?:戴|佩|系|围|披)(?:着|了)?[\u4e00-\u9fff]*(?:围巾|领带|丝巾|项链|耳环|手链|戒指|帽子|头巾)")),
    ("hair","发色",re.compile(r"(?:黑|棕|金|白|银|灰|红|蓝|紫|粉|绿|黄|橙|褐|栗|亚麻)(?:色)?[长中短板寸](?:发|头发|辫子|马尾|短发|长发|卷发|直发)")),
    ("hair","发色",re.compile(r"(?:头发|发色|发)(?:为|是)?[\u4e00-\u9fff]{1,4}(?:色|发)")),
    ("hair","发型",re.compile(r"(?:长发|短发|卷发|直发|马尾|辫子|丸子头|盘发|披肩发|寸头|光头|齐耳短发|波波头|大波浪|梨花头)")),
    ("eyes","瞳色",re.compile(r"(?:黑|棕|金|银|白|红|蓝|紫|粉|绿|黄|灰|褐|琥珀|碧|墨)(?:色)?(?:瞳孔|眼睛|眼珠|眸子|眼眸|瞳)")),
    ("eyes","眼型",re.compile(r"(?:丹凤眼|桃花眼|杏眼|圆眼|细眼|大眼|小眼|眯眯眼|单眼皮|双眼皮)")),
    ("build","体型",re.compile(r"(?:高大|魁梧|苗条|纤细|丰满|结实|健壮|瘦弱|肥胖|匀称|修长|娇小|高挑)")),
    ("accessory","眼镜",re.compile(r"(?:戴|佩)(?:着|了)?(?:眼镜|墨镜|金丝眼镜|黑框眼镜|隐形眼镜)")),
    ("accessory","饰物",re.compile(r"(?:持|拿|握|拎|背|挎)(?:着|了)?[\u4e00-\u9fff]*(?:包|伞|剑|扇|杖|法器|手机|书本)")),
]


def extract_attributes(text: str) -> list[AttributeEntry]:
    """Extract character attributes from a description or prompt."""
    entries: list[AttributeEntry] = []
    seen: set[str] = set()
    for category, attr_type, pattern in _ATTRIBUTE_PATTERNS:
        for match in pattern.finditer(text):
            m = match.group(0)
            k = f"{category}:{m}"
            if k not in seen:
                seen.add(k)
                entries.append(AttributeEntry(category=category, attribute=m, source_text=m, confidence=0.9))
    color_noun = re.compile(r"([\u4e00-\u9fff]{1,3}(?:色))[\u4e00-\u9fff]{0,8}(?:的)?([\u4e00-\u9fff]{1,6})")
    for match in color_noun.finditer(text):
        f = match.group(0)
        k = f"color:{f}"
        if k not in seen and len(f) <= 16:
            seen.add(k)
            entries.append(AttributeEntry(category="other", attribute=f, source_text=f, confidence=0.6))
    return entries


def _dedup_attributes(attrs: list[AttributeEntry]) -> list[AttributeEntry]:
    seen: set[str] = set()
    return [a for a in attrs if not (k := f"{a.category}:{a.attribute}", k in seen or seen.add(k))[0]]


# ── Database schema ──────────────────────────────────────────────────────


def ensure_consistency_schema(connection: sqlite3.Connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS consistency_reports (id TEXT PRIMARY KEY, project_id TEXT DEFAULT '', episode_code TEXT DEFAULT '', total_shots INTEGER DEFAULT 0, total_characters INTEGER DEFAULT 0, issue_count INTEGER DEFAULT 0, overall_score REAL DEFAULT 1.0, summary TEXT DEFAULT '', report_data TEXT DEFAULT '{}', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS character_state_snapshots (id TEXT PRIMARY KEY, character_id TEXT NOT NULL, shot_id TEXT NOT NULL, episode_code TEXT DEFAULT '', project_id TEXT DEFAULT '', attributes_json TEXT DEFAULT '[]', raw_prompt TEXT DEFAULT '', consistency_score REAL DEFAULT 1.0, created_at TEXT NOT NULL, FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS idx_consistency_report_project ON consistency_reports(project_id);
        CREATE INDEX IF NOT EXISTS idx_consistency_report_episode ON consistency_reports(episode_code);
        CREATE INDEX IF NOT EXISTS idx_char_state_shot ON character_state_snapshots(shot_id);
        CREATE INDEX IF NOT EXISTS idx_char_state_char ON character_state_snapshots(character_id);
    """)
    connection.commit()


# ── Database helpers ─────────────────────────────────────────────────────


def _save_report(connection: sqlite3.Connection, report: ConsistencyReport) -> str:
    connection.execute(
        "INSERT INTO consistency_reports (id, project_id, episode_code, total_shots, total_characters, "
        "issue_count, overall_score, summary, report_data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (report.report_id, report.project_id, report.episode_code, report.total_shots,
         report.total_characters, len(report.issues), report.overall_score,
         report.summary, json.dumps(report.to_dict(), ensure_ascii=False), report.created_at),
    )
    connection.commit()
    return report.report_id


def _save_state_snapshot(connection: sqlite3.Connection, character_id: str, shot_id: str,
                         attributes: list[AttributeEntry], episode_code: str = "", project_id: str = "",
                         raw_prompt: str = "") -> str:
    snapshot_id = str(uuid.uuid4())
    now = now_utc_iso()
    connection.execute(
        "INSERT INTO character_state_snapshots (id, character_id, shot_id, episode_code, project_id, "
        "attributes_json, raw_prompt, consistency_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (snapshot_id, character_id, shot_id, episode_code, project_id,
         json.dumps([a.__dict__ for a in attributes], ensure_ascii=False, default=str),
         raw_prompt, 1.0, now),
    )
    connection.commit()
    return snapshot_id


# ── Consistency Service ──────────────────────────────────────────────────


class ConsistencyService:
    """Cross-shot character consistency checking and reporting."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def analyze_shot(self, shot_id: str, characters_in_shot: list[dict[str, Any]],
                     episode_code: str = "", project_id: str = "") -> list[ShotCharacterState]:
        """Analyze all characters in a single shot and snapshot their state."""
        states: list[ShotCharacterState] = []
        for entry in characters_in_shot:
            char_id = entry.get("character_id", "")
            name = entry.get("name", "")
            prompt = entry.get("prompt", "")
            ref = entry.get("reference_prompt", "")
            attrs = _dedup_attributes(extract_attributes(ref) + extract_attributes(prompt))
            state = ShotCharacterState(character_name=name, shot_id=shot_id, attributes=attrs,
                                       raw_prompt=prompt, source="reference_prompt + image_prompt")
            states.append(state)
            if char_id:
                _save_state_snapshot(self._connection, char_id, shot_id, attrs, episode_code=episode_code,
                                     project_id=project_id, raw_prompt=prompt)
        return states

    def check_cross_shot_consistency(self, shot_states: list[ShotCharacterState]) -> list[ConsistencyIssue]:
        """Compare character states across multiple shots."""
        issues: list[ConsistencyIssue] = []
        per_char: dict[str, list[ShotCharacterState]] = {}
        for s in shot_states:
            per_char.setdefault(s.character_name, []).append(s)

        for char_name, states in per_char.items():
            if len(states) < 2:
                continue
            cat_occurrences: dict[str, list[tuple[str, str]]] = {}
            for st in states:
                for attr in st.attributes:
                    cat_occurrences.setdefault(attr.category, []).append((st.shot_id, attr.attribute))

            for category, occurrences in cat_occurrences.items():
                shot_vals: dict[str, set[str]] = {}
                for sid, val in occurrences:
                    shot_vals.setdefault(sid, set()).add(val)
                sids = list(shot_vals.keys())
                for i in range(len(sids)):
                    for j in range(i + 1, len(sids)):
                        a, b = sids[i], sids[j]
                        va, vb = shot_vals[a], shot_vals[b]
                        if va and vb and va != vb and (va - vb) and (vb - va):
                            issues.append(ConsistencyIssue(
                                character_name=char_name, attribute_category=category, attribute_name=category,
                                shot_id_a=a, value_a=", ".join(sorted(va)),
                                shot_id_b=b, value_b=", ".join(sorted(vb)),
                                severity="error" if category in ("hair", "eyes", "build") else "warning",
                                description=f"角色「{char_name}」在 {a} 和 {b} 中的{category}不一致："
                                            f"「{', '.join(sorted(va))}」vs「{', '.join(sorted(vb))}」",
                            ))
        return issues

    def generate_report(self, shot_states: list[ShotCharacterState], project_id: str = "",
                        episode_code: str = "") -> ConsistencyReport:
        """Generate a full consistency report from shot states."""
        issues = self.check_cross_shot_consistency(shot_states)
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        score = max(0.0, 1.0 - (errors * 0.15 + warnings * 0.05)) if issues else 1.0
        char_names = sorted(set(s.character_name for s in shot_states))

        if not issues:
            summary = f"一致性检查通过：{len(shot_states)}个分镜中所有角色（{', '.join(char_names)}）的外观属性保持一致"
        else:
            summary = f"发现 {len(issues)} 个一致性问题（{errors}个严重，{warnings}个警告），涉及角色：{', '.join(char_names)}"

        report = ConsistencyReport(report_id=str(uuid.uuid4()), project_id=project_id, episode_code=episode_code,
                                   total_shots=len(shot_states), total_characters=len(char_names),
                                   issues=issues, overall_score=round(score, 4), summary=summary,
                                   created_at=now_utc_iso())
        _save_report(self._connection, report)
        return report

    def analyze_episode_manifest(self, manifest: dict[str, Any], character_service: Any,
                                 project_id: str = "") -> ConsistencyReport:
        """Analyze an entire episode manifest for character consistency."""
        all_states: list[ShotCharacterState] = []
        for ep in manifest.get("episodes", []):
            ep_code = ep.get("episode_code", "")
            for shot in ep.get("shots", []):
                shot_id = shot.get("shot_id", "")
                combined = f"{shot.get('visual', '')}，{shot.get('action', '')}，{shot.get('emotion', '')}"
                chars = list_characters(self._connection, project_id=project_id)
                for char_name in shot.get("characters", []):
                    matching = [c for c in chars if c.get("name") == char_name]
                    ref_prompt = matching[0].get("reference_prompt", "") if matching else ""
                    attrs = _dedup_attributes(extract_attributes(ref_prompt) + extract_attributes(combined))
                    all_states.append(ShotCharacterState(
                        character_name=char_name, shot_id=shot_id, attributes=attrs,
                        raw_prompt=combined, source="manifest",
                    ))
        episodes = manifest.get("episodes", [])
        return self.generate_report(all_states, project_id=project_id,
                                    episode_code=episodes[0].get("episode_code", "") if episodes else "")

    def check_character_against_reference(self, character: Character | dict[str, Any],
                                          image_prompt: str) -> list[ConsistencyIssue]:
        """Check whether an image prompt is consistent with a character's reference."""
        if isinstance(character, dict):
            ref_prompt, name = character.get("reference_prompt", ""), character.get("name", "")
        else:
            ref_prompt, name = character.reference_prompt, character.name
        ref_attrs = extract_attributes(ref_prompt)
        prompt_attrs = extract_attributes(image_prompt)
        ref_by_cat: dict[str, set[str]] = {}
        for attr in ref_attrs:
            ref_by_cat.setdefault(attr.category, set()).add(attr.attribute)
        prompt_by_cat: dict[str, set[str]] = {}
        for attr in prompt_attrs:
            prompt_by_cat.setdefault(attr.category, set()).add(attr.attribute)

        issues: list[ConsistencyIssue] = []
        for category, ref_vals in ref_by_cat.items():
            prompt_vals = prompt_by_cat.get(category, set())
            for pv in prompt_vals:
                if pv not in ref_vals and _is_contradictory(ref_vals, pv):
                    issues.append(ConsistencyIssue(
                        character_name=name, attribute_category=category, attribute_name=category,
                        shot_id_a="reference", value_a=", ".join(sorted(ref_vals)),
                        shot_id_b="prompt", value_b=pv,
                        severity="error" if category in ("hair", "eyes") else "warning",
                        description=f"角色「{name}」的参考设定中{category}为「{', '.join(sorted(ref_vals))}」，"
                                    f"但生成 prompt 中使用了「{pv}」",
                    ))
        return issues

    def suggest_corrections(self, issues: list[ConsistencyIssue],
                            character_references: dict[str, str]) -> list[CorrectionSuggestion]:
        """Generate correction suggestions for detected issues."""
        suggestions: list[CorrectionSuggestion] = []
        for issue in issues:
            ref_attrs = extract_attributes(character_references.get(issue.character_name, ""))
            canonical = ""
            for attr in ref_attrs:
                if attr.category == issue.attribute_category:
                    canonical = attr.attribute
                    break
            suggestions.append(CorrectionSuggestion(
                attribute_category=issue.attribute_category, attribute_name=issue.attribute_name,
                shot_ids=[issue.shot_id_b], suggested_value=canonical or issue.value_a,
                reason=issue.description, confidence=0.85,
            ))
        return suggestions

    def get_recent_reports(self, project_id: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Get recent consistency reports."""
        if project_id:
            cursor = self._connection.execute(
                "SELECT * FROM consistency_reports WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            )
        else:
            cursor = self._connection.execute(
                "SELECT * FROM consistency_reports ORDER BY created_at DESC LIMIT ?", (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_report_by_id(self, report_id: str) -> dict[str, Any] | None:
        cursor = self._connection.execute("SELECT * FROM consistency_reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ── Helper functions ─────────────────────────────────────────────────────


def _is_contradictory(reference_values: set[str], prompt_value: str) -> bool:
    opposite_pairs = {"黑":"白","白":"黑","红":"绿","绿":"红","蓝":"黄","黄":"蓝","金":"银","银":"金","长":"短","短":"长","卷":"直","直":"卷","浓":"淡","淡":"浓","深":"浅","浅":"深"}
    for ref_val in reference_values:
        for k, op in opposite_pairs.items():
            if (k in prompt_value and op in ref_val) or (op in prompt_value and k in ref_val):
                return True
    hair_types = {"直发","卷发","长发","短发","马尾","辫子","丸子头","盘发","披肩发","寸头","光头","齐耳短发","波波头","大波浪","梨花头","黑长直","黑长直发"}
    for ref_val in reference_values:
        for ht in hair_types:
            if ht in ref_val and ht not in prompt_value and any(o != ht and o in prompt_value for o in hair_types):
                return True
    return False
