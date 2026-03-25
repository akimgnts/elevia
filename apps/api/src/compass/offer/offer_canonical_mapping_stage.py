from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from compass.canonical.canonical_mapper import map_to_canonical
from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from compass.pipeline.contracts import StructuredExtractionStageResult
from compass.promotion.aliases import ALIAS_TO_CANONICAL_RAW
from esco.mapper import map_skill


_CLUSTER_TO_DOMAINS = {
    "DATA_ANALYTICS_AI": ("data",),
    "FINANCE_BUSINESS_OPERATIONS": ("finance", "business"),
    "MARKETING_SALES_GROWTH": ("marketing", "sales", "communication"),
    "SOFTWARE_IT": ("software", "it"),
    "GENERIC_TRANSVERSAL": ("general",),
}


@dataclass(frozen=True)
class OfferCanonicalMappingStageResult:
    mapping_inputs: List[str] = field(default_factory=list)
    alias_normalized_inputs: List[str] = field(default_factory=list)
    canonical_skills: List[dict] = field(default_factory=list)
    canonical_domains: List[str] = field(default_factory=list)
    unresolved: List[dict] = field(default_factory=list)
    near_matches: List[dict] = field(default_factory=list)
    canonical_stats: Dict[str, Any] = field(default_factory=dict)
    canonical_enriched_labels: List[str] = field(default_factory=list)


def _dedupe_preserve(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        label = str(value or "").strip()
        key = normalize_canonical_key(label)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def _alias_normalize(label: str) -> str:
    raw = str(label or "").strip()
    if not raw:
        return ""

    store = get_canonical_store()
    key = normalize_canonical_key(raw)
    if not key:
        return raw

    canonical_id = store.alias_to_id.get(key)
    if canonical_id:
        entry = store.id_to_skill.get(canonical_id, {})
        canonical_label = str(entry.get("label") or "").strip()
        if canonical_label:
            return canonical_label

    promoted = ALIAS_TO_CANONICAL_RAW.get(key)
    if promoted:
        promoted_key = normalize_canonical_key(promoted)
        canonical_id = store.alias_to_id.get(promoted_key)
        if canonical_id:
            entry = store.id_to_skill.get(canonical_id, {})
            canonical_label = str(entry.get("label") or "").strip()
            if canonical_label:
                return canonical_label
        return promoted

    esco_match = map_skill(raw, enable_fuzzy=False)
    if esco_match and esco_match.get("label"):
        esco_label = str(esco_match.get("label") or "").strip()
        canonical_id = store.alias_to_id.get(normalize_canonical_key(esco_label))
        if canonical_id:
            entry = store.id_to_skill.get(canonical_id, {})
            canonical_label = str(entry.get("label") or "").strip()
            if canonical_label:
                return canonical_label
        return esco_label

    return raw


def _collect_canonical_domains(
    *,
    canonical_skills: Sequence[dict],
    structured_extraction: StructuredExtractionStageResult,
) -> List[str]:
    scores: Dict[str, float] = {}

    def add(domain: str, weight: float) -> None:
        if not domain or weight <= 0:
            return
        scores[domain] = round(scores.get(domain, 0.0) + weight, 4)

    for entry in canonical_skills:
        cluster_name = str(entry.get("cluster_name") or "")
        genericity = float(entry.get("genericity_score") or 0.0)
        weight = max(0.2, 1.0 - min(genericity, 0.85))
        for domain in _CLUSTER_TO_DOMAINS.get(cluster_name, ()):
            add(domain, weight)

    for unit in list(structured_extraction.top_signal_units or [])[:5]:
        domain = str(unit.get("domain") or "").strip()
        if domain and domain != "unknown":
            add(domain, 1.2)

    for unit in list(structured_extraction.secondary_signal_units or [])[:5]:
        domain = str(unit.get("domain") or "").strip()
        if domain and domain != "unknown":
            add(domain, 0.5)

    return [
        domain
        for domain, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if score > 0
    ][:3]


def _dedupe_canonical_skills(values: Sequence[dict]) -> List[dict]:
    seen: set[str] = set()
    result: List[dict] = []
    for value in values:
        canonical_id = str(value.get("canonical_id") or "").strip()
        if not canonical_id or canonical_id in seen:
            continue
        seen.add(canonical_id)
        result.append(dict(value))
    return result


def run_offer_canonical_mapping_stage(
    *,
    offer_cluster: str | None,
    structured_extraction: StructuredExtractionStageResult,
    validated_labels: Sequence[str] | None = None,
) -> OfferCanonicalMappingStageResult:
    raw_mapping_inputs = list(structured_extraction.mapping_inputs or [])
    alias_normalized_inputs = _dedupe_preserve(
        [_alias_normalize(label) for label in [*raw_mapping_inputs, *(validated_labels or [])]]
    )

    mapping_seed = _dedupe_preserve([*alias_normalized_inputs, *raw_mapping_inputs])
    mapping_result = map_to_canonical(mapping_seed, cluster=offer_cluster)

    canonical_skills: List[dict] = []
    unresolved: List[dict] = []
    near_matches: List[dict] = []
    for item in mapping_result.mappings:
        entry = {
            "raw": item.raw,
            "canonical_id": item.canonical_id,
            "label": item.label,
            "strategy": item.strategy,
            "confidence": item.confidence,
            "cluster_name": item.cluster_name,
            "genericity_score": item.genericity_score,
        }
        if item.canonical_id:
            canonical_skills.append(entry)
            continue

        unresolved.append(entry)
        fuzzy = map_skill(item.raw, enable_fuzzy=True, fuzzy_threshold=0.96)
        if fuzzy and fuzzy.get("method") == "fuzzy_strict":
            near_matches.append(
                {
                    "raw": item.raw,
                    "label": str(fuzzy.get("label") or ""),
                    "esco_id": str(fuzzy.get("esco_id") or ""),
                    "confidence": float(fuzzy.get("confidence") or 0.0),
                    "method": str(fuzzy.get("method") or ""),
                }
            )

    canonical_skills = _dedupe_canonical_skills(canonical_skills)
    canonical_labels = _dedupe_preserve([str(item.get("label") or "") for item in canonical_skills])
    mapping_inputs = _dedupe_preserve([*canonical_labels, *alias_normalized_inputs])
    canonical_domains = _collect_canonical_domains(
        canonical_skills=canonical_skills,
        structured_extraction=structured_extraction,
    )

    return OfferCanonicalMappingStageResult(
        mapping_inputs=mapping_inputs,
        alias_normalized_inputs=alias_normalized_inputs,
        canonical_skills=canonical_skills,
        canonical_domains=canonical_domains,
        unresolved=unresolved,
        near_matches=near_matches,
        canonical_stats={
            "matched_count": int(mapping_result.matched_count),
            "unresolved_count": int(mapping_result.unresolved_count),
            "synonym_count": int(mapping_result.synonym_count),
            "tool_count": int(mapping_result.tool_count),
            "near_match_count": len(near_matches),
        },
        canonical_enriched_labels=_dedupe_preserve([*canonical_labels, *mapping_inputs]),
    )
