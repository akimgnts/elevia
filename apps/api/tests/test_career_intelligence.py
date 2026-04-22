import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api.routes import dev_tools
from api.routes.dev_tools import MetricsRequest
from api.utils.career_intelligence import build_career_intelligence
from api.utils.generic_skills_filter import HARD_GENERIC_URIS, WEAKLY_GENERIC_URIS


HARD_URI = sorted(HARD_GENERIC_URIS)[0]
WEAK_URI = sorted(WEAKLY_GENERIC_URIS)[0]
DOMAIN_A = "http://example.test/skill/domain-a"
DOMAIN_B = "http://example.test/skill/domain-b"
DOMAIN_C = "http://example.test/skill/domain-c"


def test_career_intelligence_mixed_domain_strengths_gaps_and_generics():
    result = build_career_intelligence(
        profile_skills_uri=[DOMAIN_A, DOMAIN_C, HARD_URI],
        offer_skills_uri=[DOMAIN_A, DOMAIN_B, WEAK_URI],
    )

    assert result == {
        "strengths": [DOMAIN_A],
        "gaps": [DOMAIN_B],
        "generic_ignored": {
            "profile": [HARD_URI],
            "offer": [WEAK_URI],
        },
        "positioning": "Profil partiellement aligné avec plusieurs gaps ciblés",
    }


def test_career_intelligence_without_domain_match_keeps_gaps():
    result = build_career_intelligence(
        profile_skills_uri=[DOMAIN_C],
        offer_skills_uri=[DOMAIN_A, DOMAIN_B],
    )

    assert result["strengths"] == []
    assert result["gaps"] == [DOMAIN_A, DOMAIN_B]
    assert result["positioning"] == "Profil encore éloigné du noyau métier"


def test_career_intelligence_generic_overlap_is_not_a_strength():
    result = build_career_intelligence(
        profile_skills_uri=[HARD_URI, WEAK_URI],
        offer_skills_uri=[HARD_URI, WEAK_URI, DOMAIN_A],
    )

    assert result == {
        "strengths": [],
        "gaps": [DOMAIN_A],
        "generic_ignored": {
            "profile": [HARD_URI, WEAK_URI],
            "offer": [HARD_URI, WEAK_URI],
        },
        "positioning": "Profil encore éloigné du noyau métier",
    }


def test_dev_metrics_exposes_career_intelligence_additively(monkeypatch):
    class FakeEngine:
        def __init__(self, offers):
            self.offers = offers

        def score_offer(self, profile, offer):
            return SimpleNamespace(score=42)

    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    monkeypatch.setattr(
        dev_tools,
        "extract_profile",
        lambda profile: SimpleNamespace(skills_uri=[DOMAIN_A, HARD_URI]),
    )
    monkeypatch.setattr(
        dev_tools,
        "load_catalog_offers",
        lambda: [
            {
                "id": "offer-1",
                "skills_uri": [DOMAIN_A, DOMAIN_B, WEAK_URI],
                "skills_unmapped": [],
            }
        ],
    )
    monkeypatch.setattr(dev_tools, "MatchingEngine", FakeEngine)
    monkeypatch.setattr(dev_tools, "compute_semantic_for_offer", lambda profile_id, offer: {})

    result = asyncio.run(
        dev_tools.dev_metrics(
            MetricsRequest(
                profile_id="profile-1",
                profile={"skills_uri": [DOMAIN_A, HARD_URI]},
                limit=1,
            )
        )
    )

    for existing_key in [
        "average_unmapped_tokens_per_offer",
        "top_20_unmapped_tokens",
        "distribution_score_A",
        "correlation_score_A_vs_score_B",
        "semantic_sample_size",
        "skill_tag_observability",
    ]:
        assert existing_key in result

    assert result["career_intelligence"] == {
        "strengths": [DOMAIN_A],
        "gaps": [DOMAIN_B],
        "generic_ignored": {
            "profile": [HARD_URI],
            "offer": [WEAK_URI],
        },
        "positioning": "Profil partiellement aligné avec plusieurs gaps ciblés",
    }
