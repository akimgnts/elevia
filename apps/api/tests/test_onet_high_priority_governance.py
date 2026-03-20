from __future__ import annotations

import sqlite3

from integrations.onet.governance.high_priority_decisions import (
    HIGH_PRIORITY_GOVERNANCE_DECISIONS,
    apply_high_priority_governance,
)
from integrations.onet.repository import OnetRepository


def test_high_priority_governance_covers_exactly_60_review_rows():
    assert len(HIGH_PRIORITY_GOVERNANCE_DECISIONS) == 60


def test_apply_high_priority_governance_handles_mapping_approval_and_rejection(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    rows = [
        (
            "technology_skills:43231602",
            "sap software",
            "SAP software",
            "technology_skills",
            "43231602",
        ),
        (
            "technology_skills:43233405",
            "screen reader software",
            "Screen reader software",
            "technology_skills",
            "43233405",
        ),
        (
            "technology_skills:43231513",
            "microsoft office software",
            "Microsoft Office software",
            "technology_skills",
            "43231513",
        ),
    ]

    with repo.connect() as conn:
        conn.executemany(
            """
            INSERT INTO onet_skill (
                external_skill_id, source_table, source_key, skill_name, skill_name_norm, source_hash, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'hash', 'active', '2026-01-01T00:00:00Z')
            """,
            [(external_skill_id, source_table, source_key, skill_name, skill_name_norm) for external_skill_id, skill_name_norm, skill_name, source_table, source_key in rows],
        )
        conn.executemany(
            """
            INSERT INTO onet_canonical_promotion_candidate (
                external_skill_id, proposed_canonical_id, proposed_label, proposed_entity_type,
                source_table, status, review_status, reason, match_weight_policy,
                display_policy, promotion_score, promotion_tier, triage_reason,
                evidence_json, source_hash, updated_at
            ) VALUES (?, ?, ?, 'skill_tool', ?, 'proposed_from_onet', 'pending', 'discriminant_external_skill',
                      'matching_secondary', 'standard', 0.9, 'high_priority', 'seed', '{}', 'hash', '2026-01-01T00:00:00Z')
            """,
            [
                (external_skill_id, f"skill:{skill_name_norm.replace(' ', '_')}", skill_name, source_table)
                for external_skill_id, skill_name_norm, skill_name, source_table, _source_key in rows
            ],
        )
        conn.commit()

    summary = apply_high_priority_governance(
        repo,
        external_skill_ids=[
            "technology_skills:43231602",
            "technology_skills:43233405",
            "technology_skills:43231513",
        ],
    )

    assert summary["reviewed"] == 3
    assert summary["mapped_rows"] == 4
    assert summary["approved_new"] == 1
    assert summary["rejected"] == 1
    assert summary["mapped_existing"] == 1

    conn = sqlite3.connect(str(tmp_path / "onet.db"))
    conn.row_factory = sqlite3.Row

    sap_rows = conn.execute(
        """
        SELECT canonical_skill_id, status
        FROM onet_skill_mapping_to_canonical
        WHERE external_skill_id = 'technology_skills:43231602'
        ORDER BY canonical_skill_id
        """
    ).fetchall()
    accessibility_mapping = conn.execute(
        """
        SELECT canonical_skill_id, status
        FROM onet_skill_mapping_to_canonical
        WHERE external_skill_id = 'technology_skills:43233405'
        """
    ).fetchone()
    approved_proposal = conn.execute(
        """
        SELECT proposed_canonical_id, proposed_label, review_status
        FROM onet_canonical_promotion_candidate
        WHERE external_skill_id = 'technology_skills:43233405'
        """
    ).fetchone()
    rejected_proposal = conn.execute(
        """
        SELECT review_status, reason
        FROM onet_canonical_promotion_candidate
        WHERE external_skill_id = 'technology_skills:43231513'
        """
    ).fetchone()
    deleted_queue_row = conn.execute(
        """
        SELECT COUNT(*)
        FROM onet_canonical_promotion_candidate
        WHERE external_skill_id = 'technology_skills:43231602'
        """
    ).fetchone()[0]
    conn.close()

    assert [row["canonical_skill_id"] for row in sap_rows] == [
        "skill:erp_usage",
        "skill:procurement_basics",
        "skill:supply_chain_management",
    ]
    assert all(row["status"] == "mapped_existing" for row in sap_rows)
    assert accessibility_mapping["canonical_skill_id"] == "skill:digital_accessibility"
    assert accessibility_mapping["status"] == "mapped"
    assert approved_proposal["proposed_canonical_id"] == "skill:digital_accessibility"
    assert approved_proposal["proposed_label"] == "Digital Accessibility"
    assert approved_proposal["review_status"] == "approved"
    assert rejected_proposal["review_status"] == "rejected"
    assert rejected_proposal["reason"] == "generic_tool_suite"
    assert deleted_queue_row == 0
