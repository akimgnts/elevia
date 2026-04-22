import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api.routes import matching
from api.schemas.matching import MatchingRequest
from api.utils.generic_skills_filter import HARD_GENERIC_URIS, WEAKLY_GENERIC_URIS


HARD_URI = sorted(HARD_GENERIC_URIS)[0]
WEAK_URI = sorted(WEAKLY_GENERIC_URIS)[0]
DOMAIN_A = "http://example.test/skill/domain-a"
DOMAIN_B = "http://example.test/skill/domain-b"


class FakeStatus:
    def __init__(self, value):
        self.value = value


def _criterion(status="OK"):
    return SimpleNamespace(status=FakeStatus(status), details=None, missing=[])


def _diagnostic(status="OK"):
    return SimpleNamespace(
        global_verdict=FakeStatus(status),
        top_blocking_reasons=[],
        hard_skills=_criterion(),
        soft_skills=_criterion(),
        languages=_criterion(),
        education=_criterion(),
        vie_eligibility=_criterion(status),
    )


def test_match_response_exposes_career_intelligence_additively(monkeypatch):
    class FakeEngine:
        def __init__(self, offers, context_coeffs=None):
            self.offers = offers

        def score_offer(self, profile, offer):
            return SimpleNamespace(
                offer_id=str(offer["id"]),
                score=81,
                breakdown={"skills": 1.0},
                reasons=["ok"],
                match_debug={"existing": True},
                score_is_partial=False,
            )

    monkeypatch.setattr(matching, "_attach_offer_skills", lambda offers: None)
    monkeypatch.setattr(matching, "MatchingEngine", FakeEngine)
    monkeypatch.setattr(
        matching,
        "extract_profile",
        lambda profile: SimpleNamespace(
            profile_id="profile-1",
            skills_uri=[DOMAIN_A, HARD_URI],
        ),
    )
    monkeypatch.setattr(matching, "compute_diagnostic", lambda profile, offer: _diagnostic())

    response = asyncio.run(
        matching.match_profile(
            MatchingRequest(
                profile={"skills_uri": [DOMAIN_A, HARD_URI]},
                offers=[
                    {
                        "id": "offer-1",
                        "is_vie": True,
                        "skills_uri": [DOMAIN_A, DOMAIN_B, WEAK_URI],
                    }
                ],
            )
        )
    )

    result = response.results[0]
    assert result.offer_id == "offer-1"
    assert result.score == 81
    assert result.match_debug == {"existing": True}
    assert result.career_intelligence == {
        "strengths": [DOMAIN_A],
        "gaps": [DOMAIN_B],
        "generic_ignored": {
            "profile": [HARD_URI],
            "offer": [WEAK_URI],
        },
        "positioning": "Profil partiellement aligné avec plusieurs gaps ciblés",
    }


def test_match_response_handles_empty_skills_without_error(monkeypatch):
    class FakeEngine:
        def __init__(self, offers, context_coeffs=None):
            self.offers = offers

        def score_offer(self, profile, offer):
            return SimpleNamespace(
                offer_id=str(offer["id"]),
                score=80,
                breakdown={"skills": 0.0},
                reasons=["ok"],
                match_debug=None,
                score_is_partial=False,
            )

    monkeypatch.setattr(matching, "_attach_offer_skills", lambda offers: None)
    monkeypatch.setattr(matching, "MatchingEngine", FakeEngine)
    monkeypatch.setattr(
        matching,
        "extract_profile",
        lambda profile: SimpleNamespace(profile_id="profile-1", skills_uri=[]),
    )
    monkeypatch.setattr(matching, "compute_diagnostic", lambda profile, offer: _diagnostic())

    response = asyncio.run(
        matching.match_profile(
            MatchingRequest(
                profile={"skills_uri": []},
                offers=[{"id": "offer-1", "is_vie": True, "skills_uri": []}],
            )
        )
    )

    assert response.results[0].career_intelligence is None
