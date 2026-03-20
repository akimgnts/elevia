from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key

from .semantic_guards import apply_semantic_guards
from .skill_priority_vocab import (
    ALL_RULES,
    LOCAL_ABSTRACTION_COLLISIONS,
    SUMMARY_DERIVATIONS,
    SkillPriorityRule,
)
from .task_phrase_mapping import detect_task_phrase_matches

_NULL_RE = re.compile(r"\x00+")
_DIGIT_HEAVY_RE = re.compile(r"\d")
_SECTION_HINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("skills", re.compile(r"\b(skills?|comp[eé]tences?|tools?|outils?|stack|technologies?)\b", re.I)),
    ("experience", re.compile(r"\b(experience|experiences|missions?|projects?|projets?)\b", re.I)),
    ("summary", re.compile(r"\b(summary|profile|profil|about)\b", re.I)),
    ("education", re.compile(r"\b(education|formation)\b", re.I)),
)

_SECTION_BONUS = {
    "skills": 0.08,
    "experience": 0.05,
    "summary": 0.0,
    "education": 0.0,
    "unknown": 0.0,
}
_STRICT_SECTION_TEXT_SCAN_LABELS = {
    "Tableau": {"skills"},
}
_SUMMARY_EXCLUDED_LABELS = {"English"}

_SKILL_POLICY = {
    "P1": ["protected_explicit", "matching_core_candidate"],
    "P2": ["protected_explicit", "representation_primary"],
    "P3": ["protected_explicit", "representation_primary"],
    "P4": ["display_only"],
}


@dataclass(frozen=True)
class SkillPriorityLayerResult:
    mapping_inputs: List[str] = field(default_factory=list)
    preserved_explicit_skills: List[dict] = field(default_factory=list)
    profile_summary_skills: List[dict] = field(default_factory=list)
    dropped_by_priority: List[dict] = field(default_factory=list)
    priority_trace: List[dict] = field(default_factory=list)
    priority_stats: Dict[str, Any] = field(default_factory=dict)


def _sanitize_text(text: str) -> str:
    cleaned = text or ""
    cleaned = cleaned.replace("ﬁ", "fi").replace("ﬂ", "fl")
    cleaned = cleaned.replace("Bl", "BI").replace("bl", "bi") if "power bl" in cleaned.lower() else cleaned
    cleaned = _NULL_RE.sub(" ", cleaned)
    return cleaned


def _normalize_for_scan(text: str) -> str:
    cleaned = _sanitize_text(text)
    cleaned = cleaned.replace("Power Bl", "Power BI").replace("power bl", "power bi")
    return normalize_canonical_key(cleaned)


