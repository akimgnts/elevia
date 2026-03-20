from integrations.onet.mappers.map_onet_skills_to_canonical import map_onet_skills_to_canonical


def test_onet_mapping_maps_exact_or_alias_when_available():
    rows = [{
        "external_skill_id": "technology_skills:python",
        "source_table": "technology_skills",
        "skill_name": "Python",
    }]

    mappings, unresolved = map_onet_skills_to_canonical(rows)

    assert len(mappings) == 1
    assert mappings[0]["canonical_skill_id"]
    assert mappings[0]["status"] == "mapped"
    assert unresolved == []
