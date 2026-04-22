#!/usr/bin/env python3
"""
Sprint 2 — Profile parsing + mapping audit.

Reads the 5 frozen profiles from baseline/sprint1/inputs/profiles/ and traces
every input skill through:

    raw  →  normalized  →  alias-expanded  →  map_skill()  →  URI (or drop)

Produces per-profile skill traces, a cross-profile coverage summary, a global
findings report, and a short languages/education appendix.

No code in apps/api/ is modified. The audit reuses the product's public
functions (normalize_skill, _expand_profile_skills, SKILL_ALIASES, map_skill,
extract_profile) exactly as they are.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASELINE_SPRINT2 = Path(__file__).resolve().parent
BASELINE_SPRINT1 = BASELINE_SPRINT2.parent / "sprint1"
API_SRC = BASELINE_SPRINT2.parent.parent / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from esco.extract import SKILL_ALIASES  # noqa: E402
from esco.mapper import map_skill  # noqa: E402
from matching.extractors import (  # noqa: E402
    extract_profile,
    normalize_skill,
    _expand_profile_skills,
)


PROFILES_DIR = BASELINE_SPRINT1 / "inputs" / "profiles"
OFFERS_FILE = BASELINE_SPRINT1 / "inputs" / "offers.json"
OUTPUTS_DIR = BASELINE_SPRINT2 / "outputs"
MANIFEST_FILE = BASELINE_SPRINT2 / "manifest.json"

# Target terms called out in the Sprint 2 brief. We track these specifically.
TARGET_TERMS = [
    "python", "excel", "sql", "powerbi", "sap", "crm",
    "sales", "negotiation", "prospection", "presentation",
    "marketing_digital", "google_analytics",
]


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=BASELINE_SPRINT2, stderr=subprocess.DEVNULL
        )
        return out.decode("ascii").strip()
    except Exception:
        return "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _classify_failure(
    input_skill: str,
    normalized: str,
    alias_labels: list,
    direct_mapped: bool,
    any_mapped: bool,
) -> str:
    """Assign one of the brief's failure categories, justified by the trace.

    Categories:
      - normalization_issue: normalized form empty or mangled
      - alias_expansion_issue: direct map failed AND term has no alias entry
      - mapper_coverage_issue: direct map failed, aliases tried, none mapped
      - pipeline_order_issue: never observed on this trace — placeholder only
      - term_dropped_too_early: normalization collapsed the term to empty
      - unknown_from_current_trace: cannot justify a category from the trace
    """
    if any_mapped:
        return "n_a_mapped"
    if not normalized:
        return "term_dropped_too_early"
    if direct_mapped is False and not alias_labels:
        return "alias_expansion_issue"
    if direct_mapped is False and alias_labels:
        return "mapper_coverage_issue"
    return "unknown_from_current_trace"


def _trace_one_skill(input_skill: str) -> dict:
    """Re-run the product pipeline on a single input skill and capture it step-by-step."""
    if not isinstance(input_skill, str) or not input_skill.strip():
        return {
            "input_skill": input_skill,
            "normalized_input": "",
            "alias_labels": [],
            "mapping_attempts": [],
            "mapped_uris": [],
            "status": "dropped_before_mapping",
            "failure_type": "term_dropped_too_early",
        }

    normalized = normalize_skill(input_skill)

    # Replicate the alias expansion for THIS single term only.
    # _expand_profile_skills operates on lists; run it on the 1-element list
    # to stay faithful to the real pipeline.
    expanded_list = _expand_profile_skills([normalized])
    alias_labels = [s for s in expanded_list if s != normalized]

    attempts = []
    mapped_uris = []
    direct_mapped = False
    for label in ([normalized] if normalized else []) + alias_labels:
        result = map_skill(label, enable_fuzzy=False)  # matches extract_profile call
        if result and result.get("esco_id"):
            attempts.append({
                "label": label,
                "mapped": True,
                "uri": result["esco_id"],
                "esco_label": result.get("label"),
                "method": result.get("method"),
                "confidence": result.get("confidence"),
            })
            mapped_uris.append(result["esco_id"])
            if label == normalized:
                direct_mapped = True
        else:
            attempts.append({
                "label": label,
                "mapped": False,
                "uri": None,
                "esco_label": None,
                "method": None,
                "confidence": None,
            })

    # Deduplicate URIs preserving order
    seen = set()
    deduped = []
    for u in mapped_uris:
        if u and u not in seen:
            seen.add(u)
            deduped.append(u)

    if not normalized:
        status = "dropped_before_mapping"
    elif deduped and direct_mapped:
        status = "mapped"
    elif deduped and not direct_mapped:
        status = "mapped_via_fallback"  # mapped only through alias expansion
    else:
        status = "unmapped"

    failure_type = _classify_failure(
        input_skill=input_skill,
        normalized=normalized,
        alias_labels=alias_labels,
        direct_mapped=direct_mapped,
        any_mapped=bool(deduped),
    )

    return {
        "input_skill": input_skill,
        "normalized_input": normalized,
        "alias_labels": alias_labels,
        "mapping_attempts": attempts,
        "mapped_uris": deduped,
        "status": status,
        "failure_type": failure_type,
    }


def audit_profile(profile_data: dict) -> dict:
    raw_skills = profile_data.get("skills") or []
    # Faithful pipeline call: same function the engine uses.
    extracted = extract_profile(profile_data)

    per_skill_trace = [_trace_one_skill(s) for s in raw_skills]

    input_count = len(raw_skills)
    mapped_count = sum(1 for t in per_skill_trace if t["status"] in {"mapped", "mapped_via_fallback"})
    unmapped_count = sum(1 for t in per_skill_trace if t["status"] == "unmapped")
    dropped_count = sum(1 for t in per_skill_trace if t["status"] == "dropped_before_mapping")

    return {
        "profile_id": profile_data.get("profile_id"),
        "skills_input_count": input_count,
        "skills_after_extraction_count": len(extracted.skills),
        "labels_attempted_mapping_count": sum(len(t["mapping_attempts"]) for t in per_skill_trace),
        "skills_mapped_count": mapped_count,
        "skills_unmapped_count": unmapped_count,
        "skills_dropped_count": dropped_count,
        "coverage_ratio": round(mapped_count / input_count, 3) if input_count else 0.0,
        "skills_uri_count_frozenset": int(extracted.skills_uri_count),
        "skills_unmapped_count_extractor": int(extracted.skills_unmapped_count),
        "per_skill_trace": per_skill_trace,
    }


def run_languages_education_probe(offers: list, profiles: list) -> dict:
    """Quick shape audit of languages and education between offer fixtures and
    the extracted profile expectation — why scores are 0 on Sprint 1 top hits."""
    offer_lang_fields = Counter()
    offer_edu_fields = Counter()
    offer_lang_shapes = Counter()
    offer_edu_shapes = Counter()

    for o in offers:
        for key in ("languages", "languages_required", "language", "required_languages"):
            if key in o:
                offer_lang_fields[key] += 1
                val = o[key]
                if isinstance(val, list) and val:
                    shape = "list_of_" + (
                        "dict_with_code" if isinstance(val[0], dict) and "code" in val[0]
                        else "dict"
                        if isinstance(val[0], dict)
                        else "str"
                    )
                else:
                    shape = "empty_or_non_list"
                offer_lang_shapes[shape] += 1
        for key in ("education", "education_level", "education_summary", "required_education"):
            if key in o:
                offer_edu_fields[key] += 1
                val = o[key]
                if isinstance(val, str):
                    offer_edu_shapes["str"] += 1
                elif isinstance(val, dict):
                    offer_edu_shapes["dict"] += 1
                else:
                    offer_edu_shapes["other"] += 1

    profile_lang_samples = []
    profile_edu_samples = []
    for p in profiles:
        profile_lang_samples.append({
            "profile_id": p.get("profile_id"),
            "languages_raw": p.get("languages"),
        })
        profile_edu_samples.append({
            "profile_id": p.get("profile_id"),
            "education_level_raw": p.get("education_level"),
        })

    return {
        "offer_language_field_counts": dict(offer_lang_fields),
        "offer_language_value_shapes": dict(offer_lang_shapes),
        "offer_education_field_counts": dict(offer_edu_fields),
        "offer_education_value_shapes": dict(offer_edu_shapes),
        "profile_language_raw": profile_lang_samples,
        "profile_education_raw": profile_edu_samples,
        "observations": [
            "Scorer expects offer['languages'] as a list — via _score_languages in matching_v1.py.",
            "Scorer expects offer['education'] (string) — via _score_education in matching_v1.py.",
        ],
    }


def main() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    offers = json.loads(OFFERS_FILE.read_text(encoding="utf-8"))
    profile_files = sorted(PROFILES_DIR.glob("profile_*.json"))
    profiles = [json.loads(pf.read_text(encoding="utf-8")) for pf in profile_files]

    per_profile_results = []
    for pf, pd in zip(profile_files, profiles):
        result = audit_profile(pd)
        out_path = OUTPUTS_DIR / f"skill_trace_{pf.stem}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        per_profile_results.append(result)
        print(
            f"[ok] {pf.name} → in={result['skills_input_count']} "
            f"mapped={result['skills_mapped_count']} "
            f"unmapped={result['skills_unmapped_count']} "
            f"dropped={result['skills_dropped_count']} "
            f"cov={result['coverage_ratio']}"
        )

    # profile_summary.json
    summary = {
        "profiles": [
            {
                "profile_id": r["profile_id"],
                "skills_input_count": r["skills_input_count"],
                "skills_after_extraction_count": r["skills_after_extraction_count"],
                "labels_attempted_mapping_count": r["labels_attempted_mapping_count"],
                "skills_mapped_count": r["skills_mapped_count"],
                "skills_unmapped_count": r["skills_unmapped_count"],
                "skills_dropped_count": r["skills_dropped_count"],
                "coverage_ratio": r["coverage_ratio"],
                "skills_uri_count_frozenset": r["skills_uri_count_frozenset"],
            }
            for r in per_profile_results
        ],
    }
    (OUTPUTS_DIR / "profile_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # global_findings.json
    unmapped_terms = Counter()
    failure_counter = Counter()
    status_counter = Counter()
    target_trace = {t: [] for t in TARGET_TERMS}

    for r in per_profile_results:
        for t in r["per_skill_trace"]:
            status_counter[t["status"]] += 1
            failure_counter[t["failure_type"]] += 1
            if t["status"] == "unmapped":
                unmapped_terms[t["input_skill"].lower()] += 1
            key = t["input_skill"].lower()
            if key in TARGET_TERMS:
                target_trace[key].append({
                    "profile_id": r["profile_id"],
                    "normalized_input": t["normalized_input"],
                    "alias_labels": t["alias_labels"],
                    "mapped_uris": t["mapped_uris"],
                    "status": t["status"],
                    "failure_type": t["failure_type"],
                })

    global_findings = {
        "status_distribution": dict(status_counter),
        "failure_type_distribution": dict(failure_counter),
        "top_unmapped_terms": unmapped_terms.most_common(20),
        "target_term_trace": target_trace,
        "profile_coverage_ranking": sorted(
            [
                {"profile_id": r["profile_id"], "coverage_ratio": r["coverage_ratio"]}
                for r in per_profile_results
            ],
            key=lambda x: x["coverage_ratio"],
            reverse=True,
        ),
        "notes": [
            "status 'mapped_via_fallback' means the input term did NOT map directly but one of its SKILL_ALIASES entries did — signal reaches skills_uri.",
            "skills_unmapped_count_extractor (from extract_profile) counts only direct-mapping failures among normalized inputs; items rescued by alias expansion are still counted as unmapped by that internal metric.",
        ],
    }
    (OUTPUTS_DIR / "global_findings.json").write_text(
        json.dumps(global_findings, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # scoring_inputs_appendix.json
    appendix = run_languages_education_probe(offers, profiles)
    (OUTPUTS_DIR / "scoring_inputs_appendix.json").write_text(
        json.dumps(appendix, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = {
        "sprint": "sprint2_audit_parsing_mapping",
        "generated_at_utc": _utc_now(),
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "env_flags": {
            "ELEVIA_FILTER_GENERIC_URIS": os.getenv("ELEVIA_FILTER_GENERIC_URIS", "unset"),
            "ELEVIA_PROMOTE_ESCO": os.getenv("ELEVIA_PROMOTE_ESCO", "unset"),
            "ELEVIA_DEBUG_MATCHING": os.getenv("ELEVIA_DEBUG_MATCHING", "unset"),
        },
        "inputs": {
            "profiles_dir": str(PROFILES_DIR.relative_to(BASELINE_SPRINT2.parent.parent)),
            "profiles": [pf.name for pf in profile_files],
            "offers_file": str(OFFERS_FILE.relative_to(BASELINE_SPRINT2.parent.parent)),
        },
        "entrypoints_audited": {
            "normalize_skill": "apps/api/src/matching/extractors.py",
            "_expand_profile_skills": "apps/api/src/matching/extractors.py",
            "SKILL_ALIASES": "apps/api/src/esco/extract.py",
            "map_skill": "apps/api/src/esco/mapper.py",
            "extract_profile": "apps/api/src/matching/extractors.py",
        },
        "generated_files": sorted(str(p.relative_to(BASELINE_SPRINT2)) for p in OUTPUTS_DIR.iterdir()),
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[manifest] {MANIFEST_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