def _iter_section_lines(cv_text: str) -> List[tuple[str, str]]:
    section = "unknown"
    out: List[tuple[str, str]] = []
    for raw_line in _sanitize_text(cv_text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for candidate_section, pattern in _SECTION_HINTS:
            if pattern.search(line):
                section = candidate_section
                break
        out.append((_normalize_for_scan(line), section))
    return out


def _matches_alias(normalized_text: str, alias: str) -> bool:
    if not normalized_text or not alias:
        return False
    pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
    return re.search(pattern, normalized_text) is not None


def _resolve_canonical_target(label: str) -> Optional[dict]:
    store = get_canonical_store()
    key = normalize_canonical_key(label)
    if not key:
        return None
    for cid, skill in store.id_to_skill.items():
        if normalize_canonical_key(str(skill.get("label") or "")) == key:
            return {
                "canonical_id": cid,
                "label": skill.get("label", cid),
                "strategy": "label_match",
            }
    cid = store.alias_to_id.get(key)
    strategy = "synonym_match"
    if not cid:
        targets = store.tool_to_ids.get(key) or []
        if not targets:
            return None
        cid = targets[0]
        strategy = "tool_match"
    skill = store.id_to_skill.get(cid, {})
    return {
        "canonical_id": cid,
        "label": skill.get("label", cid),
        "strategy": strategy,
    }


def _build_record(
    *,
    rule: SkillPriorityRule,
    matched_alias: str,
    source_section: str,
    source_confidence: float,
    is_explicit: bool,
    keep_reason: str,
) -> dict:
    return {
        "raw_text": matched_alias,
        "normalized_text": normalize_canonical_key(rule.label),
        "label": rule.label,
        "source_section": source_section,
        "source_confidence": round(source_confidence, 3),
        "candidate_type": rule.candidate_type,
        "priority_level": rule.priority_level,
        "is_explicit": bool(is_explicit),
        "canonical_target": _resolve_canonical_target(rule.label),
        "keep_reason": keep_reason,
        "drop_reason": None,
        "dominates": list(LOCAL_ABSTRACTION_COLLISIONS.get(rule.label, ())),
        "matching_use_policy": list(_SKILL_POLICY.get(rule.priority_level, ["display_only"])),
    }


def _best_source_for_rule(
    *,
    rule: SkillPriorityRule,
    validated_labels: Iterable[str],
    mapping_inputs: Iterable[str],
    section_lines: List[tuple[str, str]],
    normalized_cv_text: str,
    task_phrase_matches: Dict[str, dict],
) -> Optional[dict]:
    normalized_validated = [(_normalize_for_scan(item), item) for item in validated_labels if isinstance(item, str)]
    normalized_mapping = [(_normalize_for_scan(item), item) for item in mapping_inputs if isinstance(item, str)]

    best: Optional[dict] = None
    if rule.label in task_phrase_matches:
        task_match = task_phrase_matches[rule.label]
        best = {
            "matched_alias": task_match["matched_phrase"],
            "source_section": task_match["source_section"],
            "source_confidence": task_match["source_confidence"],
            "keep_reason": task_match["keep_reason"],
        }
    for alias in (normalize_canonical_key(rule.label), *[normalize_canonical_key(a) for a in rule.aliases]):
        if not alias:
            continue

        for norm, raw in normalized_validated:
            if _matches_alias(norm, alias):
                candidate = {
                    "matched_alias": raw,
                    "source_section": "unknown",
                    "source_confidence": 1.0,
                    "keep_reason": f"kept:validated_label_match:{alias}",
                }
                if best is None or candidate["source_confidence"] > best["source_confidence"]:
                    best = candidate

        for norm, raw in normalized_mapping:
            if _matches_alias(norm, alias):
                candidate = {
                    "matched_alias": raw,
                    "source_section": "unknown",
                    "source_confidence": 0.95,
                    "keep_reason": f"kept:mapping_input_match:{alias}",
                }
                if best is None or candidate["source_confidence"] > best["source_confidence"]:
                    best = candidate

        for line_norm, section in section_lines:
            allowed_sections = _STRICT_SECTION_TEXT_SCAN_LABELS.get(rule.label)
            if allowed_sections is not None and section not in allowed_sections:
                continue
            if _matches_alias(line_norm, alias):
                candidate = {
                    "matched_alias": alias,
                    "source_section": section,
                    "source_confidence": 0.9 + _SECTION_BONUS.get(section, 0.0),
                    "keep_reason": f"kept:text_match:{alias}",
                }
                if best is None or candidate["source_confidence"] > best["source_confidence"]:
                    best = candidate

        if best is None and rule.label not in _STRICT_SECTION_TEXT_SCAN_LABELS and _matches_alias(normalized_cv_text, alias):
            best = {
                "matched_alias": alias,
                "source_section": "unknown",
                "source_confidence": 0.88,
                "keep_reason": f"kept:text_body_match:{alias}",
            }
    return best


def _is_narrative_fragment(token: str) -> bool:
    norm = _normalize_for_scan(token)
    if not norm:
        return True
    words = norm.split()
    if len(words) >= 3 and _DIGIT_HEAVY_RE.search(norm):
        return True
    if len(words) >= 5:
        return True
    if sum(ch.isdigit() for ch in norm) >= 3:
        return True
    if len(words) >= 3 and any(word in {"with", "for", "using", "pour", "avec", "sur"} for word in words):
        return True
    return False


def _summary_rank(item: dict) -> tuple[int, float, str]:
    priority = item.get("priority_level")
    if priority == "P2":
        base = 0
    elif priority == "P3":
        base = 1
    elif priority == "P1":
        base = 2
    else:
        base = 3
    return (base, -float(item.get("source_confidence", 0.0) or 0.0), str(item.get("label") or ""))


def run_skill_priority_layer(
    *,
    cv_text: str,
    validated_labels: Iterable[str],
    mapping_inputs: Iterable[str],
) -> SkillPriorityLayerResult:
    base_mapping_inputs = list(mapping_inputs)
    normalized_cv_text = _normalize_for_scan(cv_text)
    section_lines = _iter_section_lines(cv_text)
    task_phrase_matches = {
        label: {
            "matched_phrase": match.matched_phrase,
            "source_section": match.source_section,
            "source_confidence": match.source_confidence,
            "keep_reason": match.keep_reason,
        }
        for label, match in detect_task_phrase_matches(
            section_lines=section_lines,
            mapping_inputs=base_mapping_inputs,
        ).items()
    }
    preserved: List[dict] = []
    dropped: List[dict] = []
    trace: List[dict] = []
    explicit_norms: set[str] = set()

    for rule in ALL_RULES:
        source = _best_source_for_rule(
            rule=rule,
            validated_labels=validated_labels,
            mapping_inputs=base_mapping_inputs,
            section_lines=section_lines,
            normalized_cv_text=normalized_cv_text,
            task_phrase_matches=task_phrase_matches,
        )
        if not source:
            continue
        record = _build_record(
            rule=rule,
            matched_alias=source["matched_alias"],
            source_section=source["source_section"],
            source_confidence=source["source_confidence"],
            is_explicit=True,
            keep_reason=source["keep_reason"],
        )
        if rule.priority_level == "P4":
            trace.append(
                {
                    "label": rule.label,
                    "decision": "display_only",
                    "reason": record["keep_reason"],
                    "priority_level": rule.priority_level,
                    "candidate_type": rule.candidate_type,
                    "matching_use_policy": record["matching_use_policy"],
                }
            )
            continue
        preserved.append(record)
        explicit_norms.add(normalize_canonical_key(rule.label))
        trace.append(
            {
                "label": rule.label,
                "decision": "keep",
                "reason": record["keep_reason"],
                "priority_level": rule.priority_level,
                "candidate_type": rule.candidate_type,
                "matching_use_policy": record["matching_use_policy"],
            }
        )

    preserved_guard_result = apply_semantic_guards(
        cv_text=cv_text,
        mapping_inputs=[],
        preserved_labels=[item["label"] for item in preserved],
        preserved_items=preserved,
    )
    preserved = list(preserved_guard_result.preserved_items or preserved)
    dropped.extend(preserved_guard_result.dropped)
    trace.extend(preserved_guard_result.trace)
    explicit_norms = {normalize_canonical_key(item["label"]) for item in preserved if item.get("label")}

    normalized_validated = [(_normalize_for_scan(item), item) for item in validated_labels if isinstance(item, str)]
    normalized_mapping_inputs = [(_normalize_for_scan(item), item) for item in base_mapping_inputs if isinstance(item, str)]
    for item in preserved:
        if item.get("priority_level") != "P1":
            continue
        blocker = normalize_canonical_key(item["label"])
        for abstract_label in LOCAL_ABSTRACTION_COLLISIONS.get(item["label"], ()):
            abstract_norm = normalize_canonical_key(abstract_label)
            matched_raw = None
            for norm, raw in normalized_validated + normalized_mapping_inputs:
                if _matches_alias(norm, abstract_norm):
                    matched_raw = raw
                    break
            if not matched_raw:
                continue
            dropped.append(
                {
                    "raw_text": matched_raw,
                    "normalized_text": abstract_norm,
                    "label": abstract_label,
                    "source_section": "unknown",
                    "source_confidence": 0.0,
                    "candidate_type": "domain",
                    "priority_level": "DROP",
                    "is_explicit": False,
                    "canonical_target": _resolve_canonical_target(abstract_label),
                    "keep_reason": None,
                    "drop_reason": f"dropped:local_abstraction_shadowed_by_{blocker}",
                    "dominates": [],
                    "matching_use_policy": [],
                }
            )
            trace.append(
                {
                    "label": abstract_label,
                    "decision": "drop",
                    "reason": f"dropped:local_abstraction_shadowed_by_{blocker}",
                    "priority_level": "DROP",
                    "candidate_type": "domain",
                }
            )

    filtered_mapping_inputs: List[str] = []
    seen_mapping: set[str] = set()
    for token in base_mapping_inputs:
        if not isinstance(token, str):
            continue
        token_key = _normalize_for_scan(token)
        if not token_key or token_key in seen_mapping:
            continue
        seen_mapping.add(token_key)
        if token_key in explicit_norms:
            filtered_mapping_inputs.append(token)
            continue
        if _is_narrative_fragment(token):
            dropped.append(
                {
                    "raw_text": token,
                    "normalized_text": token_key,
                    "label": token,
                    "source_section": "unknown",
                    "source_confidence": 0.0,
                    "candidate_type": "generic_phrase",
                    "priority_level": "DROP",
                    "is_explicit": False,
                    "canonical_target": None,
                    "keep_reason": None,
                    "drop_reason": "dropped:narrative_fragment",
                    "dominates": [],
                    "matching_use_policy": [],
                }
            )
            trace.append(
                {
                    "label": token,
                    "decision": "drop",
                    "reason": "dropped:narrative_fragment",
                    "priority_level": "DROP",
                    "candidate_type": "generic_phrase",
                }
            )
            continue
        filtered_mapping_inputs.append(token)

    resolvable_explicit = []
    for item in preserved:
        if item.get("canonical_target"):
            resolvable_explicit.append(item["label"])
    final_mapping_inputs: List[str] = []
    final_mapping_keys: set[str] = set()
    for token in resolvable_explicit + filtered_mapping_inputs:
        key = _normalize_for_scan(token)
        if not key or key in final_mapping_keys:
            continue
        final_mapping_keys.add(key)
        final_mapping_inputs.append(token)

    guard_result = apply_semantic_guards(
        cv_text=cv_text,
        mapping_inputs=final_mapping_inputs,
        preserved_labels=[item["label"] for item in preserved],
    )
    final_mapping_inputs = list(guard_result.mapping_inputs)
    dropped.extend(guard_result.dropped)
    trace.extend(guard_result.trace)

    summary_items: Dict[str, dict] = {}
    for item in preserved:
        policies = set(item.get("matching_use_policy") or [])
        if item.get("label") in _SUMMARY_EXCLUDED_LABELS:
            continue
        if "representation_primary" in policies or item.get("priority_level") == "P1":
            summary_items.setdefault(item["label"], dict(item))
        for derived_label in SUMMARY_DERIVATIONS.get(item["label"], ()):
            if derived_label in summary_items:
                continue
            derived = {
                "raw_text": item["label"],
                "normalized_text": normalize_canonical_key(derived_label),
                "label": derived_label,
                "source_section": item["source_section"],
                "source_confidence": item["source_confidence"],
                "candidate_type": "domain",
                "priority_level": "P3",
                "is_explicit": False,
                "canonical_target": _resolve_canonical_target(derived_label),
                "keep_reason": f"kept:derived_summary_from:{normalize_canonical_key(item['label'])}",
                "drop_reason": None,
                "dominates": [],
                "matching_use_policy": ["representation_primary"],
            }
            summary_items[derived_label] = derived
            trace.append(
                {
                    "label": derived_label,
                    "decision": "keep",
                    "reason": derived["keep_reason"],
                    "priority_level": "P3",
                    "candidate_type": "domain",
                    "matching_use_policy": derived["matching_use_policy"],
                }
            )

    profile_summary_skills = sorted(summary_items.values(), key=_summary_rank)[:10]
    preserved_explicit_skills = sorted(
        preserved,
        key=lambda item: (
            item.get("priority_level") != "P1",
            -float(item.get("source_confidence", 0.0) or 0.0),
            str(item.get("label") or ""),
        ),
    )

    stats = {
        "preserved_count": len(preserved_explicit_skills),
        "summary_count": len(profile_summary_skills),
        "dropped_count": len(dropped),
        "added_mapping_inputs_count": max(len(final_mapping_inputs) - len(base_mapping_inputs), 0),
        "protected_atomic_count": sum(1 for item in preserved_explicit_skills if item.get("priority_level") == "P1"),
        "task_phrase_match_count": len(task_phrase_matches),
        "guard_dropped_count": int(preserved_guard_result.stats.get("guard_dropped_count", 0) or 0)
        + int(guard_result.stats.get("guard_dropped_count", 0) or 0),
    }
    return SkillPriorityLayerResult(
        mapping_inputs=final_mapping_inputs,
        preserved_explicit_skills=preserved_explicit_skills,
        profile_summary_skills=profile_summary_skills,
        dropped_by_priority=dropped,
        priority_trace=trace,
        priority_stats=stats,
    )
