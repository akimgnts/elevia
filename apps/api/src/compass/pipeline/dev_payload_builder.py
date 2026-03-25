from __future__ import annotations

from typing import Any, Dict, List

from compass.pipeline.skill_candidate_stage import classify_unresolved

from .contracts import ParseFilePipelineArtifacts


def dev_tools_enabled() -> bool:
    import os

    elevia_dev_tools = os.getenv("ELEVIA_DEV_TOOLS", "").strip().lower()
    elevia_dev = os.getenv("ELEVIA_DEV", "").strip().lower()
    return elevia_dev_tools in {"1", "true", "yes", "on"} or elevia_dev in {"1", "true", "yes", "on"}


def build_analyze_dev_payload(artifacts: ParseFilePipelineArtifacts) -> dict:
    result = artifacts.result
    profile = artifacts.enrichment.profile
    skill_candidates = artifacts.skill_candidates
    structured_extraction = artifacts.structured_extraction
    enriched_signals = artifacts.enriched_signals
    concept_signals = artifacts.concept_signals
    canonical_mapping = artifacts.canonical_mapping
    enrichment = artifacts.enrichment

    promoted_uris = list(profile.get("skills_uri_promoted") or []) if profile else []
    mapping_inputs = canonical_mapping.mapping_inputs or []
    if skill_candidates.cleaned_chunks:
        mapping_count_base = len(skill_candidates.cleaned_chunks)
    elif skill_candidates.split_chunks:
        mapping_count_base = len(skill_candidates.split_chunks)
    else:
        mapping_count_base = len(skill_candidates.tight_candidates)

    canonical_success_rate = round(
        (canonical_mapping.canonical_stats["matched_count"] / mapping_count_base) if mapping_count_base else 0.0,
        4,
    )
    compass_skill_candidates = int(enrichment.domain_debug.get("candidates_count", 0) or 0)
    compass_skill_rejected = int(enrichment.domain_debug.get("rejected_count", 0) or 0)
    signal_loss_audit: List[dict] = []
    if canonical_mapping.canonical_skills_list:
        seen_norm: set = set()
        from compass.canonical.canonical_store import normalize_canonical_key

        for item in canonical_mapping.canonical_skills_list:
            raw = item.get("raw") if isinstance(item, dict) else None
            if not raw or not isinstance(raw, str):
                continue
            norm = normalize_canonical_key(raw)
            is_dup = norm in seen_norm if norm else False
            if norm:
                seen_norm.add(norm)
            if item.get("canonical_id"):
                continue
            reason = classify_unresolved(raw, is_dup)
            signal_loss_audit.append({
                "token": raw,
                "stage": "tight_candidates",
                "reason_not_canonical": reason,
            })
            if len(signal_loss_audit) >= 50:
                break

    analyze_dev = {
        "raw_extraction": {
            "raw_extracted_skills": result.get("skills_raw", []),
            "raw_tokens": result.get("raw_tokens", []),
            "raw_detected": result.get("raw_detected", 0),
            "validated_labels": result.get("validated_labels", []),
        },
        "tight_candidates": {
            "items": skill_candidates.tight_candidates,
            "count": len(skill_candidates.tight_candidates),
            "top_candidates": skill_candidates.tight_candidates[:30],
            "top_filtered": (skill_candidates.tight_metrics.get("top_dropped") or [])[:30],
            "split_examples": (skill_candidates.tight_metrics.get("split_examples") or [])[:30],
            "cv_structure_rejected_count": skill_candidates.tight_metrics.get("cv_structure_rejected_count", 0),
            "cv_structure_rejected_examples": (skill_candidates.tight_metrics.get("cv_structure_rejected_examples") or [])[:10],
            "guardrail_scope_mode": skill_candidates.tight_metrics.get("guardrail_scope_mode", "unknown"),
            "final_guardrail_rejected_count": skill_candidates.tight_metrics.get("final_guardrail_rejected_count", 0),
            "final_guardrail_examples": (skill_candidates.tight_metrics.get("final_guardrail_examples") or [])[:10],
        },
        "tight_split_trace": [],
        "tight_selection_trace": (skill_candidates.tight_metrics.get("selection_trace") or [])[:30],
        "top_candidates_source": "final_tight_candidates_post_filter",
        "mapping_inputs_source": "",
        "mapping_inputs_preview": [],
        "phrase_reducer": {
            "added_candidates": skill_candidates.reduced_candidates[:50],
            "added_count": len(skill_candidates.reduced_candidates),
            "trace": skill_candidates.reducer_traces[:30],
        },
        "token_cleaner": {
            "added_candidates": skill_candidates.cleaned_candidates[:50],
            "added_count": len(skill_candidates.cleaned_candidates),
        },
        "structured_extraction": {
            "structured_units": structured_extraction.structured_units[:50],
            "top_signal_units": structured_extraction.top_signal_units[:10],
            "secondary_signal_units": structured_extraction.secondary_signal_units[:20],
            "generic_filter_removed": structured_extraction.generic_filter_removed[:30],
            "stats": structured_extraction.stats,
        },
        "enriched_signals": enriched_signals.enriched_signals[:80],
        "concept_signals": concept_signals.concept_signals[:80],
        "signal_loss_audit": signal_loss_audit,
        "split_chunks": skill_candidates.split_chunks,
        "split_chunks_count": len(skill_candidates.split_chunks),
        "cleaned_chunks": skill_candidates.cleaned_chunks,
        "cleaned_chunks_count": len(skill_candidates.cleaned_chunks),
        "lemmatized_chunks_count": skill_candidates.lemmatized_chunks_count,
        "pos_rejected_count": skill_candidates.pos_rejected_count,
        "stage_flags": {
            "phrase_splitting": skill_candidates.enable_phrase_split,
            "chunk_normalizer": skill_candidates.enable_chunk_normalizer,
            "light_lemmatization": skill_candidates.enable_lemmatization,
            "pos_filter": skill_candidates.enable_pos_filter,
        },
        "noise_removed": skill_candidates.noise_removed[:200],
        "canonical_mapping": {
            "mappings": canonical_mapping.canonical_skills_list,
            "matched_count": canonical_mapping.canonical_stats["matched_count"],
            "unresolved_count": canonical_mapping.canonical_stats["unresolved_count"],
            "synonym_count": canonical_mapping.canonical_stats["synonym_count"],
            "tool_count": canonical_mapping.canonical_stats["tool_count"],
        },
        "skill_priority": {
            "preserved_explicit_skills": canonical_mapping.preserved_explicit_skills,
            "profile_summary_skills": canonical_mapping.profile_summary_skills,
            "dropped_by_priority": canonical_mapping.dropped_by_priority[:50],
            "priority_trace": canonical_mapping.priority_trace[:100],
            "priority_stats": canonical_mapping.priority_stats,
        },
        "canonical_dedupe_debug": canonical_mapping.canonical_dedupe_debug,
        "hierarchy_expansion": {
            "input_ids": canonical_mapping.resolved_ids,
            "added_parents": canonical_mapping.canonical_hierarchy_added,
            "expansion_map": canonical_mapping.expansion_map,
            "expanded_ids": canonical_mapping.expanded_ids or canonical_mapping.resolved_ids,
        },
        "esco_promotion": {
            "canonical_labels": canonical_mapping.canonical_enriched_labels,
            "skills_uri_promoted": promoted_uris,
            "promoted_uri_count": len(promoted_uris),
        },
        "proximity": {
            "links": canonical_mapping.skill_proximity_links,
            "summary": canonical_mapping.skill_proximity_summary,
            "count": canonical_mapping.skill_proximity_count,
        },
        "explainability": {
            "status": "not_computed_here",
            "reason": "not_available_at_parse_stage",
        },
        "profile_intelligence": artifacts.profile_intelligence.data,
        "profile_intelligence_ai_assist": artifacts.profile_intelligence_ai_assist.data,
        "counters": {
            "raw_count": int(result.get("raw_detected", 0) or 0),
            "tight_count": len(skill_candidates.tight_candidates),
            "split_chunks_count": len(skill_candidates.split_chunks),
            "cleaned_chunks_count": len(skill_candidates.cleaned_chunks),
            "lemmatized_chunks_count": skill_candidates.lemmatized_chunks_count,
            "pos_rejected_count": skill_candidates.pos_rejected_count,
            "phrase_length_gt3_tokens": int(skill_candidates.phrase_length_gt3_tokens),
            "canonical_count": int(canonical_mapping.canonical_stats["matched_count"]),
            "unresolved_count": int(canonical_mapping.canonical_stats["unresolved_count"]),
            "expanded_count": len(canonical_mapping.canonical_hierarchy_added),
            "promoted_uri_count": len(promoted_uris),
            "near_match_count": int(canonical_mapping.skill_proximity_count),
            "noise_removed_count": len(skill_candidates.noise_removed),
            "canonical_success_rate": canonical_success_rate,
            "compass_skill_candidates": compass_skill_candidates,
            "compass_skill_rejected": compass_skill_rejected,
            "cv_structure_rejected_count": int(skill_candidates.tight_metrics.get("cv_structure_rejected_count", 0) or 0),
            "tight_single_token_count": int(skill_candidates.tight_metrics.get("single_token_count", 0) or 0),
            "tight_generic_rejected_count": int(skill_candidates.tight_metrics.get("generic_rejected_count", 0) or 0),
            "tight_numeric_rejected_count": int(skill_candidates.tight_metrics.get("numeric_rejected_count", 0) or 0),
            "tight_repeated_fragment_count": int(skill_candidates.tight_metrics.get("repeated_fragment_count", 0) or 0),
            "tight_filtered_out_count": int(skill_candidates.tight_metrics.get("filtered_out_count", 0) or 0),
            "tight_split_generated_count": int(skill_candidates.tight_metrics.get("split_generated_count", 0) or 0),
            "broken_token_repair_count": int(skill_candidates.tight_metrics.get("broken_token_repair_count", 0) or 0),
            "generated_composite_rejected_count": int(skill_candidates.tight_metrics.get("generated_composite_rejected_count", 0) or 0),
            "duplicate_tokens": int(skill_candidates.duplicate_tokens),
            "broken_tokens": int(skill_candidates.broken_tokens),
            "multi_skill_phrases": int(skill_candidates.multi_skill_phrases),
            "reduced_candidates_count": int(len(skill_candidates.reduced_candidates)),
            "cleaned_candidates_count": int(len(skill_candidates.cleaned_candidates)),
            "structured_unit_count": int(structured_extraction.stats.get("structured_unit_count", 0) or 0),
            "top_signal_unit_count": int(structured_extraction.stats.get("top_signal_unit_count", 0) or 0),
            "generic_filter_removed_count": int(structured_extraction.stats.get("generic_removed_count", 0) or 0),
            "structured_units_promoted_count": int(structured_extraction.stats.get("structured_units_promoted_count", 0) or 0),
            "structured_units_rejected_count": int(structured_extraction.stats.get("structured_units_rejected_count", 0) or 0),
            "mapping_inputs_count": int(structured_extraction.stats.get("mapping_inputs_count", 0) or 0),
            "enriched_signal_count": int(len(enriched_signals.enriched_signals)),
            "concept_signal_count": int(len(concept_signals.concept_signals)),
            "priority_preserved_count": int(canonical_mapping.priority_stats.get("preserved_count", 0) or 0),
            "priority_summary_count": int(canonical_mapping.priority_stats.get("summary_count", 0) or 0),
            "priority_dropped_count": int(canonical_mapping.priority_stats.get("dropped_count", 0) or 0),
            "priority_added_mapping_inputs_count": int(canonical_mapping.priority_stats.get("added_mapping_inputs_count", 0) or 0),
            "profile_intelligence_role_hypothesis_count": int(len((artifacts.profile_intelligence.data or {}).get("role_hypotheses") or [])),
            "profile_intelligence_ai_assist_triggered": int(bool((artifacts.profile_intelligence_ai_assist.data or {}).get("triggered"))),
            "profile_intelligence_ai_assist_accepted": int(bool((artifacts.profile_intelligence_ai_assist.data or {}).get("accepted"))),
        },
    }
    analyze_dev["broken_token_repair_examples"] = (skill_candidates.tight_metrics.get("broken_token_repair_examples") or [])[:20]

    if structured_extraction.enabled and structured_extraction.mapping_inputs:
        analyze_dev["mapping_inputs_source"] = "structured_extraction_stage"
        analyze_dev["mapping_inputs_preview"] = structured_extraction.mapping_inputs[:20]
    elif skill_candidates.cleaned_chunks:
        base_source = "cleaned_chunks_post_normalizer"
        base_preview = skill_candidates.cleaned_chunks[:20]
    elif skill_candidates.split_chunks:
        base_source = "split_chunks_post_noise_filter"
        base_preview = skill_candidates.split_chunks[:20]
    else:
        base_source = "final_tight_candidates_post_filter"
        base_preview = skill_candidates.tight_candidates[:20]

    if structured_extraction.enabled and structured_extraction.mapping_inputs:
        pass
    elif skill_candidates.reduced_candidates:
        analyze_dev["mapping_inputs_source"] = f"{base_source}+phrase_reducer"
        analyze_dev["mapping_inputs_preview"] = mapping_inputs[:20]
    else:
        analyze_dev["mapping_inputs_source"] = base_source
        analyze_dev["mapping_inputs_preview"] = base_preview

    trace_raw = skill_candidates.tight_metrics.get("split_trace") or []
    mapping_set = {s.lower() for s in mapping_inputs if isinstance(s, str)}
    final_set = {s.lower() for s in skill_candidates.tight_candidates if isinstance(s, str)}
    trace_final = []
    for item in trace_raw:
        generated = item.get("generated") or []
        survived = item.get("survived_final_tight") or []
        survived_after_filter = [c for c in survived if c.lower() in final_set]
        present_in_mapping = [c for c in survived_after_filter if c.lower() in mapping_set]
        trace_final.append({
            "source": item.get("source"),
            "generated": generated,
            "inserted": item.get("inserted") or [],
            "survived_after_filter": survived_after_filter,
            "present_in_final_tight": survived_after_filter,
            "present_in_mapping_inputs": present_in_mapping,
            "dropped": item.get("dropped") or [],
        })
    analyze_dev["tight_split_trace"] = trace_final[:30]
    return analyze_dev
