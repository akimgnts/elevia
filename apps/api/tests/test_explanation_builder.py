from compass.explainability.explanation_builder import build_offer_explanation
from matching.explanation_builder import build_explanation


def test_offer_explanation_builder_returns_front_ready_payload():
    match_debug = {
        "skills": {
            "matched_core": ["sql", "power bi"],
            "missing_core": ["erp systems"],
            "matched_secondary": ["data analysis"],
            "missing_secondary": ["financial reporting"],
        }
    }

    result = build_offer_explanation(match_debug, score=72, confidence="HIGH")

    assert result["score"] == 72
    assert result["fit_label"] == "Good fit"
    assert result["strengths"] == ["SQL", "Power BI", "Data analysis"]
    assert result["gaps"][:2] == ["ERP systems", "Financial reporting"]
    assert result["blockers"] == ["ERP systems"]
    assert "SQL" in result["summary_reason"]
    assert "ERP systems" in result["summary_reason"]


def test_offer_explanation_builder_is_deterministic_and_hides_internal_noise():
    match_debug = {
        "skills": {
            "matched_core": ["skill:sql", "both", "query", "python"],
            "missing_core": ["https://example.com/skill/x", "business intelligence", "contribute", "ifrs", "ability"],
        }
    }

    r1 = build_offer_explanation(match_debug, score=48, confidence="MED")
    r2 = build_offer_explanation(match_debug, score=48, confidence="MED")

    assert r1 == r2
    assert r1["strengths"] == ["Python"]
    assert r1["gaps"] == ["Business intelligence", "IFRS"]
    assert all("skill:" not in item.lower() for item in r1["strengths"] + r1["gaps"])


def test_legacy_explanation_builder_remains_compatible():
    match_debug = {
        "skills": {
            "matched_core": ["data analysis"],
            "missing_core": ["business intelligence"],
            "matched_secondary": [],
        }
    }

    result = build_explanation(match_debug, score=50, confidence="MED")

    assert result["fit_score"] == 50
    assert result["why_match"] == ["Data analysis"]
    assert result["main_blockers"] == ["Business intelligence"]
    assert result["distance"] == "Partial fit"
    assert "Business intelligence" in result["next_move"]
