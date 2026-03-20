from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload

REPO_ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_MANIFEST = REPO_ROOT / "apps" / "api" / "data" / "eval" / "synthetic_cv_dataset_v1_manifest.json"
OUTPUT_JSON = REPO_ROOT / "apps" / "api" / "data" / "eval" / "profile_intelligence_eval_results.json"
OUTPUT_CSV = REPO_ROOT / "apps" / "api" / "data" / "eval" / "profile_intelligence_eval_results.csv"

SYNTHETIC_EXPECTED_BLOCKS = {
    "cv_01_lina_morel.txt": "sales_business_dev",
    "cv_02_hugo_renaud.txt": "sales_business_dev",
    "cv_03_sarah_el_mansouri.txt": "supply_chain_ops",
    "cv_04_benoit_caron.txt": "supply_chain_ops",
    "cv_05_camille_vasseur.txt": "marketing_communication",
    "cv_06_yasmine_haddad.txt": "marketing_communication",
    "cv_07_pierre_lemaire.txt": "finance_ops",
    "cv_08_amel_dufour.txt": "finance_ops",
    "cv_09_ines_barbier.txt": "hr_ops",
}


@dataclass(frozen=True)
class RealCvExpectation:
    label: str
    path: str
    expected_primary_block: str
    accepted_primary_blocks: tuple[str, ...]
    family: str
    notes: str = ""


REAL_CV_CASES: tuple[RealCvExpectation, ...] = (
    RealCvExpectation(
        label="Akim Resume Data",
        path="/Users/akimguentas/Downloads/cvtest/Akim_Guentas_Resume.pdf",
        expected_primary_block="data_analytics",
        accepted_primary_blocks=("data_analytics", "business_analysis"),
        family="data_bi",
    ),
    RealCvExpectation(
        label="Akim Audit Data Analyst",
        path="/Users/akimguentas/Downloads/cvtest/Akim Guentas – Audit & Data Analyst.pdf",
        expected_primary_block="finance_ops",
        accepted_primary_blocks=("finance_ops", "data_analytics", "business_analysis"),
        family="finance_controlling",
        notes="Hybrid audit/data CV; finance or data dominant can both be acceptable if the summary stays coherent.",
    ),
    RealCvExpectation(
        label="Akim Business Analyst",
        path="/Users/akimguentas/Downloads/Akim Guentas – Business Analyst.pdf",
        expected_primary_block="business_analysis",
        accepted_primary_blocks=("business_analysis", "data_analytics"),
        family="business_analysis",
    ),
    RealCvExpectation(
        label="Akim Marketing Analyst",
        path="/Users/akimguentas/Downloads/Akim_Guentas_CV_Marketing_Analyst_Decathlon.pdf",
        expected_primary_block="marketing_communication",
        accepted_primary_blocks=("marketing_communication", "business_analysis"),
        family="marketing_communication",
    ),
    RealCvExpectation(
        label="Supply Chain Performance Analyst",
        path="/Users/akimguentas/Downloads/APPLICATION/CV – Akim Guentas – Future Talent Supply Chain Performance Analyst.pdf",
        expected_primary_block="supply_chain_ops",
        accepted_primary_blocks=("supply_chain_ops", "business_analysis", "data_analytics"),
        family="supply_chain_ops",
    ),
    RealCvExpectation(
        label="CV Wecker",
        path="/Users/akimguentas/Downloads/cvtest/CV WECKER.pdf",
        expected_primary_block="software_it",
        accepted_primary_blocks=("software_it", "data_analytics"),
        family="software_it",
    ),
    RealCvExpectation(
        label="Ania Benabbas",
        path="/Users/akimguentas/Downloads/cvtest/CV_2026-02-17_Ania_Benabbas (1).pdf",
        expected_primary_block="legal_compliance",
        accepted_primary_blocks=("legal_compliance", "finance_ops"),
        family="legal_compliance",
    ),
)


def _read_manifest() -> list[dict[str, Any]]:
    return json.loads(SYNTHETIC_MANIFEST.read_text(encoding="utf-8"))


def _content_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    return "text/plain"


