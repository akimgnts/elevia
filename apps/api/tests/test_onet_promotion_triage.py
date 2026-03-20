from __future__ import annotations

import sqlite3
from pathlib import Path

from integrations.onet.repository import OnetRepository
from integrations.onet.triage.promotion_triage import _rank_candidates, run_promotion_triage


def _seed_repo(tmp_path: Path) -> OnetRepository:
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()
    repo.upsert_occupations(
        [
            {
                "onetsoc_code": "15-1252.00",
                "title": "Software Developer",
                "title_norm": "software developer",
                "description": "",
                "source_db_version_name": None,
                "source_hash": "o1",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "onetsoc_code": "15-2051.00",
                "title": "Data Scientist",
                "title_norm": "data scientist",
                "description": "",
                "source_db_version_name": None,
                "source_hash": "o2",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "onetsoc_code": "13-1071.00",
                "title": "Human Resources Specialist",
                "title_norm": "human resources specialist",
                "description": "",
                "source_db_version_name": None,
                "source_hash": "o3",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ]
    )
    repo.upsert_skills(
        [
            {
                "external_skill_id": "tools_used:custom_erp_tool",
                "source_table": "tools_used",
                "source_key": "custom_erp_tool",
                "skill_name": "Custom ERP Tool",
                "skill_name_norm": "custom erp tool",
                "content_element_id": None,
                "commodity_code": None,
                "commodity_title": None,
                "scale_id": None,
                "scale_name": None,
                "source_hash": "s1",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "external_skill_id": "skills:hris",
                "source_table": "skills",
                "source_key": "hris",
                "skill_name": "HRIS",
                "skill_name_norm": "hris",
                "content_element_id": "x1",
                "commodity_code": None,
                "commodity_title": None,
                "scale_id": None,
                "scale_name": None,
                "source_hash": "s2",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "external_skill_id": "skills:analysis",
                "source_table": "skills",
                "source_key": "analysis",
                "skill_name": "Analysis",
                "skill_name_norm": "analysis",
                "content_element_id": "x2",
                "commodity_code": None,
                "commodity_title": None,
                "scale_id": None,
                "scale_name": None,
                "source_hash": "s3",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ]
    )
    repo.upsert_occupation_tools(
        [
            {
                "onetsoc_code": "15-1252.00",
                "external_skill_id": "tools_used:custom_erp_tool",
                "tool_label": "Custom ERP Tool",
                "tool_label_norm": "custom erp tool",
                "commodity_code": None,
                "commodity_title": None,
                "source_hash": "t1",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "onetsoc_code": "15-2051.00",
                "external_skill_id": "tools_used:custom_erp_tool",
                "tool_label": "Custom ERP Tool",
                "tool_label_norm": "custom erp tool",
                "commodity_code": None,
                "commodity_title": None,
                "source_hash": "t2",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ]
    )
    repo.upsert_occupation_skills(
        [
            {
                "onetsoc_code": "13-1071.00",
                "external_skill_id": "skills:hris",
                "scale_name": "importance",
                "data_value": 4.0,
                "n": 10,
                "recommend_suppress": None,
                "not_relevant": None,
                "domain_source": None,
                "source_hash": "l1",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "onetsoc_code": "15-2051.00",
                "external_skill_id": "skills:analysis",
                "scale_name": "importance",
                "data_value": 4.0,
                "n": 10,
                "recommend_suppress": None,
                "not_relevant": None,
                "domain_source": None,
                "source_hash": "l2",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "onetsoc_code": "15-1252.00",
                "external_skill_id": "skills:analysis",
                "scale_name": "importance",
                "data_value": 4.0,
                "n": 10,
                "recommend_suppress": None,
                "not_relevant": None,
                "domain_source": None,
                "source_hash": "l3",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ]
    )
    repo.replace_typed_skill_mapping_outcomes(
        mappings=[],
        proposals=[
            {
                "external_skill_id": "tools_used:custom_erp_tool",
                "proposed_canonical_id": "skill:custom_erp_tool",
                "proposed_label": "Custom ERP Tool",
                "proposed_entity_type": "skill_tool",
                "source_table": "tools_used",
                "status": "proposed_from_onet",
                "review_status": "pending",
                "reason": "discriminant_external_skill",
                "match_weight_policy": "matching_secondary",
                "display_policy": "standard",
                "promotion_score": None,
                "promotion_tier": None,
                "triage_reason": None,
                "evidence_json": "{}",
                "source_hash": "p1",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "external_skill_id": "skills:hris",
                "proposed_canonical_id": "skill:hris",
                "proposed_label": "HRIS",
                "proposed_entity_type": "skill_domain",
                "source_table": "skills",
                "status": "proposed_from_onet",
                "review_status": "pending",
                "reason": "discriminant_external_skill",
                "match_weight_policy": "matching_core",
                "display_policy": "standard",
                "promotion_score": None,
                "promotion_tier": None,
                "triage_reason": None,
                "evidence_json": "{}",
                "source_hash": "p2",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "external_skill_id": "skills:analysis",
                "proposed_canonical_id": "skill:analysis",
                "proposed_label": "Analysis",
                "proposed_entity_type": "skill_domain",
                "source_table": "skills",
                "status": "proposed_from_onet",
                "review_status": "pending",
                "reason": "discriminant_external_skill",
                "match_weight_policy": "matching_core",
                "display_policy": "standard",
                "promotion_score": None,
                "promotion_tier": None,
                "triage_reason": None,
                "evidence_json": "{}",
                "source_hash": "p3",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ],
        rejected=[],
    )
    return repo


def test_promotion_scoring_is_deterministic(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    rows = [dict(r) for r in repo.list_canonical_promotion_candidates(review_status="pending")]
    ranked_a = _rank_candidates(repo, rows)
    ranked_b = _rank_candidates(repo, rows)
    assert [(r.external_skill_id, r.score, r.tier) for r in ranked_a] == [
        (r.external_skill_id, r.score, r.tier) for r in ranked_b
    ]


def test_generic_skills_are_penalized_and_tools_are_boosted(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    rows = [dict(r) for r in repo.list_canonical_promotion_candidates(review_status="pending")]
    ranked = {r.external_skill_id: r for r in _rank_candidates(repo, rows)}

    assert ranked["tools_used:custom_erp_tool"].tool_bonus > 0.0
    assert ranked["skills:analysis"].generic_penalty > ranked["skills:hris"].generic_penalty
    assert ranked["tools_used:custom_erp_tool"].score > ranked["skills:analysis"].score


def test_tier_classification_is_stable(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    rows = [dict(r) for r in repo.list_canonical_promotion_candidates(review_status="pending")]
    ranked = {r.external_skill_id: r for r in _rank_candidates(repo, rows)}

    assert ranked["tools_used:custom_erp_tool"].tier == "high_priority"
    assert ranked["skills:hris"].tier in {"high_priority", "reviewable"}
    assert ranked["skills:analysis"].tier == "rejected_noise"


def test_physical_equipment_is_penalized_more_than_high_value_tech(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    repo.upsert_skills(
        [
            {
                "external_skill_id": "tools_used:reading_stands",
                "source_table": "tools_used",
                "source_key": "reading_stands",
                "skill_name": "Reading stands",
                "skill_name_norm": "reading stands",
                "content_element_id": None,
                "commodity_code": None,
                "commodity_title": None,
                "scale_id": None,
                "scale_name": None,
                "source_hash": "s4",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    repo.upsert_occupation_tools(
        [
            {
                "onetsoc_code": "13-1071.00",
                "external_skill_id": "tools_used:reading_stands",
                "tool_label": "Reading stands",
                "tool_label_norm": "reading stands",
                "commodity_code": None,
                "commodity_title": None,
                "source_hash": "t4",
                "status": "active",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    repo.replace_typed_skill_mapping_outcomes(
        mappings=[],
        proposals=[
            {
                "external_skill_id": "tools_used:custom_erp_tool",
                "proposed_canonical_id": "skill:custom_erp_tool",
                "proposed_label": "Custom ERP Tool",
                "proposed_entity_type": "skill_tool",
                "source_table": "tools_used",
                "status": "proposed_from_onet",
                "review_status": "pending",
                "reason": "discriminant_external_skill",
                "match_weight_policy": "matching_secondary",
                "display_policy": "standard",
                "promotion_score": None,
                "promotion_tier": None,
                "triage_reason": None,
                "evidence_json": "{}",
                "source_hash": "p1",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "external_skill_id": "tools_used:reading_stands",
                "proposed_canonical_id": "skill:reading_stands",
                "proposed_label": "Reading stands",
                "proposed_entity_type": "skill_tool",
                "source_table": "tools_used",
                "status": "proposed_from_onet",
                "review_status": "pending",
                "reason": "discriminant_external_skill",
                "match_weight_policy": "matching_secondary",
                "display_policy": "standard",
                "promotion_score": None,
                "promotion_tier": None,
                "triage_reason": None,
                "evidence_json": "{}",
                "source_hash": "p4",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        ],
        rejected=[],
    )
    rows = [dict(r) for r in repo.list_canonical_promotion_candidates(review_status="pending")]
    ranked = {r.external_skill_id: r for r in _rank_candidates(repo, rows)}
    assert ranked["tools_used:reading_stands"].physical_penalty > 0.0
    assert ranked["tools_used:reading_stands"].score < ranked["tools_used:custom_erp_tool"].score
    assert ranked["tools_used:reading_stands"].tier in {"rejected_noise", "deferred_long_tail"}


def test_run_promotion_triage_updates_db_and_writes_report(tmp_path: Path):
    repo = _seed_repo(tmp_path)
    report_path = tmp_path / "report.json"
    report = run_promotion_triage(repo, report_path=report_path)

    assert report_path.exists()
    assert report["tier_distribution"]

    conn = sqlite3.connect(str(tmp_path / "onet.db"))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT promotion_score, promotion_tier, triage_reason FROM onet_canonical_promotion_candidate "
        "WHERE external_skill_id = 'tools_used:custom_erp_tool'"
    ).fetchone()
    conn.close()

    assert row["promotion_score"] is not None
    assert row["promotion_tier"] == "high_priority"
    assert row["triage_reason"]
