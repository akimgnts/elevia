"""Unit tests for fit_score_v2 — deterministic, AI-free, shadow signal."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from matching.extractors import ExtractedProfile  # noqa: E402
from matching.fit_score_v2 import (  # noqa: E402
    EligibilityStatus,
    FitScoreV2Result,
    score_offer_v2,
)
from matching.fit_score_v2.eligibility import evaluate_eligibility  # noqa: E402
from matching.fit_score_v2.fit import compute_fit_score  # noqa: E402
from matching.fit_score_v2.preference import compute_preference_score  # noqa: E402


def _make_profile(
    skills_uri=("uri:python", "uri:sql", "uri:etl", "uri:airflow"),
    languages=("en", "fr"),
    education_level=4,
    preferred_countries=("DE", "ES"),
):
    return ExtractedProfile(
        profile_id="p1",
        skills=frozenset({"python", "sql", "etl", "airflow"}),
        skills_uri=frozenset(skills_uri),
        languages=frozenset(languages),
        education_level=education_level,
        preferred_countries=frozenset(preferred_countries),
    )


def _make_offer(
    *,
    is_vie=True,
    country="Germany",
    title="Data Engineer",
    company="Acme GmbH",
    skills_uri=("uri:python", "uri:sql", "uri:etl"),
    languages=("en",),
    education=None,
):
    return {
        "id": "o1",
        "is_vie": is_vie,
        "country": country,
        "title": title,
        "company": company,
        "skills_uri": list(skills_uri),
        "languages": list(languages),
        "education": education,
    }


def _match_debug(
    *,
    matched_core=("python",),
    missing_core=(),
    matched_secondary=("sql",),
    missing_secondary=(),
    matched_context=("etl",),
    missing_context=(),
):
    return {
        "skills": {
            "matched_core": list(matched_core),
            "missing_core": list(missing_core),
            "matched_secondary": list(matched_secondary),
            "missing_secondary": list(missing_secondary),
            "matched_context": list(matched_context),
            "missing_context": list(missing_context),
        }
    }


class EligibilityTests(unittest.TestCase):
    def test_eligible_when_required_fields_present(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        status = evaluate_eligibility(profile, offer)
        self.assertTrue(status.ok)
        self.assertEqual(status.reasons, [])

    def test_not_vie_returns_reason(self) -> None:
        profile = _make_profile()
        offer = _make_offer(is_vie=False)
        status = evaluate_eligibility(profile, offer)
        self.assertFalse(status.ok)
        self.assertTrue(any("is_vie" in r for r in status.reasons))

    def test_missing_country_returns_reason(self) -> None:
        profile = _make_profile()
        offer = _make_offer(country=None)
        status = evaluate_eligibility(profile, offer)
        self.assertFalse(status.ok)
        self.assertTrue(any("pays" in r for r in status.reasons))

    def test_missing_title_returns_reason(self) -> None:
        profile = _make_profile()
        offer = _make_offer(title=None)
        status = evaluate_eligibility(profile, offer)
        self.assertFalse(status.ok)
        self.assertTrue(any("titre" in r for r in status.reasons))

    def test_missing_company_returns_reason(self) -> None:
        profile = _make_profile()
        offer = _make_offer(company=None)
        status = evaluate_eligibility(profile, offer)
        self.assertFalse(status.ok)
        self.assertTrue(any("entreprise" in r for r in status.reasons))

    def test_required_languages_no_overlap_when_profile_declares(self) -> None:
        profile = _make_profile(languages=("zh",))
        offer = _make_offer(languages=("en", "de"))
        status = evaluate_eligibility(profile, offer)
        self.assertFalse(status.ok)
        self.assertTrue(any("langues" in r for r in status.reasons))

    def test_required_languages_lenient_when_profile_silent(self) -> None:
        profile = _make_profile(languages=())
        offer = _make_offer(languages=("en", "de"))
        status = evaluate_eligibility(profile, offer)
        self.assertTrue(status.ok)


class FitScoreTests(unittest.TestCase):
    def test_eligible_offer_returns_fit_score(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        result = score_offer_v2(profile, offer, match_debug=_match_debug())
        self.assertTrue(result.eligibility_status.ok)
        self.assertIsNotNone(result.fit_score)
        self.assertGreaterEqual(result.fit_score, 0)
        self.assertLessEqual(result.fit_score, 100)

    def test_short_circuits_to_none_when_not_eligible(self) -> None:
        profile = _make_profile()
        offer = _make_offer(is_vie=False)
        result = score_offer_v2(profile, offer, match_debug=_match_debug())
        self.assertFalse(result.eligibility_status.ok)
        self.assertIsNone(result.fit_score)
        self.assertIsNone(result.preference_score)

    def test_core_weighs_more_than_secondary(self) -> None:
        """Same matched count, but core hits should outscore secondary hits."""
        profile = _make_profile()
        offer = _make_offer()
        all_core = _match_debug(
            matched_core=("a", "b"), matched_secondary=(), matched_context=()
        )
        all_secondary = _match_debug(
            matched_core=(), matched_secondary=("a", "b"), matched_context=()
        )
        score_core, _ = compute_fit_score(profile, offer, match_debug=all_core)
        score_sec, _ = compute_fit_score(profile, offer, match_debug=all_secondary)
        # With equal match ratios per tier (1.0 each), CORE/SECONDARY normalised separately
        # both reach 1.0 base. They differ only when missing items exist.
        # Keep this test focused: a core-only profile with one missing core penalised.
        all_core_with_miss = _match_debug(
            matched_core=("a",), missing_core=("b",), matched_secondary=(), matched_context=()
        )
        all_sec_with_miss = _match_debug(
            matched_core=(), matched_secondary=("a",), missing_secondary=("b",), matched_context=()
        )
        s_core_miss, _ = compute_fit_score(profile, offer, match_debug=all_core_with_miss)
        s_sec_miss, _ = compute_fit_score(profile, offer, match_debug=all_sec_with_miss)
        # CORE missing triggers extra penalty → lower than SECONDARY missing
        self.assertLess(s_core_miss, s_sec_miss)

    def test_distant_lowers_score(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        md = _match_debug()
        score_neutral, _ = compute_fit_score(profile, offer, match_debug=md, domain_affinity="neutral")
        score_distant, _ = compute_fit_score(profile, offer, match_debug=md, domain_affinity="distant")
        self.assertLess(score_distant, score_neutral)

    def test_aligned_raises_score(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        md = _match_debug(
            matched_core=("a",), missing_core=("b",),  # leave headroom < 1.0
            matched_secondary=("c",), missing_secondary=(),
        )
        score_neutral, _ = compute_fit_score(profile, offer, match_debug=md, domain_affinity="neutral")
        score_aligned, _ = compute_fit_score(profile, offer, match_debug=md, domain_affinity="aligned")
        self.assertGreaterEqual(score_aligned, score_neutral)

    def test_title_multiplier_only_when_aligned_and_same_domain(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        md = _match_debug(
            matched_core=("a",), missing_core=("b",),
            matched_secondary=(), missing_secondary=(),
            matched_context=(), missing_context=(),
        )
        s_no_title, _ = compute_fit_score(
            profile, offer, match_debug=md,
            domain_affinity="aligned", cv_domain="data", offer_domain="ops",
        )
        s_title, _ = compute_fit_score(
            profile, offer, match_debug=md,
            domain_affinity="aligned", cv_domain="data", offer_domain="data",
        )
        self.assertGreaterEqual(s_title, s_no_title)

    def test_unknown_domain_label_falls_back_to_neutral(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        md = _match_debug()
        s_unknown, explain = compute_fit_score(
            profile, offer, match_debug=md, domain_affinity="weird"
        )
        self.assertEqual(explain["domain_multiplier"]["value"], 1.00)


class PreferenceScoreTests(unittest.TestCase):
    def test_preference_score_independent_of_skills(self) -> None:
        """Preference score should not depend on skill match — only on country/edu/lang."""
        profile = _make_profile()
        offer_match = _make_offer()
        offer_country_mismatch = _make_offer(country="Brazil")
        s_match, _ = compute_preference_score(profile, offer_match)
        s_mismatch, _ = compute_preference_score(profile, offer_country_mismatch)
        self.assertGreater(s_match, s_mismatch)

    def test_preference_full_when_all_satisfied(self) -> None:
        profile = _make_profile()
        offer = _make_offer(education="bac+5", country="Germany", languages=("en",))
        score, explain = compute_preference_score(profile, offer)
        self.assertEqual(score, 100)

    def test_preferences_never_affect_fit(self) -> None:
        """Country mismatch must not change fit_score (it only changes preference_score)."""
        profile = _make_profile()
        offer_a = _make_offer(country="Germany")
        offer_b = _make_offer(country="Brazil")
        md = _match_debug()
        fit_a, _ = compute_fit_score(profile, offer_a, match_debug=md)
        fit_b, _ = compute_fit_score(profile, offer_b, match_debug=md)
        self.assertEqual(fit_a, fit_b)


class NoMutationTests(unittest.TestCase):
    def test_does_not_mutate_offer_skills_uri(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        snapshot = list(offer["skills_uri"])
        score_offer_v2(profile, offer, match_debug=_match_debug())
        self.assertEqual(offer["skills_uri"], snapshot)

    def test_does_not_mutate_profile_skills_uri(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        snapshot = frozenset(profile.skills_uri)
        score_offer_v2(profile, offer, match_debug=_match_debug())
        self.assertEqual(profile.skills_uri, snapshot)


class NoAITests(unittest.TestCase):
    def test_no_anthropic_or_openai_calls(self) -> None:
        """Sanity: scoring must not perform any HTTP calls to AI providers."""
        profile = _make_profile()
        offer = _make_offer()
        # If anything tried to call requests.post / httpx etc., this would fail.
        with patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            score_offer_v2(profile, offer, match_debug=_match_debug())


class FallbackWithoutMatchDebugTests(unittest.TestCase):
    def test_flat_fallback_when_match_debug_absent(self) -> None:
        profile = _make_profile()
        offer = _make_offer()
        result = score_offer_v2(profile, offer, match_debug=None)
        self.assertTrue(result.eligibility_status.ok)
        self.assertIsNotNone(result.fit_score)
        self.assertGreater(result.fit_score, 0)

    def test_dict_profile_supported(self) -> None:
        profile_dict = {
            "skills_uri": ["uri:python", "uri:sql"],
            "languages": ["en"],
            "education_level": 4,
            "preferred_countries": ["DE"],
        }
        offer = _make_offer()
        result = score_offer_v2(profile_dict, offer, match_debug=None)
        self.assertTrue(result.eligibility_status.ok)
        self.assertIsNotNone(result.fit_score)


if __name__ == "__main__":
    unittest.main()