def _safe_parse(path: Path) -> dict[str, Any] | None:
    try:
        return build_parse_file_response_payload(
            ParseFilePipelineRequest(
                request_id=f"profile-intel:{path.name}",
                raw_filename=path.name,
                content_type=_content_type_for_path(path),
                file_bytes=path.read_bytes(),
                enrich_llm=0,
            )
        )
    except Exception as exc:
        return {"_error": type(exc).__name__, "_error_detail": str(exc), "path": str(path)}


def _summarize_case(
    *,
    label: str,
    source_type: str,
    path: Path,
    expected_primary_block: str,
    accepted_primary_blocks: Iterable[str],
    payload: dict[str, Any],
    family: str,
    notes: str = "",
) -> dict[str, Any]:
    if "_error" in payload:
        return {
            "label": label,
            "source_type": source_type,
            "path": str(path),
            "family": family,
            "expected_primary_block": expected_primary_block,
            "accepted_primary_blocks": list(accepted_primary_blocks),
            "error": payload["_error"],
            "error_detail": payload["_error_detail"],
            "notes": notes,
        }

    intelligence = payload.get("profile_intelligence") or {}
    ai_assist = payload.get("profile_intelligence_ai_assist") or {}
    predicted = str(intelligence.get("dominant_role_block") or "")
    top_signals = list(intelligence.get("top_profile_signals") or [])
    role_hypotheses = list(intelligence.get("role_hypotheses") or [])
    strict_match = predicted == expected_primary_block
    accepted_match = predicted in set(accepted_primary_blocks)
    ai_suggestion = ai_assist.get("suggestion") or {}
    ai_suggested_block = str(ai_suggestion.get("suggested_role_block") or "")
    ai_triggered = bool(ai_assist.get("triggered"))
    ai_accepted = bool(ai_assist.get("accepted"))
    ai_helped = bool(ai_accepted and ai_suggested_block == expected_primary_block and predicted != expected_primary_block)
    ai_hurt = bool(ai_accepted and strict_match and ai_suggested_block != expected_primary_block)

    return {
        "label": label,
        "source_type": source_type,
        "path": str(path),
        "family": family,
        "expected_primary_block": expected_primary_block,
        "accepted_primary_blocks": list(accepted_primary_blocks),
        "predicted_primary_block": predicted,
        "strict_primary_match": strict_match,
        "accepted_primary_match": accepted_match,
        "secondary_role_blocks": list(intelligence.get("secondary_role_blocks") or []),
        "dominant_domains": list(intelligence.get("dominant_domains") or []),
        "top_profile_signals": top_signals,
        "role_hypotheses": role_hypotheses,
        "profile_summary": intelligence.get("profile_summary"),
        "role_block_scores": intelligence.get("role_block_scores") or [],
        "profile_intelligence_ai_assist": ai_assist,
        "ai_triggered": ai_triggered,
        "ai_accepted": ai_accepted,
        "ai_suggested_role_block": ai_suggested_block or None,
        "ai_helped": ai_helped,
        "ai_hurt": ai_hurt,
        "notes": notes,
    }


def _build_synthetic_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for item in _read_manifest():
        path = REPO_ROOT / item["path"]
        expected_primary_block = SYNTHETIC_EXPECTED_BLOCKS[path.name]
        payload = _safe_parse(path)
        cases.append(
            _summarize_case(
                label=item["candidate_name"],
                source_type="synthetic",
                path=path,
                expected_primary_block=expected_primary_block,
                accepted_primary_blocks=(expected_primary_block,),
                payload=payload or {},
                family=item["domain"],
                notes=item["title"],
            )
        )
    return cases


