from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Sequence

from compass.canonical.canonical_mapper import map_to_canonical
from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key

from .corpus_builder import build_corpus_artifact
from .gating import apply_gating
from .llm_interpreter import interpret_phrase
from .retriever import LocalSemanticRetriever
from .schemas import GatedSuggestion

logger = logging.getLogger(__name__)

_ENABLE_ENV = "ELEVIA_ENABLE_SEMANTIC_RAG_ASSIST"
_MAX_SEGMENTS_ENV = "ELEVIA_SEMANTIC_RAG_MAX_SEGMENTS"
_TOPK_ENV = "ELEVIA_SEMANTIC_RAG_TOPK"

_SECTION_HINTS = {"profil", "profile", "summary", "parcours", "experience", "experiences", "missions", "projects", "projets"}
_OPERATIONAL_HINTS = {
    "coordination", "coordonner", "suivi", "gestion", "organisation", "organiser", "relation",
    "mise", "jour", "administration", "traitement", "verification", "passation", "expeditions",
    "livraison", "livraisons", "transport", "stocks", "stock", "fournisseurs", "fournisseur",
    "recrutement", "onboarding", "newsletter", "email", "reporting", "budget", "factures",
}
_SKIP_LINE_PATTERNS = (
    re.compile(r"^\d{4}[–-]\d{4}$"),
    re.compile(r"^[A-Z][A-Za-z .'-]{0,40}$"),
)


