from integrations.onet.normalizers.normalize_skills import normalize_skill_rows, normalize_technology_skill_rows, normalize_tool_rows


def test_normalize_skill_rows_builds_skill_and_link_records():
    rows = [{
        "onetsoc_code": "15-1252.00",
        "element_id": "2.A.1.a",
        "element_name": "Reading Comprehension",
        "scale_id": "IM",
        "scale_name": "Importance",
        "data_value": 4.1,
    }]

    skills, links = normalize_skill_rows(rows, source_table="skills")

    assert skills[0]["external_skill_id"] == "skills:2.A.1.a"
    assert skills[0]["skill_name"] == "Reading Comprehension"
    assert links[0]["onetsoc_code"] == "15-1252.00"
    assert links[0]["scale_name"] == "Importance"


def test_normalize_technology_and_tool_rows_build_external_ids():
    tech_rows = [{
        "onetsoc_code": "15-1252.00",
        "example": "Python",
        "commodity_code": 123,
        "commodity_title": "Programming language",
        "hot_technology": "Y",
        "in_demand": "Y",
    }]
    tool_rows = [{
        "onetsoc_code": "15-1252.00",
        "example": "Git",
        "commodity_code": 456,
        "commodity_title": "Version control",
    }]

    tech_skills, tech_links = normalize_technology_skill_rows(tech_rows)
    tool_skills, tool_links = normalize_tool_rows(tool_rows)

    assert tech_skills[0]["external_skill_id"] == "technology_skills:123"
    assert tech_links[0]["technology_label_norm"] == "python"
    assert tool_skills[0]["external_skill_id"] == "tools_used:456"
    assert tool_links[0]["tool_label_norm"] == "git"
