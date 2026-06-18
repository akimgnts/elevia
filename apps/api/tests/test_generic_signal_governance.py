import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api.routes import matching
from api.schemas.matching import MatchingRequest
from api.utils.generic_skills_filter import (
    HARD_GENERIC_URIS,
    SOLO_BLOCK_GENERIC_URIS,
    WEAKLY_GENERIC_URIS,
    should_block_generic_only_overlap,
)


HARD_URI = sorted(HARD_GENERIC_URIS)[0]
WEAK_URI = "http://data.europa.eu/esco/skill/97bd1c21-66b2-4b7e-ad0f-e3cda590e378"
AGILE_URI = "http://data.europa.eu/esco/skill/0a9acb6b-1139-4be9-b431-3a80a959f2f4"
DOMAIN_URI = "http://example.test/skill/domain-a"


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


def test_solo_block_generic_uris_include_weak_data_and_agile():
    assert WEAK_URI in SOLO_BLOCK_GENERIC_URIS
    assert AGILE_URI in SOLO_BLOCK_GENERIC_URIS


def test_should_block_generic_only_overlap_blocks_uri_only_overlap():
    assert should_block_generic_only_overlap(
        matched_values=[WEAK_URI],
        scoring_unit="uri",
    ) is True


def test_should_block_generic_only_overlap_keeps_domain_plus_generic_overlap():
    assert should_block_generic_only_overlap(
        matched_values=[WEAK_URI, DOMAIN_URI],
        scoring_unit="uri",
    ) is False


def test_should_block_generic_only_overlap_blocks_noise_labels():
    assert should_block_generic_only_overlap(
        matched_values=["gestion", "suivi", "participation"],
        scoring_unit="string",
    ) is True


def test_should_block_generic_only_overlap_keeps_non_noise_string_match():
    assert should_block_generic_only_overlap(
        matched_values=["recruitment", "gestion"],
        scoring_unit="string",
    ) is False


def test_match_route_blocks_generic_only_overlap_when_flag_enabled(monkeypatch):
    class FakeEngine:
        def __init__(self, offers, context_coeffs=None):
            self.offers = offers

        def score_offer(self, profile, offer):
            return SimpleNamespace(
                offer_id=str(offer["id"]),
                score=100,
                breakdown={"skills": 1.0},
                reasons=["ok"],
                match_debug={
                    "skills": {
                        "matched": [WEAK_URI],
                        "missing": [],
                        "scoring_unit": "uri",
                        "intersection_count": 1,
                    }
                },
                score_is_partial=False,
            )

    monkeypatch.setenv("ELEVIA_BLOCK_GENERIC_ONLY_OVERLAP", "1")
    monkeypatch.setattr(matching, "_attach_offer_skills", lambda offers: None)
    monkeypatch.setattr(matching, "MatchingEngine", FakeEngine)
    monkeypatch.setattr(
        matching,
        "extract_profile",
        lambda profile: SimpleNamespace(
            profile_id="profile-1",
            skills_uri=[WEAK_URI, DOMAIN_URI, HARD_URI],
        ),
    )
    monkeypatch.setattr(matching, "compute_diagnostic", lambda profile, offer: _diagnostic())

    response = asyncio.run(
        matching.match_profile(
            MatchingRequest(
                profile={"skills_uri": [WEAK_URI, DOMAIN_URI, HARD_URI]},
                offers=[
                    {
                        "id": "offer-1",
                        "is_vie": True,
                        "skills_uri": [WEAK_URI],
                    }
                ],
            )
        )
    )

    assert response.results == []


def test_match_route_keeps_offer_when_generic_overlap_has_domain_anchor(monkeypatch):
    class FakeEngine:
        def __init__(self, offers, context_coeffs=None):
            self.offers = offers

        def score_offer(self, profile, offer):
            return SimpleNamespace(
                offer_id=str(offer["id"]),
                score=91,
                breakdown={"skills": 1.0},
                reasons=["ok"],
                match_debug={
                    "skills": {
                        "matched": [WEAK_URI, DOMAIN_URI],
                        "missing": [],
                        "scoring_unit": "uri",
                        "intersection_count": 2,
                    }
                },
                score_is_partial=False,
            )

    monkeypatch.setenv("ELEVIA_BLOCK_GENERIC_ONLY_OVERLAP", "1")
    monkeypatch.setattr(matching, "_attach_offer_skills", lambda offers: None)
    monkeypatch.setattr(matching, "MatchingEngine", FakeEngine)
    monkeypatch.setattr(
        matching,
        "extract_profile",
        lambda profile: SimpleNamespace(
            profile_id="profile-1",
            skills_uri=[WEAK_URI, DOMAIN_URI],
        ),
    )
    monkeypatch.setattr(matching, "compute_diagnostic", lambda profile, offer: _diagnostic())

    response = asyncio.run(
        matching.match_profile(
            MatchingRequest(
                profile={"skills_uri": [WEAK_URI, DOMAIN_URI]},
                offers=[
                    {
                        "id": "offer-1",
                        "is_vie": True,
                        "skills_uri": [WEAK_URI, DOMAIN_URI],
                    }
                ],
            )
        )
    )

    assert [item.offer_id for item in response.results] == ["offer-1"]
