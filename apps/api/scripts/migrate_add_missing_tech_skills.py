#!/usr/bin/env python3
"""migrate_add_missing_tech_skills — add 13 missing tech skills to canonical dictionary.

Deterministic, hardcoded skill definitions. No AI expansion.
Bounded to skills identified in CV extraction gap analysis.

Skills added:
1. javascript, typescript (web languages)
2. react, django, flask (frameworks)
3. docker, terraform (devops/infra)
4. postgresql, mongodb (databases)
5. tensorflow, spark, hadoop (data engineering)
6. gcp (cloud)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Hardcoded skill definitions (no expansion)
TECH_SKILLS_TO_ADD = [
    {
        "canonical_id": "metier:javascript",
        "label": "javascript",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,  # Placeholder
        "aliases": ["javascript", "js"],
    },
    {
        "canonical_id": "metier:typescript",
        "label": "typescript",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["typescript", "ts"],
    },
    {
        "canonical_id": "metier:react",
        "label": "react",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["react", "reactjs"],
    },
    {
        "canonical_id": "metier:django",
        "label": "django",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["django", "django_framework"],
    },
    {
        "canonical_id": "metier:flask",
        "label": "flask",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["flask", "flask_framework"],
    },
    {
        "canonical_id": "metier:docker",
        "label": "docker",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["docker", "containerization"],
    },
    {
        "canonical_id": "metier:terraform",
        "label": "terraform",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["terraform", "infrastructure_as_code"],
    },
    {
        "canonical_id": "metier:postgresql",
        "label": "postgresql",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["postgresql", "postgres", "postgresql_database"],
    },
    {
        "canonical_id": "metier:mongodb",
        "label": "mongodb",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["mongodb", "mongo", "nosql_database"],
    },
    {
        "canonical_id": "metier:tensorflow",
        "label": "tensorflow",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["tensorflow", "tf"],
    },
    {
        "canonical_id": "metier:spark",
        "label": "spark",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["spark", "apache_spark"],
    },
    {
        "canonical_id": "metier:hadoop",
        "label": "hadoop",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["hadoop", "apache_hadoop"],
    },
    {
        "canonical_id": "metier:gcp",
        "label": "gcp",
        "skill_type": "TOOL",
        "domain_tag": "tools",
        "occurrences": 1,
        "aliases": ["gcp", "google_cloud_platform", "google_cloud"],
    },
]


def main() -> int:
    db_path = Path("apps/api/data/db/offers.db")
    if not db_path.exists():
        print(f"ERROR: {db_path} not found")
        return 1

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"

    try:
        # Insert canonical skills
        print(f"Adding {len(TECH_SKILLS_TO_ADD)} tech skills to canonical_skills...\n")
        added = 0
        skipped = 0

        for skill_def in TECH_SKILLS_TO_ADD:
            canonical_id = skill_def["canonical_id"]

            # Check if already exists
            cursor.execute("SELECT 1 FROM canonical_skills WHERE canonical_id = ?", (canonical_id,))
            if cursor.fetchone():
                print(f"  ⊘ {skill_def['label']}: already exists")
                skipped += 1
                continue

            # Insert canonical skill
            cursor.execute("""
                INSERT INTO canonical_skills
                (canonical_id, label, skill_type, domain_tag, occurrences, aliases_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                canonical_id,
                skill_def["label"],
                skill_def["skill_type"],
                skill_def["domain_tag"],
                skill_def["occurrences"],
                len(skill_def["aliases"]),
                now,
            ))

            # Insert aliases
            for alias in skill_def["aliases"]:
                language = "en"  # All tech skills are English
                cursor.execute("""
                    INSERT INTO canonical_aliases
                    (alias, canonical_id, language, normalization_type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    alias,
                    canonical_id,
                    language,
                    "exact" if alias == skill_def["label"] else "normalized",
                    now,
                ))

            print(f"  ✓ {skill_def['label']}: added with {len(skill_def['aliases'])} aliases")
            added += 1

        conn.commit()
        print(f"\n✓ Migration complete")
        print(f"  Added: {added}")
        print(f"  Skipped: {skipped}")

        # Verify
        cursor.execute("SELECT COUNT(*) FROM canonical_skills")
        total_skills = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM canonical_aliases")
        total_aliases = cursor.fetchone()[0]

        print(f"\nDatabase state:")
        print(f"  Total canonical_skills: {total_skills}")
        print(f"  Total canonical_aliases: {total_aliases}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
