#!/usr/bin/env python3
"""load_canonical_skills — populate canonical_skills + canonical_aliases from consolidated v3.

Loads audit/skill_dictionary_consolidated_v3_balanced.json into SQLite DB.

Usage:
    python3 apps/api/scripts/load_canonical_skills.py
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


def main() -> int:
    # Paths (resolve relative to repo root)
    repo_root = Path(__file__).parent.parent.parent.parent
    json_path = repo_root / "audit/skill_dictionary_consolidated_v3_balanced.json"
    db_path = repo_root / "apps/api/data/db/offers.db"

    if not json_path.exists():
        print(f"ERROR: {json_path} not found")
        return 1

    if not db_path.exists():
        print(f"ERROR: {db_path} not found. Run init_db.py first.")
        return 1

    # Load consolidated JSON
    print(f"Loading {json_path}...")
    consolidated = json.loads(json_path.read_text())
    canonical_skills = consolidated["canonical_skills"]
    print(f"  Loaded {len(canonical_skills)} canonical skills\n")

    # Connect to DB
    conn = sqlite3.connect(str(db_path), timeout=10)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"

    try:
        # Clear existing data (optional, change to INSERT OR IGNORE for append)
        print("Clearing existing canonical_skills and canonical_aliases...")
        cursor.execute("DELETE FROM canonical_aliases")
        cursor.execute("DELETE FROM canonical_skills")

        # Insert canonical skills
        print("Inserting canonical skills...")
        for skill in canonical_skills:
            cursor.execute("""
                INSERT INTO canonical_skills
                (canonical_id, label, skill_type, domain_tag, occurrences, aliases_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                skill["canonical_id"],
                skill["label"],
                skill["skill_type"],
                skill["domain_tag"],
                skill["occurrences"],
                len(skill.get("aliases", [])),
                now,
            ))

        conn.commit()
        print(f"  Inserted {len(canonical_skills)} canonical skills\n")

        # Insert aliases
        print("Inserting canonical aliases...")
        total_aliases = 0
        skipped_duplicates = 0

        # Track aliases already inserted to handle duplicates gracefully
        inserted_aliases = set()

        for skill in canonical_skills:
            canonical_id = skill["canonical_id"]
            aliases = skill.get("aliases", [])

            for alias in aliases:
                # Skip if already inserted
                if alias in inserted_aliases:
                    skipped_duplicates += 1
                    continue

                # Detect language by presence of accents
                language = "fr" if any(c in alias for c in "éèêàâôû") else "en"

                try:
                    cursor.execute("""
                        INSERT INTO canonical_aliases
                        (alias, canonical_id, language, normalization_type, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        alias,
                        canonical_id,
                        language,
                        "exact" if alias == skill["label"] else "normalized",
                        now,
                    ))
                    inserted_aliases.add(alias)
                    total_aliases += 1
                except sqlite3.IntegrityError:
                    # Duplicate alias already in DB, skip
                    skipped_duplicates += 1

        conn.commit()
        print(f"  Inserted {total_aliases} aliases")
        print(f"  Skipped {skipped_duplicates} duplicates\n")

        # Verify
        cursor.execute("SELECT COUNT(*) FROM canonical_skills")
        skills_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM canonical_aliases")
        aliases_count = cursor.fetchone()[0]

        print(f"✓ Load complete")
        print(f"  Canonical skills: {skills_count}")
        print(f"  Canonical aliases: {aliases_count}")
        print(f"  Compression: {(total_aliases + len(canonical_skills)) / len(canonical_skills):.2f}x")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
