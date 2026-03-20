from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Tuple

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from compass.pipeline import build_parse_file_response_payload
from compass.pipeline.contracts import ParseFilePipelineRequest
from semantic_retrieval.assist import run_semantic_rag_assist

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "apps" / "api" / "data" / "eval" / "synthetic_cv_dataset_v1_manifest.json"

store = get_canonical_store()
FALSE_POSITIVE_GUARD_LABELS = {
    "machine learning",
    "data science",
    "advanced analytics",
}


@contextmanager
def _temporary_env(var: str, value: str | None):
    previous = os.getenv(var)
    if value is None:
        os.environ.pop(var, None)
    else:
        os.environ[var] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = previous


def _normalize_label(value: str) -> str:
    return normalize_canonical_key(value or "")


def _resolve_expected_to_canonical(skill: str) -> tuple[str | None, str]:
    key = _normalize_label(skill)
    if not key:
        return None, key
    cid = store.alias_to_id.get(key)
    if cid:
        return cid, key
    for candidate_id, skill_entry in store.id_to_skill.items():
        label_key = _normalize_label(str(skill_entry.get("label") or ""))
        if label_key == key:
            return candidate_id, key
    return None, key


def _score_view(expected_core_skills: List[str], *, preserved: List[dict], summary: List[dict], canonical: List[dict]) -> Dict[str, object]:
    preserved_labels = {_normalize_label(entry.get("label") or "") for entry in preserved}
    summary_labels = {_normalize_label(entry.get("label") or "") for entry in summary}
    canonical_ids = {entry.get("canonical_id") for entry in canonical if entry.get("canonical_id")}
    canonical_labels = {_normalize_label(entry.get("label") or "") for entry in canonical if entry.get("label")}
    expected_label_keys = {_normalize_label(skill) for skill in expected_core_skills}
    false_positive_labels = sorted(
        label
        for label in canonical_labels
        if label in FALSE_POSITIVE_GUARD_LABELS and label not in expected_label_keys
    )

    expected_rows = []
    preserved_hits = 0
    summary_hits = 0
    canonical_hits = 0
    for skill in expected_core_skills:
        cid, key = _resolve_expected_to_canonical(skill)
        in_preserved = key in preserved_labels
        in_summary = key in summary_labels
        in_canonical = (cid in canonical_ids) if cid else (key in canonical_labels)
        if in_preserved:
            preserved_hits += 1
        if in_summary:
            summary_hits += 1
        if in_canonical:
            canonical_hits += 1
        expected_rows.append({
            "skill": skill,
            "canonical_id": cid,
            "preserved_hit": in_preserved,
            "summary_hit": in_summary,
            "canonical_hit": in_canonical,
        })

    count = len(expected_core_skills) or 1
    return {
        "expected_skill_results": expected_rows,
        "preserved_hit_count": preserved_hits,
        "summary_hit_count": summary_hits,
        "canonical_hit_count": canonical_hits,
        "preserved_hit_rate": round(preserved_hits / count, 3),
        "summary_hit_rate": round(summary_hits / count, 3),
        "canonical_hit_rate": round(canonical_hits / count, 3),
        "false_positive_labels": false_positive_labels,
        "false_positive_count": len(false_positive_labels),
    }


def _aggregate(results: List[dict], *, use_assisted: bool) -> Dict[str, object]:
    key_prefix = "assisted" if use_assisted else "baseline"
    return {
        "cv_count": len(results),
        "avg_preserved_hit_rate": round(mean(item[key_prefix]["preserved_hit_rate"] for item in results), 3),
        "avg_summary_hit_rate": round(mean(item[key_prefix]["summary_hit_rate"] for item in results), 3),
        "avg_canonical_hit_rate": round(mean(item[key_prefix]["canonical_hit_rate"] for item in results), 3),
        "avg_preserved_count": round(mean(len(item[f"{key_prefix}_preserved_labels"]) for item in results), 2),
        "avg_dropped_count": round(mean(item["dropped_count"] for item in results), 2),
        "false_positive_count": sum(item[key_prefix]["false_positive_count"] for item in results),
        "rag_proposed_count": sum(item["semantic_rag_assist"].get("accepted_count", 0) + item["semantic_rag_assist"].get("rejected_count", 0) for item in results),
        "rag_accepted_count": sum(item["semantic_rag_assist"].get("accepted_count", 0) for item in results),
        "rag_rejected_count": sum(item["semantic_rag_assist"].get("rejected_count", 0) for item in results),
        "rag_abstention_count": sum(item["semantic_rag_assist"].get("abstention_count", 0) for item in results),
    }


