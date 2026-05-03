#!/usr/bin/env python3
"""backfill_offer_skills_canonical — map offer labels to canonical_ids via aliases.

Deterministic backfill: read fact_offer_skills labels, map through canonical_aliases,
populate fact_offer_skills.skill_uri with metier:* canonical IDs.

No ESCO mapping. No AI. No refactoring. Just: label → canonical_id.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path


def normalize_label(label: str) -> str:
    """Normalize label for matching."""
    s = label.lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[\s\-_/]+', '_', s)
    s = re.sub(r'[^a-z0-9_]', '', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')


def main() -> int:
    db_path = Path("apps/api/data/db/offers.db")
    if not db_path.exists():
        print(f"ERROR: {db_path} not found")
        return 1

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Load canonical_aliases for lookup
        print("Loading canonical_aliases...")
        cursor.execute("""
            SELECT alias, canonical_id
            FROM canonical_aliases
        """)

        alias_map = {}  # normalized_alias → canonical_id
        for alias, canonical_id in cursor.fetchall():
            norm = normalize_label(alias)
            # Keep first match (most common)
            if norm not in alias_map:
                alias_map[norm] = canonical_id

        print(f"  Loaded {len(alias_map)} aliases\n")

        # Find manual skills to backfill
        print("Finding manual skills to backfill...")
        cursor.execute("""
            SELECT DISTINCT skill FROM fact_offer_skills
            WHERE source = 'manual' AND skill_uri IS NULL
            ORDER BY skill
        """)

        manual_skills = [row[0] for row in cursor.fetchall()]
        print(f"  Found {len(manual_skills)} unmapped manual skills\n")

        # Map each skill
        print("Mapping to canonical_ids...")
        mapped = 0
        unmapped = 0
        mappings = {}  # skill → canonical_id

        for skill in manual_skills:
            norm = normalize_label(skill)

            if norm in alias_map:
                canonical_id = alias_map[norm]
                mappings[skill] = canonical_id
                mapped += 1
            else:
                unmapped += 1

        print(f"  Mapped: {mapped}")
        print(f"  Unmapped: {unmapped}")
        print(f"  Coverage: {mapped / len(manual_skills) * 100:.1f}%\n")

        # Backfill fact_offer_skills
        print("Backfilling fact_offer_skills...")
        backfilled = 0

        for skill, canonical_id in mappings.items():
            cursor.execute("""
                UPDATE fact_offer_skills
                SET skill_uri = ?
                WHERE skill = ? AND source = 'manual' AND skill_uri IS NULL
            """, (canonical_id, skill))

            backfilled += cursor.rowcount

        conn.commit()
        print(f"  Updated {backfilled} rows\n")

        # Verify backfill
        print("Verification:")
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM fact_offer_skills
            WHERE skill_uri LIKE 'metier:%'
            GROUP BY source
        """)

        for source, count in cursor.fetchall():
            print(f"  {source}: {count} skills with metier:* URIs")

        # Sample 20 offers with their canonical skills
        print(f"\nSample: 20 offers with canonical skills")
        print(f"{'-' * 70}")

        cursor.execute("""
            SELECT DISTINCT o.id, o.title, COUNT(DISTINCT os.canonical_id) as skill_count
            FROM (
                SELECT DISTINCT offer_id FROM fact_offer_skills
                WHERE skill_uri LIKE 'metier:%'
                LIMIT 20
            ) oid
            JOIN (SELECT DISTINCT offer_id, skill_uri as canonical_id FROM fact_offer_skills
                  WHERE skill_uri LIKE 'metier:%') os ON oid.offer_id = os.offer_id
            JOIN fact_offers o ON o.id = oid.offer_id
            GROUP BY o.id, o.title
            ORDER BY skill_count DESC
        """)

        for offer_id, title, skill_count in cursor.fetchall():
            # Get canonical skills for this offer
            cursor.execute("""
                SELECT DISTINCT skill_uri FROM fact_offer_skills
                WHERE offer_id = ? AND skill_uri LIKE 'metier:%'
                ORDER BY skill_uri
            """, (offer_id,))

            skills = [row[0] for row in cursor.fetchall()]
            print(f"\n{title}")
            print(f"  Canonical skills: {skill_count}")
            for skill in skills[:5]:
                print(f"    • {skill}")
            if len(skills) > 5:
                print(f"    ... and {len(skills) - 5} more")

        print(f"\n{'=' * 70}")
        print(f"✓ Backfill complete")
        print(f"  Mapped: {mapped}/{len(manual_skills)}")
        print(f"  Ready for matching: CV and offers both use metier:* URIs")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
