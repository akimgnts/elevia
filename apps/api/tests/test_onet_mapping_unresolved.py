from integrations.onet.mappers.map_onet_skills_to_canonical import map_onet_skills_to_canonical


def test_onet_mapping_keeps_unresolved_bucket():
    rows = [{
        "external_skill_id": "technology_skills:unknown",
        "source_table": "technology_skills",
        "skill_name": "TotallyImaginaryVendorTool",
    }]

    mappings, unresolved = map_onet_skills_to_canonical(rows)

    assert mappings == []
    assert len(unresolved) == 1
    assert unresolved[0]["reason"] == "no_canonical_match"
    assert unresolved[0]["status"] == "unresolved"
