from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from api.routes import inbox as inbox_routes
from api.routes.profile_file import _build_persisted_profile_data
from compass.pipeline.canonical_mapping_stage import (
    dedupe_canonical_skills_for_display,
    merge_preserved_explicit_canonical_skills,
)


def _preserved_skill(
    *,
    raw_text: str,
    label: str,
    canonical_id: str,
    strategy: str = "label_match",
    source_confidence: float = 0.95,
) -> dict:
    return {
        "raw_text": raw_text,
        "label": label,
        "source_confidence": source_confidence,
        "source_section": "skills",
        "canonical_target": {
            "canonical_id": canonical_id,
            "label": label,
            "strategy": strategy,
        },
    }


def test_merge_preserved_explicit_skills_into_canonical_skills():
    preserved = [
        _preserved_skill(
            raw_text="recrutement",
            label="Recruitment",
            canonical_id="skill:recruitment",
        ),
        _preserved_skill(
            raw_text="analyse financière",
            label="Financial Analysis",
            canonical_id="skill:financial_analysis",
        ),
    ]

    merged = merge_preserved_explicit_canonical_skills([], preserved)

    assert {item["canonical_id"] for item in merged} == {
        "skill:recruitment",
        "skill:financial_analysis",
    }
    assert all(item["strategy"] == "synonym_match" for item in merged)
    assert all(item["source"] == "preserved_explicit" for item in merged)


def test_merge_preserved_explicit_skills_does_not_duplicate_existing_canonical_ids():
    existing = [
        {
            "raw": "recrutement",
            "canonical_id": "skill:recruitment",
            "label": "Recruitment",
            "strategy": "synonym_match",
            "confidence": 1.0,
            "cluster_name": None,
            "genericity_score": None,
        }
    ]
    preserved = [
        _preserved_skill(
            raw_text="recrutement",
            label="Recruitment",
            canonical_id="skill:recruitment",
        )
    ]

    merged = merge_preserved_explicit_canonical_skills(existing, preserved)
    deduped, _debug = dedupe_canonical_skills_for_display(merged, [])

    recruitment = [item for item in deduped if item.get("canonical_id") == "skill:recruitment"]
    assert len(recruitment) == 1


def test_build_persisted_profile_data_includes_canonical_runtime_fields():
    response_payload = {
        "profile": {"skills": ["anglais"], "matching_skills": ["anglais"]},
        "canonical_skills": [
            {
                "raw": "recrutement",
                "canonical_id": "skill:recruitment",
                "label": "Recruitment",
                "strategy": "synonym_match",
                "confidence": 1.0,
                "cluster_name": None,
                "genericity_score": None,
            }
        ],
        "canonical_skills_count": 1,
        "preserved_explicit_skills": [
            _preserved_skill(
                raw_text="recrutement",
                label="Recruitment",
                canonical_id="skill:recruitment",
            )
        ],
        "profile_summary_skills": [
            _preserved_skill(
                raw_text="plan de formation",
                label="Training Coordination",
                canonical_id="skill:training_coordination",
                strategy="task_phrase_match",
            )
        ],
    }

    persisted = _build_persisted_profile_data(response_payload)

    assert persisted["skills"] == ["anglais"]
    assert persisted["canonical_skills_count"] == 1
    assert persisted["canonical_skills"][0]["canonical_id"] == "skill:recruitment"
    assert persisted["preserved_explicit_skills"][0]["canonical_target"]["canonical_id"] == "skill:recruitment"
    assert persisted["profile_summary_skills"][0]["canonical_target"]["canonical_id"] == "skill:training_coordination"


def test_build_persisted_profile_data_recovers_canonical_skills_from_preserved_explicit():
    response_payload = {
        "profile": {"skills": ["anglais"], "matching_skills": ["anglais"]},
        "canonical_skills": [],
        "canonical_skills_count": 0,
        "preserved_explicit_skills": [
            _preserved_skill(
                raw_text="analyse financière",
                label="Financial Analysis",
                canonical_id="skill:financial_analysis",
            ),
            _preserved_skill(
                raw_text="conformité",
                label="Compliance",
                canonical_id="skill:compliance",
                strategy="text_match",
            ),
        ],
        "profile_summary_skills": [],
    }

    persisted = _build_persisted_profile_data(response_payload)

    assert persisted["canonical_skills_count"] == 2
    assert {item["canonical_id"] for item in persisted["canonical_skills"]} == {
        "skill:financial_analysis",
        "skill:compliance",
    }


def test_inbox_load_profile_keeps_canonical_skills_from_db(monkeypatch):
    db_profile = {
        "skills": ["anglais"],
        "matching_skills": ["anglais"],
        "canonical_skills": [
            {
                "canonical_id": "skill:compliance",
                "label": "Compliance",
                "strategy": "synonym_match",
                "confidence": 1.0,
            }
        ],
        "canonical_skills_count": 1,
    }

    monkeypatch.setattr(inbox_routes, "get_profile_from_db", lambda _profile_id: db_profile)

    profile, source = inbox_routes._load_profile("profile-1", {})

    assert source == "db"
    assert profile["canonical_skills"][0]["canonical_id"] == "skill:compliance"
    assert profile["canonical_skills_count"] == 1
