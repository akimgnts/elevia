"""
test_matching_e2e_profile_created.py
====================================
Sprint Debug - Test E2E du moteur de matching avec profil créé en mémoire

Ce test prouve que le moteur peut:
1. Produire au moins 1 offre avec score > 15
2. Produire au moins 1 offre avec matched_skills non vide
3. Produire la reason "Aucune compétence détectée en commun" si intersection=0
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from matching import MatchingEngine
from matching.extractors import extract_profile
from matching.match_trace import trace_matching_batch

from fixtures.test_profile_v1 import TEST_PROFILE_V1, MOCK_OFFERS, get_test_profile, get_mock_offers


class TestMatchingE2EProfileCreated:
    """Tests E2E avec profil et offres créés en mémoire."""

    def test_profile_extraction_returns_skills(self):
        """Le profil test doit avoir des skills après extraction."""
        profile = extract_profile(TEST_PROFILE_V1)

        assert profile.profile_id == "test_profile_v1"
        assert len(profile.skills) >= 5, f"Expected >=5 skills, got {len(profile.skills)}"
        assert "python" in profile.skills
        assert "sql" in profile.skills

    def test_at_least_one_offer_scores_above_15(self):
        """Au moins 1 offre doit avoir score > 15."""
        engine = MatchingEngine(offers=MOCK_OFFERS)
        profile = extract_profile(TEST_PROFILE_V1)

        scores = []
        for offer in MOCK_OFFERS:
            result = engine.score_offer(profile, offer)
            scores.append(result.score)

        scores_above_15 = [s for s in scores if s > 15]
        assert len(scores_above_15) >= 1, f"No offer scored > 15. Scores: {scores}"

    def test_at_least_one_offer_has_matched_skills(self):
        """Au moins 1 offre doit avoir matched_skills non vide."""
        engine = MatchingEngine(offers=MOCK_OFFERS)
        profile = extract_profile(TEST_PROFILE_V1)

        offers_with_matches = []
        for offer in MOCK_OFFERS:
            result = engine.score_offer(profile, offer)
            match_debug = result.match_debug or {}
            skills_debug = match_debug.get("skills", {})
            matched = skills_debug.get("matched", [])
            if matched:
                offers_with_matches.append({
                    "offer_id": result.offer_id,
                    "matched_skills": matched,
                    "score": result.score,
                })

        assert len(offers_with_matches) >= 1, "No offer had matched_skills"
        print(f"\n[DEBUG] Offers with matched_skills: {offers_with_matches}")

    def test_zero_intersection_produces_correct_reason(self):
        """Si intersection=0, la reason doit contenir 'Aucune compétence détectée en commun'."""
        engine = MatchingEngine(offers=MOCK_OFFERS)
        profile = extract_profile(TEST_PROFILE_V1)

        # mock_offer_b has no skill intersection
        offer_b = next(o for o in MOCK_OFFERS if o["id"] == "mock_offer_b")
        result = engine.score_offer(profile, offer_b)

        # Check intersection is 0
        match_debug = result.match_debug or {}
        skills_debug = match_debug.get("skills", {})
        matched = skills_debug.get("matched", [])
        assert len(matched) == 0, f"Expected 0 matched skills, got {matched}"

        # Check reason
        reasons_str = " ".join(result.reasons)
        assert "Aucune compétence détectée en commun" in reasons_str, f"Expected reason not found. Reasons: {result.reasons}"

    def test_high_intersection_produces_high_score(self):
        """Offer C (4/4 skills match) doit avoir score >= 80."""
        engine = MatchingEngine(offers=MOCK_OFFERS)
        profile = extract_profile(TEST_PROFILE_V1)

        # mock_offer_c has 4 skills all matching
        offer_c = next(o for o in MOCK_OFFERS if o["id"] == "mock_offer_c")
        result = engine.score_offer(profile, offer_c)

        assert result.score >= 80, f"Expected score >= 80 for full match, got {result.score}"

        # Verify matched skills
        match_debug = result.match_debug or {}
        skills_debug = match_debug.get("skills", {})
        matched = skills_debug.get("matched", [])
        assert len(matched) == 4, f"Expected 4 matched skills, got {len(matched)}: {matched}"

    def test_trace_batch_returns_expected_stats(self):
        """Le trace batch doit retourner les stats attendues."""
        engine = MatchingEngine(offers=MOCK_OFFERS)
        result = trace_matching_batch(TEST_PROFILE_V1, MOCK_OFFERS, engine)

        stats = result["stats"]
        assert stats["total_offers"] == 3
        assert stats["traced_offers"] == 3
        assert stats["scores_above_15"] >= 1, f"Expected >=1 score > 15, got {stats['scores_above_15']}"
        assert stats["offers_with_matched_skills"] >= 1, f"Expected >=1 with matched_skills"

        # Print for debug
        print(f"\n[DEBUG] Stats: {stats}")
        print(f"[DEBUG] Profile: {result['profile_summary']}")


def test_quick_smoke():
    """Smoke test rapide pour CI."""
    engine = MatchingEngine(offers=MOCK_OFFERS)
    profile = extract_profile(TEST_PROFILE_V1)

    results = []
    for offer in MOCK_OFFERS:
        r = engine.score_offer(profile, offer)
        results.append((r.offer_id, r.score))

    print(f"\n[SMOKE] Results: {results}")
    assert any(score > 15 for _, score in results), "No score > 15"