def _build_real_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case in REAL_CV_CASES:
        path = Path(case.path)
        if not path.exists():
            cases.append(
                {
                    "label": case.label,
                    "source_type": "real",
                    "path": case.path,
                    "family": case.family,
                    "expected_primary_block": case.expected_primary_block,
                    "accepted_primary_blocks": list(case.accepted_primary_blocks),
                    "error": "missing_file",
                    "error_detail": "File not found",
                    "notes": case.notes,
                }
            )
            continue
        payload = _safe_parse(path)
        cases.append(
            _summarize_case(
                label=case.label,
                source_type="real",
                path=path,
                expected_primary_block=case.expected_primary_block,
                accepted_primary_blocks=case.accepted_primary_blocks,
                payload=payload or {},
                family=case.family,
                notes=case.notes,
            )
        )
    return cases


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    parsed_cases = [case for case in cases if not case.get("error")]
    strict_hits = sum(1 for case in parsed_cases if case.get("strict_primary_match"))
    accepted_hits = sum(1 for case in parsed_cases if case.get("accepted_primary_match"))
    family_breakdown: dict[str, dict[str, int]] = {}
    for case in parsed_cases:
        family = str(case.get("family") or "unknown")
        bucket = family_breakdown.setdefault(family, {"count": 0, "strict_hits": 0, "accepted_hits": 0})
        bucket["count"] += 1
        bucket["strict_hits"] += int(bool(case.get("strict_primary_match")))
        bucket["accepted_hits"] += int(bool(case.get("accepted_primary_match")))
    ai_triggered = sum(1 for case in parsed_cases if case.get("ai_triggered"))
    ai_accepted = sum(1 for case in parsed_cases if case.get("ai_accepted"))
    ai_helped = sum(1 for case in parsed_cases if case.get("ai_helped"))
    ai_hurt = sum(1 for case in parsed_cases if case.get("ai_hurt"))
    return {
        "count": len(cases),
        "parsed_count": len(parsed_cases),
        "error_count": len(cases) - len(parsed_cases),
        "strict_primary_accuracy": round(strict_hits / len(parsed_cases), 4) if parsed_cases else 0.0,
        "accepted_primary_accuracy": round(accepted_hits / len(parsed_cases), 4) if parsed_cases else 0.0,
        "ai_triggered_count": ai_triggered,
        "ai_accepted_count": ai_accepted,
        "ai_helped_count": ai_helped,
        "ai_hurt_count": ai_hurt,
        "family_breakdown": family_breakdown,
    }


def _write_csv(cases: list[dict[str, Any]]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_type",
                "label",
                "family",
                "expected_primary_block",
                "predicted_primary_block",
                "strict_primary_match",
                "accepted_primary_match",
                "secondary_role_blocks",
                "dominant_domains",
                "role_hypotheses",
                "top_profile_signals",
                "profile_summary",
                "ai_triggered",
                "ai_accepted",
                "ai_suggested_role_block",
                "ai_helped",
                "ai_hurt",
                "notes",
                "path",
                "error",
            ],
        )
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "source_type": case.get("source_type"),
                    "label": case.get("label"),
                    "family": case.get("family"),
                    "expected_primary_block": case.get("expected_primary_block"),
                    "predicted_primary_block": case.get("predicted_primary_block"),
                    "strict_primary_match": case.get("strict_primary_match"),
                    "accepted_primary_match": case.get("accepted_primary_match"),
                    "secondary_role_blocks": ", ".join(case.get("secondary_role_blocks") or []),
                    "dominant_domains": ", ".join(case.get("dominant_domains") or []),
                    "role_hypotheses": " | ".join(
                        f"{item.get('label')} ({item.get('confidence')})" for item in case.get("role_hypotheses") or []
                    ),
                    "top_profile_signals": " | ".join(case.get("top_profile_signals") or []),
                    "profile_summary": case.get("profile_summary"),
                    "ai_triggered": case.get("ai_triggered"),
                    "ai_accepted": case.get("ai_accepted"),
                    "ai_suggested_role_block": case.get("ai_suggested_role_block"),
                    "ai_helped": case.get("ai_helped"),
                    "ai_hurt": case.get("ai_hurt"),
                    "notes": case.get("notes"),
                    "path": case.get("path"),
                    "error": case.get("error"),
                }
            )


def main() -> None:
    synthetic_cases = _build_synthetic_cases()
    real_cases = _build_real_cases()
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "synthetic_summary": _aggregate(synthetic_cases),
        "real_summary": _aggregate(real_cases),
        "coverage_notes": [
            "Real CV validation uses local PDF CVs available on this machine.",
            "No strong real HR or pure sales CV was found locally; those families remain synthetic-only in this sprint.",
        ],
        "synthetic_cases": synthetic_cases,
        "real_cases": real_cases,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(synthetic_cases + real_cases)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
