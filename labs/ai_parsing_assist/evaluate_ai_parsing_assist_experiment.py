from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload

from evaluate_profile_intelligence import REAL_CV_CASES

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "apps" / "api" / "data" / "eval" / "synthetic_cv_dataset_v1_manifest.json"
OUTPUT_PATH = REPO_ROOT / "apps" / "api" / "data" / "eval" / "ai_parsing_assist_experiment_results.json"

store = get_canonical_store()
FALSE_POSITIVE_GUARD_LABELS = {
    "machine learning",
    "data science",
    "advanced analytics",
}
DOMAIN_EXPECTATION_MAP = {
    "Business / Sales": "sales",
    "Supply Chain / Procurement": "supply_chain",
    "Supply Chain / Operations": "supply_chain",
    "Marketing / Communication": "marketing",
    "Finance / Controlling": "finance",
    "Finance / Accounting": "finance",
    "HR / Generalist": "hr",
}


def normalize_label(value: str) -> str:
    return normalize_canonical_key(value or "")


def resolve_expected_to_canonical(skill: str) -> tuple[str | None, str]:
    key = normalize_label(skill)
    if not key:
        return None, key
    cid = store.alias_to_id.get(key)
    if cid:
        return cid, key
    for candidate_id, skill_entry in store.id_to_skill.items():
        label_key = normalize_label(str(skill_entry.get("label") or ""))
        if label_key == key:
            return candidate_id, key
    return None, key


def _build_request(path: Path, *, request_id: str) -> ParseFilePipelineRequest:
    content_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/plain"
    return ParseFilePipelineRequest(
        request_id=request_id,
        raw_filename=path.name,
        content_type=content_type,
        file_bytes=path.read_bytes(),
        enrich_llm=0,
    )


def _extract_variant_payload(payload: dict[str, Any], variant: str) -> dict[str, Any]:
    if variant == "baseline":
        return {
            "preserved": payload.get("preserved_explicit_skills") or [],
            "summary": payload.get("profile_summary_skills") or [],
            "canonical": payload.get("canonical_skills") or [],
            "top_signal_units": payload.get("top_signal_units") or [],
            "structured_units": payload.get("structured_signal_units") or [],
            "mapping_inputs_count": int(payload.get("mapping_inputs_count") or 0),
            "structured_stats": payload.get("structured_signal_stats") or {},
            "profile_intelligence": payload.get("profile_intelligence") or {},
        }
    assist = payload.get("ai_parsing_assist") or {}
    return {
        "preserved": assist.get("assisted_preserved_explicit_skills") or payload.get("preserved_explicit_skills") or [],
        "summary": assist.get("assisted_profile_summary_skills") or payload.get("profile_summary_skills") or [],
        "canonical": assist.get("assisted_canonical_skills") or payload.get("canonical_skills") or [],
        "top_signal_units": assist.get("assisted_top_signal_units") or payload.get("top_signal_units") or [],
        "structured_units": assist.get("assisted_structured_units") or payload.get("structured_signal_units") or [],
        "mapping_inputs_count": len(assist.get("assisted_mapping_inputs") or []) or int(payload.get("mapping_inputs_count") or 0),
        "structured_stats": assist.get("assisted_stats") or payload.get("structured_signal_stats") or {},
        "profile_intelligence": assist.get("assisted_profile_intelligence") or payload.get("profile_intelligence") or {},
    }