def semantic_rag_assist_enabled() -> bool:
    return os.getenv(_ENABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _max_segments() -> int:
    try:
        return max(1, min(6, int(os.getenv(_MAX_SEGMENTS_ENV, "4"))))
    except Exception:
        return 4


def _top_k() -> int:
    try:
        return max(3, min(12, int(os.getenv(_TOPK_ENV, "8"))))
    except Exception:
        return 8


def _is_header_or_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    lowered = normalize_canonical_key(stripped)
    if lowered in _SECTION_HINTS:
        return True
    return any(pattern.match(stripped) for pattern in _SKIP_LINE_PATTERNS)


def _collect_candidate_segments(
    *,
    cv_text: str,
    dropped_by_priority: Sequence[dict],
    canonical_skills_list: Sequence[dict],
) -> List[dict]:
    unresolved_fragments: List[str] = []
    for item in dropped_by_priority:
        raw = normalize_canonical_key(str(item.get("raw_text") or item.get("label") or ""))
        if raw and 2 <= len(raw.split()) <= 8:
            unresolved_fragments.append(raw)
    for item in canonical_skills_list:
        if item.get("canonical_id"):
            continue
        raw = normalize_canonical_key(str(item.get("raw") or ""))
        if raw and 2 <= len(raw.split()) <= 8:
            unresolved_fragments.append(raw)
    unresolved_set = set(unresolved_fragments)

    segments: List[dict] = []
    for index, raw_line in enumerate((cv_text or "").splitlines()):
        line = raw_line.strip()
        if _is_header_or_noise(line):
            continue
        normalized = normalize_canonical_key(line)
        tokens = normalized.split()
        if len(tokens) < 6 or len(tokens) > 40:
            continue
        hint_matches = sum(1 for token in tokens if token in _OPERATIONAL_HINTS)
        fragment_matches = sum(1 for fragment in unresolved_set if fragment and fragment in normalized)
        score = hint_matches + (fragment_matches * 2)
        if score <= 0:
            continue
        segments.append({
            "text": line,
            "normalized": normalized,
            "score": score,
            "line_index": index,
            "matched_fragments": sorted(fragment for fragment in unresolved_set if fragment in normalized),
        })

    segments.sort(key=lambda item: (-item["score"], item["line_index"], item["normalized"]))
    return segments[:_max_segments()]


def _candidate_type_from_target(canonical_target: dict | None) -> tuple[str, str]:
    if not canonical_target:
        return "domain", "P3"
    store = get_canonical_store()
    entry = store.id_to_skill.get(canonical_target.get("canonical_id") or "", {})
    skill_type = str(entry.get("skill_type") or "").lower()
    if skill_type in {"tool", "platform", "database", "language"}:
        return skill_type or "tool", "P1"
    if skill_type in {"core", "practice", "method"}:
        return skill_type or "practice", "P2"
    return skill_type or "domain", "P3"


def _suggestion_to_skill_item(suggestion: GatedSuggestion) -> dict:
    candidate_type, priority_level = _candidate_type_from_target(suggestion.canonical_target)
    return {
        "raw_text": suggestion.evidence_span or suggestion.source_phrase,
        "normalized_text": normalize_canonical_key(suggestion.label),
        "label": suggestion.label,
        "source_section": "semantic_rag_assist",
        "source_confidence": suggestion.confidence,
        "candidate_type": candidate_type,
        "priority_level": priority_level,
        "is_explicit": False,
        "canonical_target": suggestion.canonical_target,
        "keep_reason": "kept:semantic_rag_assist",
        "drop_reason": None,
        "dominates": [],
        "matching_use_policy": ["representation_primary"],
        "source_reference": suggestion.source_reference,
        "rationale": suggestion.rationale,
    }


def run_semantic_rag_assist(
    *,
    cv_text: str,
    cluster_key: str | None,
    mapping_inputs: Sequence[str],
    preserved_explicit_skills: Sequence[dict],
    profile_summary_skills: Sequence[dict],
    dropped_by_priority: Sequence[dict],
    canonical_skills_list: Sequence[dict],
) -> Dict[str, Any]:
    if not semantic_rag_assist_enabled():
        return {"enabled": False}

    corpus_path = build_corpus_artifact()
    retriever = LocalSemanticRetriever()
    segments = _collect_candidate_segments(
        cv_text=cv_text,
        dropped_by_priority=dropped_by_priority,
        canonical_skills_list=canonical_skills_list,
    )
    existing_labels = [item.get("label") for item in preserved_explicit_skills if isinstance(item, dict)]
    existing_labels.extend(item.get("label") for item in profile_summary_skills if isinstance(item, dict))
    existing_labels.extend(item.get("label") for item in canonical_skills_list if isinstance(item, dict) and item.get("label"))

    accepted: List[dict] = []
    rejected: List[dict] = []
    abstentions: List[dict] = []
    segment_results: List[dict] = []
    accepted_items: List[dict] = []
    seen_labels = {normalize_canonical_key(label) for label in existing_labels if isinstance(label, str)}

    for segment in segments:
        retrieved = retriever.search(segment["text"], top_k=_top_k())
        interpretation = interpret_phrase(source_phrase=segment["text"], retrieved_candidates=retrieved)
        gating_result = apply_gating(
            interpretation=interpretation,
            retrieved_candidates=retrieved,
            cv_text=cv_text,
            existing_labels=existing_labels,
        )
        segment_results.append(
            {
                "segment": segment,
                "retrieved": [item.to_dict() for item in retrieved],
                "interpretation": interpretation.to_dict(),
                "gating": gating_result.to_dict(),
            }
        )
        accepted.extend(item.to_dict() for item in gating_result.accepted_suggestions)
        rejected.extend(item.to_dict() for item in gating_result.rejected_suggestions)
        abstentions.extend(gating_result.abstentions)
        for suggestion in gating_result.accepted_suggestions:
            label_key = normalize_canonical_key(suggestion.label)
            if not label_key or label_key in seen_labels:
                continue
            seen_labels.add(label_key)
            accepted_items.append(_suggestion_to_skill_item(suggestion))

    assisted_mapping_inputs = list(mapping_inputs)
    for item in accepted_items:
        assisted_mapping_inputs.append(item["label"])
    assisted_mapping_inputs = list(dict.fromkeys(assisted_mapping_inputs))

    assisted_preserved = list(preserved_explicit_skills) + accepted_items
    assisted_summary = list(profile_summary_skills)
    for item in accepted_items:
        if not any(normalize_canonical_key(existing.get("label") or "") == normalize_canonical_key(item["label"]) for existing in assisted_summary):
            assisted_summary.append(item)

    assisted_map = map_to_canonical(assisted_mapping_inputs, cluster=cluster_key)
    assisted_canonical_skills = [
        {
            "raw": mapping.raw,
            "canonical_id": mapping.canonical_id,
            "label": mapping.label,
            "strategy": mapping.strategy,
            "confidence": mapping.confidence,
            "cluster_name": mapping.cluster_name,
            "genericity_score": mapping.genericity_score,
        }
        for mapping in assisted_map.mappings
    ]
    assisted_canonical_stats = {
        "matched_count": assisted_map.matched_count,
        "unresolved_count": assisted_map.unresolved_count,
        "synonym_count": assisted_map.synonym_count,
        "tool_count": assisted_map.tool_count,
    }

    logger.info(json.dumps({
        "event": "SEMANTIC_RAG_ASSIST",
        "enabled": True,
        "segments": len(segments),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "abstentions": len(abstentions),
        "corpus_path": str(corpus_path),
    }))

    return {
        "enabled": True,
        "corpus_path": str(corpus_path),
        "candidate_segments": segments,
        "segment_results": segment_results,
        "accepted_suggestions": accepted,
        "rejected_suggestions": rejected,
        "abstentions": abstentions,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "abstention_count": len(abstentions),
        "assisted_mapping_inputs": assisted_mapping_inputs,
        "assisted_preserved_skills": assisted_preserved,
        "assisted_profile_summary_skills": assisted_summary,
        "assisted_canonical_skills": assisted_canonical_skills,
        "assisted_canonical_stats": assisted_canonical_stats,
    }
