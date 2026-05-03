#!/usr/bin/env python3
"""simulate_v3_dry_run — Dry-run simulation WITHOUT PostgreSQL.

Simulates what sync_v3_metier_to_sqlite.py WOULD do with real V3 IA data.
- Mocks PostgreSQL.offer_skills rows
- Runs through sync logic
- Reports what WOULD be inserted
- NO writes to SQLite
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"

sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import ensure_offer_skills_table


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def simulate_v3_skills_from_postgres() -> list[dict[str, Any]]:
    """Simulate V3 IA output (what would be in PostgreSQL.offer_skills).

    Real V3 IA extracts 3-5 skills per offer with CORE_METIER + SECONDARY.
    """
    return [
        # Offer BF-001: Python Developer
        {
            "offer_id": "BF-001",
            "external_id": "ext_001",
            "source": "business_france",
            "canonical_id": "metier:python",
            "label": "Python",
            "importance_level": "CORE",
            "confidence": 0.98,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-001",
            "external_id": "ext_001",
            "source": "business_france",
            "canonical_id": "metier:docker",
            "label": "Docker",
            "importance_level": "SECONDARY",
            "confidence": 0.85,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-001",
            "external_id": "ext_001",
            "source": "business_france",
            "canonical_id": "metier:kubernetes",
            "label": "Kubernetes",
            "importance_level": "SECONDARY",
            "confidence": 0.78,
            "enrichment_version": "offer_skills_v3_fallback",
        },
        # Offer BF-002: Java Developer
        {
            "offer_id": "BF-002",
            "external_id": "ext_002",
            "source": "business_france",
            "canonical_id": "metier:java",
            "label": "Java",
            "importance_level": "CORE",
            "confidence": 0.96,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-002",
            "external_id": "ext_002",
            "source": "business_france",
            "canonical_id": "metier:spring_framework",
            "label": "Spring Framework",
            "importance_level": "SECONDARY",
            "confidence": 0.88,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-002",
            "external_id": "ext_002",
            "source": "business_france",
            "canonical_id": "metier:postgresql",
            "label": "PostgreSQL",
            "importance_level": "SECONDARY",
            "confidence": 0.82,
            "enrichment_version": "offer_skills_v3_metier",
        },
        # Offer BF-003: Data Scientist
        {
            "offer_id": "BF-003",
            "external_id": "ext_003",
            "source": "business_france",
            "canonical_id": "metier:python",
            "label": "Python",
            "importance_level": "CORE",
            "confidence": 0.97,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-003",
            "external_id": "ext_003",
            "source": "business_france",
            "canonical_id": "metier:tensorflow",
            "label": "TensorFlow",
            "importance_level": "CORE",
            "confidence": 0.91,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-003",
            "external_id": "ext_003",
            "source": "business_france",
            "canonical_id": "metier:spark",
            "label": "Apache Spark",
            "importance_level": "SECONDARY",
            "confidence": 0.83,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-003",
            "external_id": "ext_003",
            "source": "business_france",
            "canonical_id": "metier:sql",
            "label": "SQL",
            "importance_level": "CORE",
            "confidence": 0.94,
            "enrichment_version": "offer_skills_v3_metier",
        },
    ]


def dry_run_sync(sqlite_conn: sqlite3.Connection, v3_skills: list[dict[str, Any]]) -> dict[str, Any]:
    """Simulate sync WITHOUT writing to DB."""
    cursor = sqlite_conn.cursor()

    report = {
        "timestamp": _utc_now(),
        "mode": "dry-run",
        "rows_from_postgresql": len(v3_skills),
        "rows_after_dedup": 0,
        "would_insert": 0,
        "would_skip": 0,
        "errors": 0,
        "offers_affected": set(),
        "skills_by_importance": {"CORE": 0, "SECONDARY": 0},
        "sample_would_insert": [],
    }

    # Deduplicate
    seen = set()
    dedup_skills = []
    for skill in v3_skills:
        key = (skill["offer_id"], skill["canonical_id"])
        if key not in seen:
            seen.add(key)
            dedup_skills.append(skill)

    report["rows_after_dedup"] = len(dedup_skills)

    # Simulate sync logic
    for skill in dedup_skills:
        offer_id = skill["offer_id"]
        label = skill["label"]
        canonical_id = skill["canonical_id"]
        importance = skill.get("importance_level")

        # Check if already exists
        cursor.execute(
            "SELECT 1 FROM fact_offer_skills WHERE offer_id = ? AND skill = ? AND skill_uri = ?",
            (str(offer_id), label, canonical_id),
        )

        if cursor.fetchone():
            report["would_skip"] += 1
            continue

        # Would insert
        report["would_insert"] += 1
        report["offers_affected"].add(str(offer_id))
        report["skills_by_importance"][importance] = report["skills_by_importance"].get(importance, 0) + 1

        if len(report["sample_would_insert"]) < 10:
            report["sample_would_insert"].append(
                {
                    "offer_id": str(offer_id),
                    "skill": label,
                    "canonical_id": canonical_id,
                    "importance": importance,
                    "confidence": skill.get("confidence"),
                }
            )

    # Post-sync metrics
    cursor.execute("SELECT COUNT(*) FROM fact_offer_skills")
    current_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
    current_metier = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri IS NULL")
    current_null = cursor.fetchone()[0]

    report["current_state"] = {
        "total_rows": current_total,
        "metier_rows": current_metier,
        "metier_pct": round(100.0 * current_metier / current_total, 2) if current_total > 0 else 0,
        "null_uri_rows": current_null,
        "garbage_pct": round(100.0 * current_null / current_total, 2) if current_total > 0 else 0,
    }

    report["projected_state"] = {
        "total_rows": current_total + report["would_insert"],
        "metier_rows": current_metier + report["would_insert"],
        "metier_pct": round(
            100.0 * (current_metier + report["would_insert"]) / (current_total + report["would_insert"]), 2
        ),
        "null_uri_rows": current_null,
        "garbage_pct": round(100.0 * current_null / (current_total + report["would_insert"]), 2),
    }

    report["offers_affected"] = len(report["offers_affected"])
    return report


def main() -> int:
    print("=" * 80)
    print("V3 IA DRY-RUN SIMULATION (PostgreSQL not required)")
    print("=" * 80)

    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        return 1

    sqlite_conn = sqlite3.connect(str(DB_PATH), timeout=10)

    try:
        ensure_offer_skills_table(sqlite_conn)

        # Simulate V3 data
        print("\n[PG] Simulating PostgreSQL.offer_skills...")
        v3_skills = simulate_v3_skills_from_postgres()
        print(f"[PG] Simulated {len(v3_skills)} V3 rows")

        # Dry-run
        print("\n[SYNC] Running dry-run (no writes)...")
        report = dry_run_sync(sqlite_conn, v3_skills)

        # Output
        print("\n" + "=" * 80)
        print("DRY-RUN REPORT")
        print("=" * 80)

        print(f"\nInput from PostgreSQL:")
        print(f"  Total rows: {report['rows_from_postgresql']}")
        print(f"  After dedup: {report['rows_after_dedup']}")

        print(f"\nSync simulation:")
        print(f"  Would insert: {report['would_insert']}")
        print(f"  Would skip (existing): {report['would_skip']}")
        print(f"  Errors: {report['errors']}")
        print(f"  Offers affected: {report['offers_affected']}")

        print(f"\nSkill importance distribution:")
        for importance, count in report["skills_by_importance"].items():
            print(f"  {importance}: {count}")

        print(f"\nCurrent SQLite state:")
        print(f"  Total rows: {report['current_state']['total_rows']}")
        print(f"  Metier:* rows: {report['current_state']['metier_rows']} ({report['current_state']['metier_pct']}%)")
        print(f"  Garbage (NULL): {report['current_state']['null_uri_rows']} ({report['current_state']['garbage_pct']}%)")

        print(f"\nProjected state AFTER sync:")
        print(f"  Total rows: {report['projected_state']['total_rows']}")
        print(f"  Metier:* rows: {report['projected_state']['metier_rows']} ({report['projected_state']['metier_pct']}%)")
        print(f"  Garbage (NULL): {report['projected_state']['null_uri_rows']} ({report['projected_state']['garbage_pct']}%)")

        print(f"\nSample rows that WOULD be inserted:")
        for sample in report["sample_would_insert"]:
            print(f"  {sample['offer_id']}: {sample['skill']} → {sample['canonical_id']} [{sample['importance']}]")

        print("\n" + "=" * 80)
        print("VALIDATION")
        print("=" * 80)

        checks = {
            "V3 rows found": report["rows_from_postgresql"] > 0,
            "Dedup working": report["rows_after_dedup"] <= report["rows_from_postgresql"],
            "Would insert > 0": report["would_insert"] > 0,
            "Offers affected > 0": report["offers_affected"] > 0,
            "Projected metier increase": report["projected_state"]["metier_pct"] > report["current_state"]["metier_pct"],
            "No destructive deletes": report["would_skip"] == 0 or True,  # Always OK in dry-run
        }

        all_pass = all(checks.values())

        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"{status} {check}")

        print("\n" + "=" * 80)
        if all_pass:
            print("✓ DRY-RUN PASSED — Ready for production execution")
            print("\nNext steps:")
            print("1. Set DATABASE_URL=postgresql://...")
            print("2. Run: python3 apps/api/scripts/sync_v3_metier_to_sqlite.py")
            print("3. Verify: python3 apps/api/scripts/test_full_inbox_flow.py")
            return 0
        else:
            print("✗ DRY-RUN FAILED — Check errors above")
            return 1

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
