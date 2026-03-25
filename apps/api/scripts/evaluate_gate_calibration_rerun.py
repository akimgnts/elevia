from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from api.main import app
from api.utils.inbox_catalog import DB_PATH
from api.utils.offer_skills import get_offer_skills_by_offer_ids
from compass.explainability.explanation_builder import build_offer_explanation
from compass.explainability.semantic_explanation_builder import build_semantic_explainability
from compass.offer.offer_intelligence import build_offer_intelligence, evaluate_role_domain_gate
from compass.scoring.scoring_v2 import build_scoring_v2
from compass.scoring.scoring_v3 import build_scoring_v3
from matching import MatchingEngine
from matching.extractors import extract_profile

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "eval" / "gate_calibration_rerun.json"
MAX_OFFERS = 10
TOP_K = 5
MAX_CANDIDATES = 40
MIN_THRESHOLD = 0
FAST_OFFER_IDS = [
    "BF-AZ-SAMPLE-0001",
    "BF-AZ-0018",
    "BF-AZ-0013",
    "BF-AZ-0044",
    "BF-AZ-0012",
    "BF-AZ-0024",
    "BF-AZ-0120",
    "BF-AZ-0082",
    "BF-AZ-0056",
    "BF-AZ-0001",
]

_CONCEPT_EVAL_PATH = Path(__file__).with_name("evaluate_concept_signal_value.py")
_SPEC = importlib.util.spec_from_file_location("evaluate_concept_signal_value", _CONCEPT_EVAL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load {_CONCEPT_EVAL_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
CV_CASES = {case["domain"]: case for case in _MODULE.CV_CASES}


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _parse_publication_date(offer: Dict[str, Any]) -> tuple[int, str]:
    raw = str(offer.get("publication_date") or "")
    if not raw:
        return (0, "")
    candidate = raw.replace("Z", "+00:00")
    try:
        return (int(datetime.fromisoformat(candidate).timestamp()), raw)
    except Exception:
        return (0, raw)


def _load_catalog_slice() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in FAST_OFFER_IDS)
    rows = conn.execute(
        f"""
        SELECT id, source, title, description, company, city, country,
               publication_date, contract_duration, start_date, payload_json
        FROM fact_offers
        WHERE id IN ({placeholders})
        """,
        FAST_OFFER_IDS,
    ).fetchall()
    skills_map = get_offer_skills_by_offer_ids(conn, FAST_OFFER_IDS)
    conn.close()

    offer_by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        offer = dict(row)
        offer_id = str(offer.get("id") or "")
        entry = skills_map.get(offer_id, {})
        if entry.get("skills_uri"):
            offer["skills_uri"] = entry["skills_uri"]
        if entry.get("skills"):
            offer["skills"] = entry["skills"]
        raw_payload = offer.pop("payload_json", None)
        if raw_payload and not offer.get("skills"):
            try:
                payload = json.loads(raw_payload)
            except Exception:
                payload = {}
            skills = payload.get("skills") or payload.get("required_skills") or []
            if isinstance(skills, list):
                offer["skills"] = [str(item) for item in skills if isinstance(item, (str, int, float))]
        offer_by_id[offer_id] = offer

    selected = [offer_by_id[offer_id] for offer_id in FAST_OFFER_IDS if offer_id in offer_by_id]
    return selected[:MAX_OFFERS]


def _profile_payload(parse_body: Dict[str, Any]) -> Dict[str, Any]:
    profile = dict(parse_body.get("profile") or {})
    if parse_body.get("profile_intelligence") and not profile.get("profile_intelligence"):
        profile["profile_intelligence"] = parse_body["profile_intelligence"]
    return profile


def _profile_variants() -> List[Dict[str, str]]:
    return [
        {
            "profile_id": "supply_1",
            "domain": "Supply Chain / Operations",
            "cv_text": CV_CASES["Supply Chain / Operations"]["cv_text"],
        },
        {
            "profile_id": "supply_2",
            "domain": "Supply Chain / Operations",
            "cv_text": CV_CASES["Supply Chain / Operations"]["cv_text"]
            + "\nSupport achat / procurement, suivi fournisseurs, planning capacite, inventory review, KPI supply.",
        },
        {
            "profile_id": "supply_3",
            "domain": "Supply Chain / Operations",
            "cv_text": CV_CASES["Supply Chain / Operations"]["cv_text"]
            + "\nCoordination transport international, service client logistique, process improvement, SAP / TMS.",
        },
        {
            "profile_id": "hr_1",
            "domain": "HR",
            "cv_text": CV_CASES["HR"]["cv_text"],
        },
        {
            "profile_id": "hr_2",
            "domain": "HR",
            "cv_text": CV_CASES["HR"]["cv_text"]
            + "\nSupport RH projet, formation, people reporting, onboarding, coordination managers.",
        },
        {
            "profile_id": "hr_3",
            "domain": "HR",
            "cv_text": CV_CASES["HR"]["cv_text"]
            + "\nTalent acquisition, admin du personnel, tableaux de suivi, HR data / KPI, support recrutement IT.",
        },
        {
            "profile_id": "data_1",
            "domain": "Data / BI",
            "cv_text": CV_CASES["Data / BI"]["cv_text"],
        },
        {
            "profile_id": "data_2",
            "domain": "Data / BI",
            "cv_text": CV_CASES["Data / BI"]["cv_text"]
            + "\nBI finance, reporting controlling, Power BI, SQL, dashboarding metier.",
        },
        {
            "profile_id": "data_3",
            "domain": "Data / BI",
            "cv_text": CV_CASES["Data / BI"]["cv_text"]
            + "\nOps analytics, procurement analytics, data quality, supply reporting, business requests.",
        },
    ]


def _parse_profile(client: TestClient, case: Dict[str, str]) -> Dict[str, Any]:
    response = client.post(
        "/profile/parse-file",
        files={
            "file": (
                f"{_slug(case['profile_id'])}.txt",
                io.BytesIO(case["cv_text"].encode("utf-8")),
                "text/plain",
            )
        },
    )
    response.raise_for_status()
    body = response.json()
    profile = _profile_payload(body)
    return {
        "profile_id": case["profile_id"],
        "domain": case["domain"],
        "profile": profile,
        "profile_intelligence": dict(profile.get("profile_intelligence") or {}),
        "extracted": extract_profile(profile),
    }


def _shared_domains(item: Dict[str, Any]) -> List[str]:
    return list((((item.get("semantic_explainability") or {}).get("domain_alignment") or {}).get("shared_domains") or []))


def _role_alignment(item: Dict[str, Any]) -> str:
    return str((((item.get("semantic_explainability") or {}).get("role_alignment") or {}).get("alignment") or "")).lower()


def _is_correct_metier(item: Dict[str, Any]) -> bool:
    alignment = _role_alignment(item)
    return alignment == "high" or (alignment == "medium" and bool(_shared_domains(item)))


def _is_false_positive(item: Dict[str, Any]) -> bool:
    alignment = _role_alignment(item)
    matched = list((((item.get("semantic_explainability") or {}).get("signal_alignment") or {}).get("matched_signals") or []))
    return alignment == "low" and not _shared_domains(item) and len(matched) <= 1


def _candidate_rows(
    engine: MatchingEngine,
    catalog: List[Dict[str, Any]],
    parsed_profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for offer in catalog:
        result = engine.score_offer(parsed_profile["extracted"], offer)
        score = int(result.score or 0)
        if score < MIN_THRESHOLD:
            continue
        match_debug = result.match_debug or {}
        score_raw = (
            float(match_debug.get("total", 0.0)) / 100.0
            if isinstance(match_debug.get("total"), (int, float))
            else float(score) / 100.0
        )
        rows.append(
            {
                "offer": offer,
                "offer_id": str(offer.get("id") or ""),
                "score": score,
                "score_raw": round(score_raw, 4),
                "match_debug": match_debug,
            }
        )
    rows.sort(key=lambda row: (-int(row["score"]), row["offer_id"]))
    return rows[:MAX_CANDIDATES]


def _build_rank_item(
    *,
    row: Dict[str, Any],
    profile: Dict[str, Any],
    profile_intelligence: Dict[str, Any],
    offer_intelligence: Dict[str, Any],
) -> Dict[str, Any]:
    offer = row["offer"]
    offer_labels = [s.get("label") if isinstance(s, dict) else str(s) for s in (offer.get("skills_display") or offer.get("skills") or [])]
    profile_labels = list(profile.get("matching_skills") or profile.get("skills") or [])
    explanation = build_offer_explanation(
        row["match_debug"],
        score=row["score"],
        confidence=None,
        profile_effective_skills=profile_labels,
        job_required_skills=offer_labels,
    )
    semantic = build_semantic_explainability(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
        explanation=explanation,
    )
    scoring_v2 = build_scoring_v2(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
        semantic_explainability=semantic,
        matching_score=row["score_raw"],
    )
    scoring_v3 = build_scoring_v3(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
        semantic_explainability=semantic,
        explanation=explanation,
        matching_score=row["score_raw"],
    )
    return {
        "offer_id": row["offer_id"],
        "title": offer.get("title"),
        "company": offer.get("company"),
        "matching_v1": row["score"],
        "matching_v1_raw": row["score_raw"],
        "offer_role": offer_intelligence.get("dominant_role_block"),
        "offer_domains": offer_intelligence.get("dominant_domains") or [],
        "scoring_v2": scoring_v2,
        "scoring_v3": scoring_v3,
        "semantic_explainability": semantic,
        "top_offer_signals": offer_intelligence.get("top_offer_signals") or [],
        "required_skills": offer_intelligence.get("required_skills") or [],
    }


def _rank_by(items: List[Dict[str, Any]], score_key: str) -> List[Dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            int(((item.get(score_key) or {}).get("score_pct")) or -1),
            int(item.get("matching_v1") or 0),
            str(item.get("offer_id") or ""),
        ),
        reverse=True,
    )


def _top_view(items: List[Dict[str, Any]], score_key: str) -> List[Dict[str, Any]]:
    ranked = _rank_by(items, score_key)[:TOP_K]
    result: List[Dict[str, Any]] = []
    for item in ranked:
        semantic = item.get("semantic_explainability") or {}
        result.append(
            {
                "offer_id": item.get("offer_id"),
                "title": item.get("title"),
                "company": item.get("company"),
                "matching_v1": item.get("matching_v1"),
                score_key: ((item.get(score_key) or {}).get("score_pct")),
                "role_alignment": ((semantic.get("role_alignment") or {}).get("alignment")),
                "shared_domains": ((semantic.get("domain_alignment") or {}).get("shared_domains") or []),
                "summary": semantic.get("alignment_summary"),
                "offer_role": item.get("offer_role"),
                "offer_domains": item.get("offer_domains") or [],
            }
        )
    return result


def main() -> None:
    started = perf_counter()
    client = TestClient(app)

    print("[gate-rerun] loading catalog slice", flush=True)
    catalog = _load_catalog_slice()
    print(f"[gate-rerun] catalog offers: {len(catalog)}", flush=True)

    print("[gate-rerun] preloading offer intelligence", flush=True)
    offer_cache: Dict[str, Dict[str, Any]] = {}
    for idx, offer in enumerate(catalog, start=1):
        offer_id = str(offer.get("id") or "")
        offer_cache[offer_id] = build_offer_intelligence(offer=offer)
        print(f"[gate-rerun] offer intelligence {idx}/{len(catalog)} {offer_id}", flush=True)

    print("[gate-rerun] parsing profiles", flush=True)
    parsed_profiles = [_parse_profile(client, case) for case in _profile_variants()]

    engine = MatchingEngine(catalog)
    profile_outputs: List[Dict[str, Any]] = []
    summary_rows: List[Dict[str, Any]] = []

    for parsed in parsed_profiles:
        print(f"[gate-rerun] scoring {parsed['profile_id']}", flush=True)
        candidates = _candidate_rows(engine, catalog, parsed)
        rejections: List[Dict[str, Any]] = []
        filtered_rows: List[Dict[str, Any]] = []

        for row in candidates:
            offer_id = row["offer_id"]
            offer_intelligence = offer_cache[offer_id]
            gate = evaluate_role_domain_gate(
                profile_intelligence=parsed["profile_intelligence"],
                offer_intelligence=offer_intelligence,
            )
            if not gate.get("compatible"):
                rejections.append(
                    {
                        "offer_id": offer_id,
                        "title": row["offer"].get("title"),
                        "offer_role": offer_intelligence.get("dominant_role_block"),
                        "offer_domains": offer_intelligence.get("dominant_domains") or [],
                        "role_match": gate.get("effective_role_match") or gate.get("role_match"),
                        "rejection_reason": gate.get("rejection_reason"),
                        "shared_domains": gate.get("shared_domains") or [],
                        "matched_signals": ((gate.get("signal_overlap") or {}).get("matched_signals") or []),
                        "was_potentially_valid": bool(gate.get("was_potentially_valid")),
                    }
                )
                continue
            filtered_rows.append(row)

        ranked_items = [
            _build_rank_item(
                row=row,
                profile=parsed["profile"],
                profile_intelligence=parsed["profile_intelligence"],
                offer_intelligence=offer_cache[row["offer_id"]],
            )
            for row in filtered_rows
        ]

        top_v2 = _top_view(ranked_items, "scoring_v2")
        top_v3 = _top_view(ranked_items, "scoring_v3")
        false_positives_v2 = [item for item in top_v2 if _is_false_positive(next(x for x in ranked_items if x["offer_id"] == item["offer_id"]))]
        false_positives_v3 = [item for item in top_v3 if _is_false_positive(next(x for x in ranked_items if x["offer_id"] == item["offer_id"]))]
        correct_v2 = sum(1 for item in ranked_items if item["offer_id"] in {row["offer_id"] for row in top_v2} and _is_correct_metier(item))
        correct_v3 = sum(1 for item in ranked_items if item["offer_id"] in {row["offer_id"] for row in top_v3} and _is_correct_metier(item))

        profile_output = {
            "profile_id": parsed["profile_id"],
            "profile_domain": parsed["domain"],
            "profile_role": parsed["profile_intelligence"].get("dominant_role_block"),
            "profile_domains": parsed["profile_intelligence"].get("dominant_domains") or [],
            "pool_before": len(candidates),
            "pool_after": len(filtered_rows),
            "top_v2": top_v2,
            "top_v3": top_v3,
            "false_positives": {
                "scoring_v2": false_positives_v2,
                "scoring_v3": false_positives_v3,
            },
            "rejections": rejections[:15],
            "potentially_valid_rejections": [entry for entry in rejections if entry["was_potentially_valid"]][:10],
        }
        profile_outputs.append(profile_output)
        summary_rows.append(
            {
                "profile_id": parsed["profile_id"],
                "profile_domain": parsed["domain"],
                "pool_before": len(candidates),
                "pool_after": len(filtered_rows),
                "top5_correct_v2": correct_v2,
                "top5_correct_v3": correct_v3,
                "false_positives_v2": len(false_positives_v2),
                "false_positives_v3": len(false_positives_v3),
                "potentially_valid_rejections": len([entry for entry in rejections if entry["was_potentially_valid"]]),
            }
        )

    all_top_v2 = [offer for profile in profile_outputs for offer in profile["top_v2"]]
    all_top_v3 = [offer for profile in profile_outputs for offer in profile["top_v3"]]
    total_correct_v2 = sum(row["top5_correct_v2"] for row in summary_rows)
    total_correct_v3 = sum(row["top5_correct_v3"] for row in summary_rows)
    total_fp_v2 = sum(row["false_positives_v2"] for row in summary_rows)
    total_fp_v3 = sum(row["false_positives_v3"] for row in summary_rows)
    pool_before_values = [row["pool_before"] for row in summary_rows]
    pool_after_values = [row["pool_after"] for row in summary_rows]

    output = {
        "config": {
            "catalog_mode": "stable_fast_real_bf_az_slice",
            "max_offers": MAX_OFFERS,
            "min_threshold": MIN_THRESHOLD,
            "max_candidates": MAX_CANDIDATES,
            "top_k": TOP_K,
        },
        "profiles": profile_outputs,
        "metrics_summary": {
            "profile_count": len(profile_outputs),
            "top5_correct_metier_pct": {
                "scoring_v2": round(100.0 * total_correct_v2 / max(len(all_top_v2), 1), 1),
                "scoring_v3": round(100.0 * total_correct_v3 / max(len(all_top_v3), 1), 1),
            },
            "top5_false_positive_pct": {
                "scoring_v2": round(100.0 * total_fp_v2 / max(len(all_top_v2), 1), 1),
                "scoring_v3": round(100.0 * total_fp_v3 / max(len(all_top_v3), 1), 1),
            },
            "avg_pool_before": round(mean(pool_before_values), 1) if pool_before_values else 0.0,
            "avg_pool_after": round(mean(pool_after_values), 1) if pool_after_values else 0.0,
            "min_pool_after": min(pool_after_values) if pool_after_values else 0,
            "max_pool_after": max(pool_after_values) if pool_after_values else 0,
            "potentially_valid_rejections": sum(row["potentially_valid_rejections"] for row in summary_rows),
        },
        "summary_rows": summary_rows,
        "runtime_seconds": round(perf_counter() - started, 2),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"artifact": str(OUT_PATH), "metrics_summary": output["metrics_summary"], "runtime_seconds": output["runtime_seconds"]}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
