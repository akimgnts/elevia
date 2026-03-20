from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from compass.domain_uris import build_domain_uris_for_text
from compass.promotion.apply_promotion import apply_profile_esco_promotion

from .contracts import CanonicalMappingStageResult, EnrichmentStageResult

logger = logging.getLogger(__name__)


def inject_profile_uris(
    profile: dict | None,
    *,
    uris: List[str],
    target_field: str,
    source: str,
    trace_bucket: List[dict],
) -> List[str]:
    cleaned = [str(uri).strip() for uri in uris if isinstance(uri, str) and str(uri).strip()]
    if not profile:
        trace_bucket.append(
            {
                "source": source,
                "target_field": target_field,
                "input_count": len(cleaned),
                "added_count": 0,
                "added_uris": [],
            }
        )
        return []

    existing = set(profile.get(target_field) or [])
    added: List[str] = []
    for uri in cleaned:
        if uri in existing:
            continue
        existing.add(uri)
        profile.setdefault(target_field, []).append(uri)
        added.append(uri)

    trace_bucket.append(
        {
            "source": source,
            "target_field": target_field,
            "input_count": len(cleaned),
            "added_count": len(added),
            "added_uris": added[:50],
        }
    )
    return added


def record_noop_stage(
    trace_bucket: List[dict],
    *,
    source: str,
    target_field: str,
    input_count: int = 0,
    error: Optional[str] = None,
) -> None:
    record = {
        "source": source,
        "target_field": target_field,
        "input_count": input_count,
        "added_count": 0,
        "added_uris": [],
    }
    if error:
        record["error"] = error
    trace_bucket.append(record)


def run_enrichment_stage(
    *,
    cv_text: str,
    profile: Dict[str, Any],
    result: Dict[str, Any],
    cluster_key: str | None,
    esco_labels: List[str],
    pipeline_resolved_to_esco: List[dict],
    pipeline_rejected_tokens: List[dict],
    canonical_mapping: CanonicalMappingStageResult,
) -> EnrichmentStageResult:
    matching_trace_stages: List[dict] = []
    baseline_esco_count = result.get("skills_uri_count", 0)
    injected_esco_from_domain = 0

    if pipeline_resolved_to_esco:
        added_esco = inject_profile_uris(
            profile,
            uris=[r["esco_uri"] for r in pipeline_resolved_to_esco if isinstance(r, dict) and r.get("esco_uri")],
            target_field="skills_uri",
            source="domain_token_to_esco",
            trace_bucket=matching_trace_stages,
        )
        injected_esco_from_domain = len(added_esco)
        for r in pipeline_resolved_to_esco:
            label = r.get("esco_label")
            if label:
                skills_list = profile.setdefault("skills", [])
                if label not in skills_list:
                    skills_list.append(label)
    else:
        record_noop_stage(
            matching_trace_stages,
            source="domain_token_to_esco",
            target_field="skills_uri",
        )

    total_esco_count = baseline_esco_count + injected_esco_from_domain

    domain_uris: List[str] = []
    domain_tokens: List[str] = []
    domain_debug: dict = {}
    if cluster_key:
        try:
            domain_tokens, domain_uris, domain_debug = build_domain_uris_for_text(
                cv_text,
                esco_labels,
                cluster_key,
            )
        except Exception as exc:
            logger.warning("[parse-file] domain uri build failed: %s", type(exc).__name__)
    if domain_uris:
        inject_profile_uris(
            profile,
            uris=domain_uris,
            target_field="skills_uri",
            source="domain_library_uri",
            trace_bucket=matching_trace_stages,
        )
    else:
        record_noop_stage(
            matching_trace_stages,
            source="domain_library_uri",
            target_field="skills_uri",
        )
    if domain_uris:
        profile["domain_uris"] = domain_uris
        profile["domain_uri_count"] = len(domain_uris)
        profile["domain_tokens"] = domain_tokens

    promoted_inputs = canonical_mapping.canonical_enriched_labels or []
    if profile:
        promoted_before = set(profile.get("skills_uri_promoted") or [])
        apply_profile_esco_promotion(
            profile,
            base_skills_uri=profile.get("skills_uri") or [],
            tight_candidates=promoted_inputs,
            filtered_tokens=result.get("filtered_tokens") or [],
            cluster=cluster_key,
        )
        promoted_after = profile.get("skills_uri_promoted") or []
        matching_trace_stages.append(
            {
                "source": "profile_esco_promotion",
                "target_field": "skills_uri_promoted",
                "input_count": len(promoted_inputs),
                "added_count": len([uri for uri in promoted_after if uri not in promoted_before]),
                "added_uris": [uri for uri in promoted_after if uri not in promoted_before][:50],
            }
        )
    else:
        record_noop_stage(
            matching_trace_stages,
            source="profile_esco_promotion",
            target_field="skills_uri_promoted",
            input_count=len(promoted_inputs),
        )

    if profile:
        try:
            from compass.canonical.esco_bridge import build_canonical_esco_promoted

            bridge_uris = build_canonical_esco_promoted(
                canonical_mapping.resolved_ids,
                base_skills_uri=profile.get("skills_uri") or [],
                cluster=cluster_key,
            )
            if bridge_uris:
                inject_profile_uris(
                    profile,
                    uris=bridge_uris,
                    target_field="skills_uri_promoted",
                    source="canonical_esco_bridge",
                    trace_bucket=matching_trace_stages,
                )
            else:
                record_noop_stage(
                    matching_trace_stages,
                    source="canonical_esco_bridge",
                    target_field="skills_uri_promoted",
                )
        except Exception as exc:
            logger.warning("[parse-file] canonical esco bridge failed: %s", type(exc).__name__)
            record_noop_stage(
                matching_trace_stages,
                source="canonical_esco_bridge",
                target_field="skills_uri_promoted",
                error=type(exc).__name__,
            )
    else:
        record_noop_stage(
            matching_trace_stages,
            source="canonical_esco_bridge",
            target_field="skills_uri_promoted",
        )

    baseline_esco_labels = [
        str(item.get("label") or item.get("uri") or "")
        for item in result.get("validated_items", [])
        if isinstance(item, dict) and (item.get("label") or item.get("uri"))
    ]
    skill_provenance = {
        "baseline_esco": baseline_esco_labels,
        "library_token_to_esco": [
            r["token_normalized"] for r in pipeline_resolved_to_esco
            if r.get("provenance") == "library_token_to_esco"
        ],
        "llm_token_to_esco": [
            r["token_normalized"] for r in pipeline_resolved_to_esco
            if r.get("provenance") == "llm_token_to_esco"
        ],
    }

    return EnrichmentStageResult(
        profile=profile,
        baseline_esco_count=baseline_esco_count,
        injected_esco_from_domain=injected_esco_from_domain,
        total_esco_count=total_esco_count,
        resolved_to_esco=list(pipeline_resolved_to_esco),
        rejected_tokens_list=pipeline_rejected_tokens[:50] if pipeline_rejected_tokens else [],
        domain_uris=domain_uris,
        domain_tokens=domain_tokens,
        domain_debug=domain_debug,
        matching_trace_stages=matching_trace_stages,
        skill_provenance=skill_provenance,
    )
