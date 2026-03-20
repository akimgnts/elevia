from __future__ import annotations

from compass.canonical.master_store import reset_master_canonical_store
from integrations.onet.mappers.map_onet_typed_canonical import classify_onet_skills_for_typed_canonical


def setup_function() -> None:
    reset_master_canonical_store()


def test_typed_onet_mapping_maps_existing_canonical_skill():
    mappings, proposals, rejected = classify_onet_skills_for_typed_canonical([
        {
            "external_skill_id": "technology_skills:python",
            "source_table": "technology_skills",
            "skill_name": "Python",
        }
    ])

    assert len(mappings) == 1
    assert mappings[0]["status"] == "mapped_existing"
    assert proposals == []
    assert rejected == []


def test_typed_onet_mapping_rejects_generic_noise():
    mappings, proposals, rejected = classify_onet_skills_for_typed_canonical([
        {
            "external_skill_id": "skills:active_listening",
            "source_table": "skills",
            "skill_name": "Active Listening",
        }
    ])

    assert mappings == []
    assert proposals == []
    assert len(rejected) == 1
    assert rejected[0]["status"] == "rejected_noise"
    assert rejected[0]["reason"] == "generic_non_discriminant_skill"


def test_typed_onet_mapping_proposes_discriminant_new_canonical():
    mappings, proposals, rejected = classify_onet_skills_for_typed_canonical([
        {
            "external_skill_id": "skills:hris",
            "source_table": "skills",
            "skill_name": "HRIS",
        }
    ])

    assert mappings == []
    assert len(proposals) == 1
    assert proposals[0]["status"] == "proposed_from_onet"
    assert proposals[0]["proposed_canonical_id"] == "skill:hris"
    assert proposals[0]["proposed_entity_type"] == "skill_domain"
    assert rejected == []


def test_typed_onet_mapping_rejects_low_signal_onet_skill_rows():
    mappings, proposals, rejected = classify_onet_skills_for_typed_canonical([
        {
            "external_skill_id": "skills:mathematics",
            "source_table": "skills",
            "skill_name": "Mathematics",
        }
    ])

    assert mappings == []
    assert proposals == []
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "low_signal_onet_skill"
