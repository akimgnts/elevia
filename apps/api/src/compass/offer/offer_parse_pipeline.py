from __future__ import annotations

import copy
import json
from typing import Any, Dict, Iterable, List, Sequence
import re

from compass.contracts import OfferDescriptionStructuredV1
from compass.pipeline.structured_extraction_stage import run_structured_extraction_stage
from compass.text_structurer import structure_offer_text_v1
from offer.offer_cluster import detect_offer_cluster
from offer.offer_description_structurer import structure_offer_description

from .offer_canonical_mapping_stage import run_offer_canonical_mapping_stage


_REQUIREMENT_SPLIT_RE = re.compile(r"\s*,\s*|\s*;\s*")
_GENERIC_BLOCKLIST = {
    "communication",
    "gestion de projets",
    "gestion",
    "analyse",
    "projets",
    "processus",
    "anglais",
    "maitrise",
}
_PIPELINE_CACHE_CAP = 1024
_PIPELINE_CACHE: Dict[str, Dict[str, Any]] = {}


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _dedupe_preserve(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        label = str(value or "").strip()
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def _extract_skill_labels(skills_display: Iterable[Any] | None, skills: Iterable[Any] | None) -> List[str]:
    labels: List[str] = []
    seen: set[str] = set()
    for item in list(skills_display or []):
        label = ""
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
        elif isinstance(item, str):
            label = item.strip()
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    for item in list(skills or []):
        label = str(item or "").strip()
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def _extract_requirement_skill_candidates(lines: Sequence[str]) -> List[str]:
    candidates: List[str] = []
    seen: set[str] = set()
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        normalized = _normalize(text)
        if normalized.startswith("competences") or normalized.startswith("compétences"):
            _, _, tail = text.partition(":")
            pieces = _REQUIREMENT_SPLIT_RE.split(tail or text)
        else:
            pieces = [text]
        for piece in pieces:
            label = piece.strip(" -•*")
            label = re.sub(r"\b(apprecie|apprécié|souhaite|souhaité|required|requireds?)\b.*$", "", label, flags=re.I).strip(" -,:;")
            key = _normalize(label)
            if not key or key in seen:
                continue
            if len(key.split()) > 5:
                continue
            if key in _GENERIC_BLOCKLIST:
                continue
            if key.startswith("formation ") or "experience" in key or "anglais" in key:
                continue
            seen.add(key)
            candidates.append(label)
    return candidates


def _build_offer_structured_text(
    *,
    title: str,
    missions: Sequence[str],
    fallback_description: str,
) -> str:
    lines: List[str] = []
    if title:
        lines.extend(["summary", title.strip()])
    if missions:
        lines.append("missions")
        for mission in missions[:8]:
            if mission:
                lines.append(f"- {mission.strip()}")
    elif fallback_description:
        lines.extend(["missions", fallback_description.strip()])
    return "\n".join(line for line in lines if line)


def _offer_cache_key(offer: Dict[str, Any]) -> str:
    payload = {
        "id": offer.get("id"),
        "title": offer.get("title"),
        "description": offer.get("description") or offer.get("display_description"),
        "skills": list(offer.get("skills") or []),
        "skills_display": list(offer.get("skills_display") or []),
        "offer_cluster": offer.get("offer_cluster"),
        "publication_date": offer.get("publication_date"),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def run_offer_parse_pipeline(offer: Dict[str, Any]) -> Dict[str, Any]:
    cache_key = _offer_cache_key(offer)
    cached = _PIPELINE_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)

    title = str(offer.get("title") or "").strip()
    description = str(offer.get("description") or offer.get("display_description") or "").strip()
    skill_labels = _extract_skill_labels(offer.get("skills_display"), offer.get("skills"))

    description_structured = structure_offer_description(description, esco_skills=skill_labels[:12], lang_hint="fr")
    description_structured_v1 = structure_offer_text_v1(description, esco_labels=skill_labels[:12])
    if isinstance(description_structured_v1, dict):
        description_structured_v1 = OfferDescriptionStructuredV1(**description_structured_v1)

    mission_lines = list(description_structured.get("missions") or [])[:8]
    requirement_lines = list(description_structured.get("profile") or [])[:6]
    for mission in list(description_structured_v1.missions or [])[:8]:
        if mission and mission not in mission_lines:
            mission_lines.append(mission)
    for requirement in list(description_structured_v1.requirements or [])[:6]:
        if requirement and requirement not in requirement_lines:
            requirement_lines.append(requirement)

    requirement_skill_candidates = _extract_requirement_skill_candidates(requirement_lines)
    tools_stack = list(description_structured_v1.tools_stack or [])[:8]

    structured_text = _build_offer_structured_text(
        title=title,
        missions=mission_lines,
        fallback_description=description,
    )
    base_mapping_inputs = _dedupe_preserve([title, *requirement_skill_candidates[:10], *skill_labels[:12], *tools_stack[:8]])
    structured_extraction = run_structured_extraction_stage(
        cv_text=structured_text,
        base_mapping_inputs=base_mapping_inputs,
    )

    offer_cluster = str(offer.get("offer_cluster") or "")
    if not offer_cluster:
        offer_cluster, _, _ = detect_offer_cluster(title, description, skill_labels)

    canonical_mapping = run_offer_canonical_mapping_stage(
        offer_cluster=offer_cluster,
        structured_extraction=structured_extraction,
        validated_labels=skill_labels,
    )

    result = {
        "title": title,
        "description": description,
        "offer_cluster": offer_cluster,
        "description_structured": description_structured,
        "description_structured_v1": description_structured_v1,
        "mission_lines": mission_lines,
        "requirement_lines": requirement_lines,
        "skill_labels": skill_labels,
        "requirement_skill_candidates": requirement_skill_candidates,
        "tools_stack": tools_stack,
        "structured_units": list(structured_extraction.structured_units or []),
        "top_signal_units": list(structured_extraction.top_signal_units or []),
        "secondary_signal_units": list(structured_extraction.secondary_signal_units or []),
        "mapping_inputs": list(canonical_mapping.mapping_inputs or []),
        "canonical_skills": list(canonical_mapping.canonical_skills or []),
        "canonical_domains": list(canonical_mapping.canonical_domains or []),
        "canonical_enriched_labels": list(canonical_mapping.canonical_enriched_labels or []),
        "unresolved": list(canonical_mapping.unresolved or []),
        "near_matches": list(canonical_mapping.near_matches or []),
        "canonical_stats": dict(canonical_mapping.canonical_stats or {}),
        "alias_normalized_inputs": list(canonical_mapping.alias_normalized_inputs or []),
        "structured_extraction_stats": dict(structured_extraction.stats or {}),
    }
    if len(_PIPELINE_CACHE) >= _PIPELINE_CACHE_CAP:
        oldest_key = next(iter(_PIPELINE_CACHE))
        _PIPELINE_CACHE.pop(oldest_key, None)
    _PIPELINE_CACHE[cache_key] = copy.deepcopy(result)
    return result


def build_offer_canonical_representation(offer: Dict[str, Any]) -> Dict[str, Any]:
    return run_offer_parse_pipeline(offer)