def _domain_deltas(results: List[dict]) -> List[dict]:
    domains = sorted({row["domain"] for row in results})
    out: List[dict] = []
    for domain in domains:
        rows = [row for row in results if row["domain"] == domain]
        out.append({
            "domain": domain,
            "baseline_avg_preserved_hit_rate": round(mean(row["baseline"]["preserved_hit_rate"] for row in rows), 3),
            "assisted_avg_preserved_hit_rate": round(mean(row["assisted"]["preserved_hit_rate"] for row in rows), 3),
            "baseline_avg_canonical_hit_rate": round(mean(row["baseline"]["canonical_hit_rate"] for row in rows), 3),
            "assisted_avg_canonical_hit_rate": round(mean(row["assisted"]["canonical_hit_rate"] for row in rows), 3),
        })
    return out


def _parse_payload(cv_path: Path, *, request_id: str) -> dict:
    cv_text = cv_path.read_text(encoding="utf-8")
    return build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id=request_id,
            raw_filename=cv_path.name,
            content_type="text/plain",
            file_bytes=cv_text.encode("utf-8"),
            enrich_llm=0,
        )
    )


def _run_offline_assist(*, cv_text: str, baseline_payload: dict) -> dict:
    profile_cluster = baseline_payload.get("profile_cluster") or {}
    mapping_inputs: list[str] = []
    for value in baseline_payload.get("tight_candidates") or []:
        if isinstance(value, str) and value.strip():
            mapping_inputs.append(value)
    for entry in baseline_payload.get("canonical_skills") or []:
        raw = entry.get("raw")
        if isinstance(raw, str) and raw.strip():
            mapping_inputs.append(raw)
    for entry in baseline_payload.get("preserved_explicit_skills") or []:
        label = entry.get("label")
        if isinstance(label, str) and label.strip():
            mapping_inputs.append(label)
    for entry in baseline_payload.get("profile_summary_skills") or []:
        label = entry.get("label")
        if isinstance(label, str) and label.strip():
            mapping_inputs.append(label)
    mapping_inputs = list(dict.fromkeys(mapping_inputs))
    return run_semantic_rag_assist(
        cv_text=cv_text,
        cluster_key=profile_cluster.get("dominant_cluster"),
        mapping_inputs=mapping_inputs,
        preserved_explicit_skills=baseline_payload.get("preserved_explicit_skills") or [],
        profile_summary_skills=baseline_payload.get("profile_summary_skills") or [],
        dropped_by_priority=baseline_payload.get("dropped_by_priority") or [],
        canonical_skills_list=baseline_payload.get("canonical_skills") or [],
    )


