#!/usr/bin/env python3
"""test_sync_v3_metier — Validate V3 sync script behavior (SQLite simulation)."""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.utils.offer_skills import ensure_offer_skills_table


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def setup_test_db() -> sqlite3.Connection:
    """Create in-memory SQLite DB for testing."""
    conn = sqlite3.connect(":memory:")
    ensure_offer_skills_table(conn)
    return conn


def simulate_v3_skills() -> list[dict[str, Any]]:
    """Simulate V3 IA skills from PostgreSQL."""
    return [
        {
            "offer_id": "BF-001",
            "external_id": "ext001",
            "source": "business_france",
            "canonical_id": "metier:python",
            "label": "Python",
            "importance_level": "CORE",
            "confidence": 0.95,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-001",
            "external_id": "ext001",
            "source": "business_france",
            "canonical_id": "metier:docker",
            "label": "Docker",
            "importance_level": "SECONDARY",
            "confidence": 0.85,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-002",
            "external_id": "ext002",
            "source": "business_france",
            "canonical_id": "metier:java",
            "label": "Java",
            "importance_level": "CORE",
            "confidence": 0.90,
            "enrichment_version": "offer_skills_v3_metier",
        },
        {
            "offer_id": "BF-002",
            "external_id": "ext002",
            "source": "business_france",
            "canonical_id": "metier:kubernetes",
            "label": "Kubernetes",
            "importance_level": "SECONDARY",
            "confidence": 0.80,
            "enrichment_version": "offer_skills_v3_fallback",
        },
    ]


def sync_v3_to_sqlite(conn: sqlite3.Connection, skills: list[dict[str, Any]], *, dry_run: bool = False) -> dict[str, int]:
    """Sync logic (same as production script)."""
    cursor = conn.cursor()
    stats = {"inserted": 0, "skipped": 0, "errors": 0, "offers": set()}
    timestamp = _utc_now()

    # Deduplicate
    seen = set()
    for skill in skills:
        key = (skill["offer_id"], skill["canonical_id"])
        if key in seen:
            continue
        seen.add(key)

        offer_id = skill["offer_id"]
        label = skill["label"]
        canonical_id = skill["canonical_id"]

        # Check existing
        cursor.execute(
            "SELECT 1 FROM fact_offer_skills WHERE offer_id = ? AND skill = ? AND skill_uri = ?",
            (str(offer_id), label, canonical_id),
        )

        if cursor.fetchone():
            stats["skipped"] += 1
            continue

        try:
            if not dry_run:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO fact_offer_skills
                    (offer_id, skill, skill_uri, source, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(offer_id), label, canonical_id, "manual", skill.get("confidence"), timestamp),
                )
                if cursor.rowcount == 1:
                    stats["inserted"] += 1
                    stats["offers"].add(str(offer_id))
            else:
                stats["inserted"] += 1
                stats["offers"].add(str(offer_id))

        except Exception as e:
            stats["errors"] += 1
            print(f"ERROR: {e}")

    cursor.close()
    if not dry_run:
        conn.commit()

    stats["offers"] = len(stats["offers"])
    return stats


class TestV3Sync:
    """Test V3 sync functionality."""

    def test_insert_new_skills(self):
        """Insert new V3 skills."""
        conn = setup_test_db()
        skills = simulate_v3_skills()

        stats = sync_v3_to_sqlite(conn, skills, dry_run=False)

        assert stats["inserted"] == 4, f"Expected 4 inserted, got {stats['inserted']}"
        assert stats["skipped"] == 0
        assert stats["errors"] == 0
        assert stats["offers"] == 2, f"Expected 2 offers, got {stats['offers']}"

        # Verify rows exist
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
        count = cursor.fetchone()[0]
        assert count == 4, f"Expected 4 rows, found {count}"

        cursor.execute("SELECT COUNT(DISTINCT offer_id) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
        offers = cursor.fetchone()[0]
        assert offers == 2, f"Expected 2 distinct offers, found {offers}"

        conn.close()
        print("✓ test_insert_new_skills PASSED")

    def test_idempotent_rerun(self):
        """Second run should skip existing rows."""
        conn = setup_test_db()
        skills = simulate_v3_skills()

        # First run
        stats1 = sync_v3_to_sqlite(conn, skills, dry_run=False)
        assert stats1["inserted"] == 4

        # Second run (should skip all)
        stats2 = sync_v3_to_sqlite(conn, skills, dry_run=False)
        assert stats2["inserted"] == 0, f"Expected 0 inserted on second run, got {stats2['inserted']}"
        assert stats2["skipped"] == 4, f"Expected 4 skipped, got {stats2['skipped']}"

        # Verify no duplicates
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
        count = cursor.fetchone()[0]
        assert count == 4, f"Expected 4 rows total (no duplicates), found {count}"

        conn.close()
        print("✓ test_idempotent_rerun PASSED")

    def test_dry_run(self):
        """Dry-run should not write to DB."""
        conn = setup_test_db()
        skills = simulate_v3_skills()

        stats = sync_v3_to_sqlite(conn, skills, dry_run=True)

        assert stats["inserted"] == 4, f"Dry-run should count as inserted, got {stats['inserted']}"

        # But DB should be empty
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
        count = cursor.fetchone()[0]
        assert count == 0, f"Dry-run should not write, but found {count} rows"

        conn.close()
        print("✓ test_dry_run PASSED")

    def test_mixed_existing_and_new(self):
        """Handle mix of existing and new skills."""
        conn = setup_test_db()

        # Pre-populate with one skill
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO fact_offer_skills (offer_id, skill, skill_uri, source, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("BF-001", "Python", "metier:python", "manual", 0.95, _utc_now()),
        )
        conn.commit()

        skills = simulate_v3_skills()

        stats = sync_v3_to_sqlite(conn, skills, dry_run=False)

        assert stats["inserted"] == 3, f"Expected 3 new (skipped 1), got {stats['inserted']} inserted"
        assert stats["skipped"] == 1, f"Expected 1 skipped, got {stats['skipped']}"

        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
        count = cursor.fetchone()[0]
        assert count == 4, f"Expected 4 total, found {count}"

        conn.close()
        print("✓ test_mixed_existing_and_new PASSED")

    def test_quality_metrics(self):
        """Check quality metrics after sync."""
        conn = setup_test_db()
        skills = simulate_v3_skills()

        # Before
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills")
        before_total = cursor.fetchone()[0]
        assert before_total == 0

        # Sync
        sync_v3_to_sqlite(conn, skills, dry_run=False)

        # After
        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
        metier_count = cursor.fetchone()[0]
        assert metier_count == 4, f"Expected 4 metier:* rows, found {metier_count}"

        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri IS NULL")
        null_count = cursor.fetchone()[0]
        assert null_count == 0, f"Expected 0 NULL uri rows, found {null_count}"

        conn.close()
        print("✓ test_quality_metrics PASSED")


if __name__ == "__main__":
    test = TestV3Sync()

    test.test_insert_new_skills()
    test.test_idempotent_rerun()
    test.test_dry_run()
    test.test_mixed_existing_and_new()
    test.test_quality_metrics()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
