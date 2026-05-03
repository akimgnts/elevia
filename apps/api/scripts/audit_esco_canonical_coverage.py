#!/usr/bin/env python3
"""audit_esco_canonical_coverage — check ESCO → canonical_skills mapping coverage."""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from collections import defaultdict
import re
import unicodedata


def normalize_label(label: str) -> str:
    """Normalize label for comparison."""
    s = label.lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[\s\-_/]+', '_', s)
    s = re.sub(r'[^a-z0-9_]', '', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')


def similarity_score(s1: str, s2: str) -> float:
    """Simple word overlap similarity [0-1]."""
    words1 = set(normalize_label(s1).split('_'))
    words2 = set(normalize_label(s2).split('_'))
    if not words1 or not words2:
        return 0.0
    overlap = len(words1 & words2)
    union = len(words1 | words2)
    return overlap / union if union > 0 else 0.0


def main() -> int:
    # Load canonical skills
    consolidated_path = Path("audit/skill_dictionary_consolidated_v3_balanced.json")
    consolidated = json.loads(consolidated_path.read_text())
    canonical_skills = consolidated["canonical_skills"]

    # Build canonical lookup (label → skill)
    canonical_by_label = {}
    for skill in canonical_skills:
        label_norm = normalize_label(skill["label"])
        canonical_by_label[label_norm] = skill

    # Load ESCO skills from DB
    db_path = Path("apps/api/data/db/offers.db")
    conn = sqlite3.connect(str(db_path))

    cursor = conn.execute("""
        SELECT DISTINCT skill FROM fact_offer_skills
        WHERE source = 'esco'
        ORDER BY skill
    """)
    esco_skills = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"ESCO Skills Audit")
    print(f"================\n")
    print(f"Total ESCO skills in DB: {len(esco_skills)}\n")

    # Try to map each ESCO skill
    mapped = []
    unmapped = []
    partial_matches = []

    for esco_skill in esco_skills:
        esco_norm = normalize_label(esco_skill)

        # Exact match
        if esco_norm in canonical_by_label:
            canonical = canonical_by_label[esco_norm]
            mapped.append({
                "esco": esco_skill,
                "canonical": canonical["label"],
                "canonical_id": canonical["canonical_id"],
                "method": "exact_match",
                "score": 1.0,
            })
            continue

        # Fuzzy match
        best_match = None
        best_score = 0.5  # Threshold

        for canon_norm, canonical in canonical_by_label.items():
            score = similarity_score(esco_skill, canonical["label"])
            if score > best_score:
                best_score = score
                best_match = canonical

        if best_match:
            partial_matches.append({
                "esco": esco_skill,
                "canonical": best_match["label"],
                "canonical_id": best_match["canonical_id"],
                "method": "fuzzy_match",
                "score": best_score,
            })
        else:
            unmapped.append(esco_skill)

    # Report
    print(f"Mapping Results:")
    print(f"  Exact matches: {len(mapped)}")
    print(f"  Fuzzy matches (0.5-1.0): {len(partial_matches)}")
    print(f"  Unmapped: {len(unmapped)}")
    print(f"  Coverage: {(len(mapped) + len(partial_matches)) / len(esco_skills) * 100:.1f}%\n")

    print(f"Exact Matches ({len(mapped)}):")
    for item in mapped:
        print(f"  ✓ {item['esco']} → {item['canonical']}")

    if partial_matches:
        print(f"\nFuzzy Matches ({len(partial_matches)}):")
        for item in sorted(partial_matches, key=lambda x: -x["score"])[:15]:
            print(f"  ~ {item['esco']} → {item['canonical']} ({item['score']:.2f})")

    if unmapped:
        print(f"\nUnmapped ({len(unmapped)}):")
        for esco_skill in unmapped[:10]:
            print(f"  ✗ {esco_skill}")
        if len(unmapped) > 10:
            print(f"  ... and {len(unmapped) - 10} more")

    # Save mapping
    mapping = {
        "total_esco_skills": len(esco_skills),
        "exact_matches": len(mapped),
        "fuzzy_matches": len(partial_matches),
        "unmapped": len(unmapped),
        "coverage_percent": round((len(mapped) + len(partial_matches)) / len(esco_skills) * 100, 1),
        "mappings": {
            "exact": mapped,
            "fuzzy": partial_matches,
            "unmapped": unmapped,
        }
    }

    output_path = Path("audit/esco_canonical_coverage.json")
    output_path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n")
    print(f"\nSaved to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
