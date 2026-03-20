#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.canonical.canonical_store import normalize_canonical_key
from compass.profile_structurer import structure_profile_text_v1
from integrations.onet.repository import OnetRepository
from profile.baseline_parser import run_baseline

SAMPLE_CV = """
Alex Martin
Senior Software Developer

Experience
Software Developer - Full Stack
TechNova, Paris
2021 - Present
Built backend services in Python and Java. Worked with SQL, Git, Docker, Linux, Jira, AWS and REST APIs.
Led CI/CD improvements and automated deployments.

Previous Experience
Web Developer
Digital Forge
2018 - 2021
Developed React and TypeScript applications, integrated PostgreSQL and analytics dashboards.
""".strip()

SENIORITY_PREFIXES = (
    "senior ",
    "junior ",
    "lead ",
    "principal ",
    "head ",
    "staff ",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare CV canonical signals with and without O*NET enrichment")
    parser.add_argument("--file", help="Optional text file containing CV text")
    return parser


def derive_title_candidates(cv_text: str, extracted_titles: list[str]) -> list[str]:
    candidates: list[str] = []

    def add(value: str) -> None:
        norm = normalize_canonical_key(value)
        if not norm:
            return
        token_count = len([t for t in norm.split() if t])
        if token_count < 1 or token_count > 6:
            return
        if norm not in candidates:
            candidates.append(norm)
        for prefix in SENIORITY_PREFIXES:
            if norm.startswith(prefix):
                stripped = norm[len(prefix):].strip()
                if stripped and stripped not in candidates:
                    candidates.append(stripped)

    for title in extracted_titles:
        add(title)

    for raw_line in cv_text.splitlines()[:30]:
        line = " ".join(raw_line.split()).strip()
        if not line or len(line) > 90:
            continue
        for piece in re.split(r"[|/,\u2013\u2014-]+", line):
            piece = piece.strip()
            if piece:
                add(piece)

    return candidates


def main() -> int:
    args = build_parser().parse_args()
    if args.file:
        cv_text = Path(args.file).read_text(encoding="utf-8")
    else:
        cv_text = SAMPLE_CV

    baseline = run_baseline(cv_text, profile_id="cv-onet-compare")
    structured = structure_profile_text_v1(cv_text, debug=False)
    title_candidates = derive_title_candidates(cv_text, structured.extracted_titles)

    db_path = Path(os.getenv("ONET_DB_PATH", "apps/api/data/db/onet.db"))
    repo = OnetRepository(db_path)
    occupation_rows = repo.find_occupations_by_title_norms(title_candidates)
    occupation_codes = []
    occupations = []
    for row in occupation_rows:
        code = row["onetsoc_code"]
        if code in occupation_codes:
            continue
        occupation_codes.append(code)
        occupations.append({
            "onetsoc_code": code,
            "title": row["title"],
            "match_source": row["match_source"],
        })

    mapped_rows = repo.get_mapped_canonical_for_occupations(occupation_codes)
    baseline_set = set(baseline.get("skills_canonical") or [])
    onet_ids = []
    onet_labels = []
    for row in mapped_rows:
        cid = row["canonical_skill_id"]
        if cid and cid not in onet_ids:
            onet_ids.append(cid)
            onet_labels.append({
                "canonical_skill_id": cid,
                "canonical_label": row["canonical_label"],
                "source_table": row["source_table"],
                "onet_skill_name": row["skill_name"],
                "confidence_score": row["confidence_score"],
                "onetsoc_code": row["onetsoc_code"],
            })
    added = [cid for cid in onet_ids if cid not in baseline_set]

    result = {
        "baseline_canonical_count": len(baseline_set),
        "baseline_canonical_ids": sorted(baseline_set),
        "title_candidates": title_candidates,
        "matched_occupations": occupations,
        "onet_canonical_count": len(onet_ids),
        "onet_canonical_preview": onet_labels[:20],
        "added_by_onet_count": len(added),
        "added_by_onet_ids": added,
        "combined_canonical_count": len(baseline_set.union(onet_ids)),
        "sample_used": args.file is None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
