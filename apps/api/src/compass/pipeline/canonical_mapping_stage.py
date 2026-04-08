from __future__ import annotations

import json
import logging
from typing import List, Tuple

from compass.canonical.canonical_store import normalize_canonical_key

from .contracts import CanonicalMappingStageResult, SkillCandidateStageResult, StructuredExtractionStageResult

logger = logging.getLogger(__name__)


def dedupe_by_canonical_key(tokens: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for token in tokens:
        if not isinstance(token, str):
            continue
        key = normalize_canonical_key(token)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out


def canonical_source_from_strategy(strategy: str) -> str:
    if strategy == "synonym_match":
        return "alias"
    if strategy == "tool_match":
        return "tool_mapping"
    if strategy == "hierarchy_parent":
        return "hierarchy_parent"
    if strategy == "unresolved":
        return "unresolved"
    return "canonical_mapping"


def dedupe_canonical_skills_for_display(
    canonical_skills: List[dict],
    canonical_hierarchy_added: List[str],
) -> Tuple[List[dict], dict]:
    seen: set = set()
    deduped: List[dict] = []
    sources: dict = {}
    total_before = 0

    for entry in canonical_skills:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("canonical_id") or ""
        if not cid:
            deduped.append(entry)
            continue
        total_before += 1
        if cid not in sources:
            sources[cid] = set()
        sources[cid].add(canonical_source_from_strategy(entry.get("strategy", "")))
        if cid in seen:
            continue
        seen.add(cid)
        deduped.append(entry)

    hierarchy_sources = [
        {"canonical_id": parent_id, "source": "hierarchy_parent"}
        for parent_id in (canonical_hierarchy_added or [])
    ]
    debug = {
        "total_canonical_before_dedupe": total_before,
        "unique_canonical_after_dedupe": len(seen),
        "duplicates_removed": max(total_before - len(seen), 0),
        "sources": [
            {"canonical_id": cid, "sources": sorted(list(srcs))}
            for cid, srcs in sources.items()
        ],
        "hierarchy_parents": hierarchy_sources,
    }
    return deduped, debug


def select_mapping_inputs(skill_candidates: SkillCandidateStageResult) -> List[str]:
    if skill_candidates.cleaned_chunks:
        mapping_inputs = list(skill_candidates.cleaned_chunks)
    elif skill_candidates.split_chunks:
        mapping_inputs = list(skill_candidates.split_chunks)
    else:
        mapping_inputs = list(skill_candidates.tight_candidates)

    if skill_candidates.reduced_candidates:
        mapping_inputs = dedupe_by_canonical_key(mapping_inputs + skill_candidates.reduced_candidates)
    if skill_candidates.cleaned_candidates:
        mapping_inputs = dedupe_by_canonical_key(mapping_inputs + skill_candidates.cleaned_candidates)
    return mapping_inputs


def run_canonical_mapping_stage(
    *,
    request_id: str,
    cluster_key: str | None,
    skill_candidates: SkillCandidateStageResult,
    structured_extraction: StructuredExtractionStageResult,
    cv_text: str,
    validated_labels: List[str],
    base_mapping_inputs: List[str] | None = None,
) -> CanonicalMappingStageResult:
    canonical_skills_list: List[dict] = []
    canonical_hierarchy_added: List[str] = []
    canonical_enriched_labels: List[str] = []
    resolved_ids: List[str] = []
    canonical_stats = {
        "matched_count": 0,
        "unresolved_count": 0,
        "synonym_count": 0,
        "tool_count": 0,
    }
    expansion_map: dict = {}
    expanded_ids: List[str] = []
    skill_proximity_links: List[dict] = []
    skill_proximity_summary: dict = {}
    skill_proximity_count = 0
    preserved_explicit_skills: List[dict] = []
    profile_summary_skills: List[dict] = []
    dropped_by_priority: List[dict] = []
    priority_trace: List[dict] = []
    priority_stats: dict = {}

    raw_mapping_inputs = list(base_mapping_inputs or select_mapping_inputs(skill_candidates))
    base_mapping_inputs = list(structured_extraction.mapping_inputs or raw_mapping_inputs)
    mapping_inputs = list(base_mapping_inputs)
    try:
        from compass.extraction.skill_priority_layer import run_skill_priority_layer
        from compass.canonical.canonical_mapper import map_to_canonical
        from compass.canonical.hierarchy_expander import expand_hierarchy

        priority_result = run_skill_priority_layer(
            cv_text=cv_text,
            validated_labels=validated_labels,
            mapping_inputs=base_mapping_inputs,
        )
        mapping_inputs = list(priority_result.mapping_inputs or base_mapping_inputs)
        preserved_explicit_skills = list(priority_result.preserved_explicit_skills)
        profile_summary_skills = list(priority_result.profile_summary_skills)
        dropped_by_priority = list(priority_result.dropped_by_priority)
        priority_trace = list(priority_result.priority_trace)
        priority_stats = dict(priority_result.priority_stats or {})

        _cmap = map_to_canonical(mapping_inputs, cluster=cluster_key)
        canonical_skills_list = [
            {
                "raw": m.raw,
                "canonical_id": m.canonical_id,
                "label": m.label,
                "strategy": m.strategy,
                "confidence": m.confidence,
                "cluster_name": m.cluster_name,
                "genericity_score": m.genericity_score,
            }
            for m in _cmap.mappings
        ]
        canonical_stats = {
            "matched_count": _cmap.matched_count,
            "unresolved_count": _cmap.unresolved_count,
            "synonym_count": _cmap.synonym_count,
            "tool_count": _cmap.tool_count,
        }
        resolved_ids = list(dict.fromkeys(m.canonical_id for m in _cmap.mappings if m.canonical_id))
        _exp = expand_hierarchy(resolved_ids)
        canonical_hierarchy_added = _exp.added_parents
        expansion_map = _exp.expansion_map
        expanded_ids = _exp.expanded_ids
        resolved_labels = [m.label for m in _cmap.mappings if m.label]
        canonical_enriched_labels = list(dict.fromkeys(resolved_labels + mapping_inputs))
        if _cmap.matched_count or canonical_hierarchy_added:
            logger.info(json.dumps({
                "event": "CANONICAL_MAPPING",
                "cluster": cluster_key,
                "raw_in": len(skill_candidates.tight_candidates),
                "priority_raw_in": len(raw_mapping_inputs),
                "structured_in": len(base_mapping_inputs),
                "priority_final_in": len(mapping_inputs),
                "priority_preserved": len(preserved_explicit_skills),
                "priority_dropped": len(dropped_by_priority),
                "matched": _cmap.matched_count,
                "synonym": _cmap.synonym_count,
                "tool": _cmap.tool_count,
                "unresolved": _cmap.unresolved_count,
                "hierarchy_added": len(canonical_hierarchy_added),
                "request_id": request_id,
            }))
    except Exception as exc:
        logger.warning("[parse-file] canonical mapping failed: %s", type(exc).__name__)
        canonical_enriched_labels = list(skill_candidates.tight_candidates)

    canonical_dedupe_debug: dict = {}
    if canonical_skills_list:
        canonical_skills_list, canonical_dedupe_debug = dedupe_canonical_skills_for_display(
            canonical_skills_list,
            canonical_hierarchy_added,
        )

    try:
        from compass.canonical.skill_proximity import compute_skill_proximity

        _prox = compute_skill_proximity(resolved_ids, resolved_ids)
        skill_proximity_links = _prox.get("links", [])
        skill_proximity_summary = _prox.get("summary", {})
        skill_proximity_count = int(skill_proximity_summary.get("match_count", len(skill_proximity_links)))
    except Exception as exc:
        logger.warning("[parse-file] skill proximity failed: %s", type(exc).__name__)

    return CanonicalMappingStageResult(
        mapping_inputs=mapping_inputs,
        canonical_skills_list=canonical_skills_list,
        canonical_hierarchy_added=canonical_hierarchy_added,
        canonical_enriched_labels=canonical_enriched_labels,
        canonical_stats=canonical_stats,
        resolved_ids=resolved_ids,
        expansion_map=expansion_map,
        expanded_ids=expanded_ids,
        canonical_dedupe_debug=canonical_dedupe_debug,
        skill_proximity_links=skill_proximity_links,
        skill_proximity_summary=skill_proximity_summary,
        skill_proximity_count=skill_proximity_count,
        preserved_explicit_skills=preserved_explicit_skills,
        profile_summary_skills=profile_summary_skills,
        dropped_by_priority=dropped_by_priority,
        priority_trace=priority_trace,
        priority_stats=priority_stats,
    )