def _synthetic_case_result(item: dict[str, Any], payload: dict[str, Any], *, variant: str) -> dict[str, Any]:
    view = _extract_variant_payload(payload, variant)
    preserved = view["preserved"]
    summary = view["summary"]
    canonical = view["canonical"]
    top_signal_units = view["top_signal_units"]
    structured_units = view["structured_units"]
    structured_stats = view["structured_stats"]

    preserved_labels = {normalize_label(entry.get("label") or "") for entry in preserved}
    summary_labels = {normalize_label(entry.get("label") or "") for entry in summary}
    canonical_ids = {entry.get("canonical_id") for entry in canonical if entry.get("canonical_id")}
    canonical_labels = {normalize_label(entry.get("label") or "") for entry in canonical if entry.get("label")}
    expected_label_keys = {normalize_label(skill) for skill in item["expected_core_skills"]}
    false_positive_labels = sorted(
        label for label in canonical_labels if label in FALSE_POSITIVE_GUARD_LABELS and label not in expected_label_keys
    )

    preserved_hits = 0
    summary_hits = 0
    canonical_hits = 0
    for skill in item["expected_core_skills"]:
        cid, key = resolve_expected_to_canonical(skill)
        if key in preserved_labels:
            preserved_hits += 1
        if key in summary_labels:
            summary_hits += 1
        if (cid in canonical_ids) if cid else (key in canonical_labels):
            canonical_hits += 1

    expected_domain = DOMAIN_EXPECTATION_MAP.get(item["domain"])
    top_domains = [entry.get("domain") for entry in top_signal_units if entry.get("domain")]
    domain_detection_hit = bool(expected_domain and expected_domain in top_domains)
    top_signal_relevance = 0.0
    if top_signal_units:
        expected_tokens = {normalize_label(skill) for skill in item["expected_core_skills"]}
        relevant = 0
        for signal in top_signal_units:
            combined = " ".join(str(signal.get(field) or "") for field in ("raw_text", "object", "action_object_text"))
            normalized = normalize_label(combined)
            if any(token and token in normalized for token in expected_tokens):
                relevant += 1
        top_signal_relevance = round(relevant / len(top_signal_units), 3)

    return {
        "candidate_name": item["candidate_name"],
        "title": item["title"],
        "domain": item["domain"],
        "variant": variant,
        "preserved_hit_rate": round(preserved_hits / len(item["expected_core_skills"]), 3),
        "summary_hit_rate": round(summary_hits / len(item["expected_core_skills"]), 3),
        "canonical_hit_rate": round(canonical_hits / len(item["expected_core_skills"]), 3),
        "preserved_hit_count": preserved_hits,
        "summary_hit_count": summary_hits,
        "canonical_hit_count": canonical_hits,
        "preserved_explicit_skills": [entry.get("label") for entry in preserved],
        "profile_summary_skills": [entry.get("label") for entry in summary],
        "canonical_skills": [entry.get("label") for entry in canonical if entry.get("label")],
        "structured_unit_count": len(structured_units),
        "mapping_inputs_count": int(view["mapping_inputs_count"] or 0),
        "structured_units_promoted_count": int(structured_stats.get("structured_units_promoted_count") or 0),
        "structured_units_rejected_count": int(structured_stats.get("structured_units_rejected_count") or 0),
        "domain_detection_hit": domain_detection_hit,
        "top_signal_relevance": top_signal_relevance,
        "false_positive_count": len(false_positive_labels),
        "false_positive_labels": false_positive_labels,
        "top_signal_units": top_signal_units,
        "profile_intelligence": view["profile_intelligence"],
    }


def _aggregate_synthetic(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cv_count": len(results),
        "avg_preserved_hit_rate": round(mean(item["preserved_hit_rate"] for item in results), 3),
        "avg_summary_hit_rate": round(mean(item["summary_hit_rate"] for item in results), 3),
        "avg_canonical_hit_rate": round(mean(item["canonical_hit_rate"] for item in results), 3),
        "avg_structured_unit_count": round(mean(item["structured_unit_count"] for item in results), 2),
        "avg_mapping_inputs_count": round(mean(item["mapping_inputs_count"] for item in results), 2),
        "avg_structured_units_promoted_count": round(mean(item["structured_units_promoted_count"] for item in results), 2),
        "avg_structured_units_rejected_count": round(mean(item["structured_units_rejected_count"] for item in results), 2),
        "domain_detection_accuracy": round(mean(1.0 if item["domain_detection_hit"] else 0.0 for item in results), 3),
        "avg_top_signal_relevance": round(mean(float(item["top_signal_relevance"] or 0.0) for item in results), 3),
        "false_positive_count": sum(item["false_positive_count"] for item in results),
    }


def _real_case_result(case: Any, payload: dict[str, Any], *, variant: str) -> dict[str, Any]:
    view = _extract_variant_payload(payload, variant)
    intelligence = view["profile_intelligence"] or {}
    predicted = str(intelligence.get("dominant_role_block") or "")
    return {
        "label": case.label,
        "family": case.family,
        "variant": variant,
        "expected_primary_block": case.expected_primary_block,
        "accepted_primary_blocks": list(case.accepted_primary_blocks),
        "predicted_primary_block": predicted,
        "strict_primary_match": predicted == case.expected_primary_block,
        "accepted_primary_match": predicted in set(case.accepted_primary_blocks),
        "top_profile_signals": list(intelligence.get("top_profile_signals") or []),
        "profile_summary": intelligence.get("profile_summary"),
        "dominant_domains": list(intelligence.get("dominant_domains") or []),
        "top_signal_units": view["top_signal_units"],
    }