def _merge_assisted_canonical_skills(*, baseline_canonical: list[dict], accepted_suggestions: list[dict]) -> list[dict]:
    merged = [dict(item) for item in baseline_canonical]
    seen_ids = {item.get("canonical_id") for item in merged if item.get("canonical_id")}
    for suggestion in accepted_suggestions:
        target = suggestion.get("canonical_target") or {}
        canonical_id = target.get("canonical_id")
        if not canonical_id or canonical_id in seen_ids:
            continue
        seen_ids.add(canonical_id)
        merged.append(
            {
                "raw": suggestion.get("evidence_span") or suggestion.get("label") or "",
                "canonical_id": canonical_id,
                "label": target.get("label") or suggestion.get("label") or "",
                "strategy": target.get("strategy") or "semantic_rag_accept",
                "confidence": suggestion.get("confidence") or 0.0,
                "cluster_name": "",
                "genericity_score": 0.0,
            }
        )
    return merged


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    results: List[dict] = []
    for item in manifest:
        cv_path = Path(item["path"])
        cv_text = cv_path.read_text(encoding="utf-8")
        with _temporary_env("ELEVIA_ENABLE_SEMANTIC_RAG_ASSIST", "0"):
            baseline_payload = _parse_payload(cv_path, request_id="semantic-rag-baseline")

        baseline_view = _score_view(
            item["expected_core_skills"],
            preserved=baseline_payload.get("preserved_explicit_skills") or [],
            summary=baseline_payload.get("profile_summary_skills") or [],
            canonical=baseline_payload.get("canonical_skills") or [],
        )

        should_run_assist = any(
            baseline_view[key] < 1.0
            for key in ("preserved_hit_rate", "summary_hit_rate", "canonical_hit_rate")
        )
        if should_run_assist:
            with _temporary_env("ELEVIA_ENABLE_SEMANTIC_RAG_ASSIST", "1"), _temporary_env(
                "ELEVIA_SEMANTIC_RAG_MAX_SEGMENTS",
                "2",
            ):
                rag = _run_offline_assist(cv_text=cv_text, baseline_payload=baseline_payload)
            assisted_payload = dict(baseline_payload)
            assisted_payload["semantic_rag_assist"] = rag
        else:
            assisted_payload = dict(baseline_payload)
            assisted_payload["semantic_rag_assist"] = {
                "enabled": False,
                "candidate_segments": [],
                "accepted_count": 0,
                "rejected_count": 0,
                "abstention_count": 0,
                "accepted_suggestions": [],
                "rejected_suggestions": [],
                "abstentions": [{"reason": "baseline_saturated"}],
            }

        rag = assisted_payload.get("semantic_rag_assist") or {}
        accepted_suggestions = rag.get("accepted_suggestions") or []
        assisted_preserved = rag.get("assisted_preserved_skills") or baseline_payload.get("preserved_explicit_skills") or []
        assisted_summary = rag.get("assisted_profile_summary_skills") or baseline_payload.get("profile_summary_skills") or []
        assisted_canonical = _merge_assisted_canonical_skills(
            baseline_canonical=baseline_payload.get("canonical_skills") or [],
            accepted_suggestions=accepted_suggestions,
        )
        assisted_view = _score_view(
            item["expected_core_skills"],
            preserved=assisted_preserved,
            summary=assisted_summary,
            canonical=assisted_canonical,
        )

        results.append({
            "candidate_name": item["candidate_name"],
            "title": item["title"],
            "domain": item["domain"],
            "layout_type": item["layout_type"],
            "difficulty": item["difficulty"],
            "expected_core_skill_count": len(item["expected_core_skills"]),
            "baseline": baseline_view,
            "assisted": assisted_view,
            "baseline_preserved_labels": [entry.get("label") for entry in baseline_payload.get("preserved_explicit_skills") or []],
            "assisted_preserved_labels": [entry.get("label") for entry in assisted_preserved],
            "semantic_rag_assist": {
                "enabled": bool(rag.get("enabled")),
                "candidate_segments": rag.get("candidate_segments") or [],
                "accepted_count": int(rag.get("accepted_count", 0) or 0),
                "rejected_count": int(rag.get("rejected_count", 0) or 0),
                "abstention_count": int(rag.get("abstention_count", 0) or 0),
                "accepted_suggestions": rag.get("accepted_suggestions") or [],
                "rejected_suggestions": rag.get("rejected_suggestions") or [],
                "abstentions": rag.get("abstentions") or [],
            },
            "dropped_count": len(baseline_payload.get("dropped_by_priority") or []),
            "delta": {
                "preserved_hit_rate": round(assisted_view["preserved_hit_rate"] - baseline_view["preserved_hit_rate"], 3),
                "summary_hit_rate": round(assisted_view["summary_hit_rate"] - baseline_view["summary_hit_rate"], 3),
                "canonical_hit_rate": round(assisted_view["canonical_hit_rate"] - baseline_view["canonical_hit_rate"], 3),
            },
        })

    payload = {
        "baseline": _aggregate(results, use_assisted=False),
        "assisted": _aggregate(results, use_assisted=True),
        "per_domain_delta": _domain_deltas(results),
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
