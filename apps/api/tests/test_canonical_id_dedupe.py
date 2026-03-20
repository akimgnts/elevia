from api.routes.profile_file import _dedupe_canonical_skills_for_display


def test_alias_tool_duplicate():
    canonical_skills = [
        {"raw": "Power BI", "canonical_id": "skill:business_intelligence", "strategy": "tool_match"},
        {"raw": "Business Intelligence", "canonical_id": "skill:business_intelligence", "strategy": "synonym_match"},
    ]
    deduped, debug = _dedupe_canonical_skills_for_display(canonical_skills, [])
    assert len([m for m in deduped if m.get("canonical_id") == "skill:business_intelligence"]) == 1
    sources = {s["canonical_id"]: s["sources"] for s in debug.get("sources", [])}
    assert "skill:business_intelligence" in sources
    assert "tool_mapping" in sources["skill:business_intelligence"]
    assert "alias" in sources["skill:business_intelligence"]


def test_hierarchy_parent_debug():
    canonical_skills = [
        {"raw": "Business Intelligence", "canonical_id": "skill:business_intelligence", "strategy": "synonym_match"},
    ]
    deduped, debug = _dedupe_canonical_skills_for_display(canonical_skills, ["skill:data_analysis"])
    assert len([m for m in deduped if m.get("canonical_id") == "skill:business_intelligence"]) == 1
    parents = {p["canonical_id"] for p in debug.get("hierarchy_parents", [])}
    assert "skill:data_analysis" in parents


def test_triple_duplicate():
    canonical_skills = [
        {"raw": "Power BI", "canonical_id": "skill:business_intelligence", "strategy": "tool_match"},
        {"raw": "BI", "canonical_id": "skill:business_intelligence", "strategy": "synonym_match"},
        {"raw": "Business Intelligence", "canonical_id": "skill:business_intelligence", "strategy": "synonym_match"},
    ]
    deduped, _debug = _dedupe_canonical_skills_for_display(canonical_skills, [])
    assert len([m for m in deduped if m.get("canonical_id") == "skill:business_intelligence"]) == 1