def _aggregate_real(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(results),
        "strict_primary_accuracy": round(mean(1.0 if item["strict_primary_match"] else 0.0 for item in results), 4),
        "accepted_primary_accuracy": round(mean(1.0 if item["accepted_primary_match"] else 0.0 for item in results), 4),
    }


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    synthetic_baseline: list[dict[str, Any]] = []
    synthetic_assisted: list[dict[str, Any]] = []
    real_baseline: list[dict[str, Any]] = []
    real_assisted: list[dict[str, Any]] = []
    ai_metrics = {
        "ai_triggered_segment_count": 0,
        "ai_accepted_count": 0,
        "ai_rejected_count": 0,
        "ai_abstention_count": 0,
        "ai_helped_case_count": 0,
        "ai_hurt_case_count": 0,
    }

    for item in manifest:
        path = REPO_ROOT / item["path"]
        payload = build_parse_file_response_payload(_build_request(path, request_id=f"ai-parse-synth:{path.name}"))
        baseline = _synthetic_case_result(item, payload, variant="baseline")
        assisted = _synthetic_case_result(item, payload, variant="assisted")
        synthetic_baseline.append(baseline)
        synthetic_assisted.append(assisted)

        if assisted["canonical_hit_rate"] > baseline["canonical_hit_rate"] or assisted["preserved_hit_rate"] > baseline["preserved_hit_rate"]:
            ai_metrics["ai_helped_case_count"] += 1
        if assisted["canonical_hit_rate"] < baseline["canonical_hit_rate"] or assisted["false_positive_count"] > baseline["false_positive_count"]:
            ai_metrics["ai_hurt_case_count"] += 1

        assist = payload.get("ai_parsing_assist") or {}
        ai_metrics["ai_triggered_segment_count"] += int(assist.get("triggered_segment_count") or 0)
        ai_metrics["ai_accepted_count"] += int(assist.get("accepted_count") or 0)
        ai_metrics["ai_rejected_count"] += int(assist.get("rejected_count") or 0)
        ai_metrics["ai_abstention_count"] += int(assist.get("abstention_count") or 0)

    for case in REAL_CV_CASES:
        path = Path(case.path)
        if not path.exists():
            continue
        payload = build_parse_file_response_payload(_build_request(path, request_id=f"ai-parse-real:{path.name}"))
        baseline = _real_case_result(case, payload, variant="baseline")
        assisted = _real_case_result(case, payload, variant="assisted")
        real_baseline.append(baseline)
        real_assisted.append(assisted)

        if (not baseline["strict_primary_match"]) and assisted["strict_primary_match"]:
            ai_metrics["ai_helped_case_count"] += 1
        if baseline["strict_primary_match"] and not assisted["strict_primary_match"]:
            ai_metrics["ai_hurt_case_count"] += 1

        assist = payload.get("ai_parsing_assist") or {}
        ai_metrics["ai_triggered_segment_count"] += int(assist.get("triggered_segment_count") or 0)
        ai_metrics["ai_accepted_count"] += int(assist.get("accepted_count") or 0)
        ai_metrics["ai_rejected_count"] += int(assist.get("rejected_count") or 0)
        ai_metrics["ai_abstention_count"] += int(assist.get("abstention_count") or 0)

    output = {
        "synthetic": {
            "baseline": {
                "aggregate": _aggregate_synthetic(synthetic_baseline),
                "results": synthetic_baseline,
            },
            "assisted": {
                "aggregate": _aggregate_synthetic(synthetic_assisted),
                "results": synthetic_assisted,
            },
        },
        "real": {
            "baseline": {
                "aggregate": _aggregate_real(real_baseline),
                "results": real_baseline,
            },
            "assisted": {
                "aggregate": _aggregate_real(real_assisted),
                "results": real_assisted,
            },
        },
        "ai_metrics": ai_metrics,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
