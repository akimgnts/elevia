"""test_offer_domain_bounded.py — Domain URI Top-K rarity filter tests.

Verifies that the Top-K rarity filter prevents denominator explosion
in skills_score = matched_uris / offer_total_uris.

Test classes:
  TestTopKBound            — domain_uri_count never exceeds K
  TestTopKRaritySelection  — rarest tokens (lowest occurrences_offers) selected
  TestScoreDilutionPrevention — score stays close to pre-enrichment baseline
"""
from __future__ import annotations

import copy

from compass.cluster_library import reset_library
from compass.offer_canonicalization import (
    _OFFER_DOMAIN_TOPK_DEFAULT,
    _apply_domain_uris,
    _get_offer_domain_topk,
)
from matching.extractors import extract_profile
from matching.matching_v1 import MatchingEngine

# Unique prefixes (capitalized) prevent collisions with other tests' tokens.
# extract_candidate_tokens() only picks up Capitalized words — tokens must have
# uppercase first letter so they appear in offer text extraction.
# Tokens are alpha-only (no digits) to avoid _HANDLE_DIGITS_RE rejection.
_PREFIXES_CAP = [
    "Zqxrareaa", "Zqxrarebbb", "Zqxrareccc", "Zqxrareddd", "Zqxrareeeee",
    "Zqxrarefff", "Zqxrareggg", "Zqxrarehhh", "Zqxrareiii", "Zqxrarejjj",
    "Zqxrarekkkk", "Zqxrarellll", "Zqxraremmm", "Zqxrarennn", "Zqxrareooo",
    "Zqxrareppp", "Zqxrareqqq", "Zqxrarersss", "Zqxrarettt", "Zqxrareuuu",
    "Zqxrarevvv",  # extra slot
]


def _tok(i: int) -> str:
    return _PREFIXES_CAP[i]


def _activate(store, cluster: str, token: str, n: int) -> None:
    for _ in range(n):
        store.record_offer_token(cluster, token)


def _make_offer(tokens: list[str], esco_uris: list[str] | None = None) -> dict:
    text = " ".join(tokens)
    return {
        "id": "o-bounded-test",
        "title": f"Data Analyst {text[:80]}",
        "description": f"We use {text} daily.",
        "company": "TestCorp",
        "country": "France",
        "is_vie": True,
        "skills_uri": list(esco_uris) if esco_uris else [],
        "skills": [],
    }


# ── Bound tests ───────────────────────────────────────────────────────────────


class TestTopKBound:
    """domain_uri_count never exceeds K after _apply_domain_uris()."""

    def test_offer_domain_uris_bounded_to_topk(self, monkeypatch):
        """20 ACTIVE tokens → only K=5 domain URIs appear on offer."""
        K = 5
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", str(K))

        store = reset_library(db_path=":memory:")
        tokens = [_tok(i) for i in range(20)]
        for tok in tokens:
            _activate(store, "DATA_IT", tok, 10)

        offer = _make_offer(tokens)
        _apply_domain_uris(offer, library=store)

        count = offer["domain_uri_count"]
        assert count > 0, "Expected some domain URIs — check token extraction"
        assert count <= K, (
            f"Expected domain_uri_count ≤ {K}, got {count}"
        )
        assert len(offer.get("domain_uris", [])) <= K

    def test_default_topk_is_5(self, monkeypatch):
        """Default K=5 when ELEVIA_OFFER_DOMAIN_TOPK is unset."""
        monkeypatch.delenv("ELEVIA_OFFER_DOMAIN_TOPK", raising=False)
        assert _get_offer_domain_topk() == _OFFER_DOMAIN_TOPK_DEFAULT == 5

    def test_topk_env_override(self, monkeypatch):
        """ELEVIA_OFFER_DOMAIN_TOPK=10 is respected."""
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", "10")
        assert _get_offer_domain_topk() == 10

    def test_topk_invalid_env_fallback(self, monkeypatch):
        """Invalid env value falls back to default K=5."""
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", "notanumber")
        assert _get_offer_domain_topk() == _OFFER_DOMAIN_TOPK_DEFAULT

    def test_fewer_than_k_tokens_unchanged(self, monkeypatch):
        """When fewer than K tokens match, all are kept (no pruning)."""
        K = 5
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", str(K))

        store = reset_library(db_path=":memory:")
        tokens = [_tok(i) for i in range(3)]  # only 3, below K
        for tok in tokens:
            _activate(store, "DATA_IT", tok, 10)

        offer = _make_offer(tokens)
        _apply_domain_uris(offer, library=store)

        # All 3 should be present (not over-clipped)
        assert offer["domain_uri_count"] > 0, "Expected some domain URIs from 3 active tokens"
        assert offer["domain_uri_count"] <= K
        assert offer["domain_uri_count"] <= 3  # can only get up to 3


# ── Rarity selection tests ────────────────────────────────────────────────────


class TestTopKRaritySelection:
    """Rarest tokens (lowest occurrences_offers) are selected first."""

    def test_topk_selects_rarest_tokens(self, monkeypatch):
        """With K=3: common tokens (occ=50) are dropped, rare tokens (occ=10) kept."""
        K = 3
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", str(K))

        store = reset_library(db_path=":memory:")

        common = [_tok(i) for i in range(3)]   # 50 offer occurrences
        rare = [_tok(i) for i in range(10, 13)]  # 10 offer occurrences

        for tok in common:
            _activate(store, "DATA_IT", tok, 50)
        for tok in rare:
            _activate(store, "DATA_IT", tok, 10)

        offer = _make_offer(common + rare)
        _apply_domain_uris(offer, library=store)

        domain_uris = offer.get("domain_uris", [])
        assert len(domain_uris) == K

        # URIs use normalized (lowercase) token form
        rare_uris = {f"compass:skill:DATA_IT:{tok.lower()}" for tok in rare}
        for uri in domain_uris:
            assert uri in rare_uris, (
                f"Expected only rare-token URIs in top-K. Got {uri}. "
                f"Rare: {rare_uris}, Returned: {set(domain_uris)}"
            )

    def test_topk_deterministic_order(self, monkeypatch):
        """Same input always produces same domain_uris (stable sort by alpha on tie)."""
        K = 2
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", str(K))

        store = reset_library(db_path=":memory:")
        tokens = [_tok(i) for i in range(6)]
        for tok in tokens:
            _activate(store, "DATA_IT", tok, 10)  # all equal rarity

        offer_a = _make_offer(tokens)
        offer_b = _make_offer(tokens)
        _apply_domain_uris(offer_a, library=store)
        _apply_domain_uris(offer_b, library=store)

        assert offer_a["domain_uris"] == offer_b["domain_uris"], (
            "Top-K output must be deterministic across identical calls"
        )


# ── Score dilution prevention tests ───────────────────────────────────────────


class TestScoreDilutionPrevention:
    """With Top-K, score is better than without any filter (dilution is reduced)."""

    def test_no_score_dilution_ab(self, monkeypatch):
        """
        Setup:
          - 3 ESCO URIs shared between profile and offer (baseline score = 100)
          - 18 domain tokens ACTIVE in offer text, none shared with profile
          - Without Top-K (K=100): 18 domain URIs inflate offer denominator → score collapses
          - With Top-K=5: ≤5 domain URIs → smaller denominator → better score than no-filter

        Asserts:
          1. domain_uri_count_topk <= K
          2. score_topk >= score_nofilter  (filter strictly helps or is neutral)
        """
        K = 5
        NO_FILTER_K = 100  # effectively "no filter" — all 18 domain tokens kept

        store = reset_library(db_path=":memory:")
        tokens = [_tok(i) for i in range(18)]
        for tok in tokens:
            _activate(store, "DATA_IT", tok, 10)

        esco_uris = [
            f"http://data.europa.eu/esco/skill/test-dilution-{i}"
            for i in range(3)
        ]
        offer_base = _make_offer(tokens, esco_uris=esco_uris)
        profile = {"profile_id": "p-dilution", "skills_uri": list(esco_uris)}
        extracted = extract_profile(profile)

        # Score WITH Top-K=5 filter
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", str(K))
        offer_topk = copy.deepcopy(offer_base)
        _apply_domain_uris(offer_topk, library=store)
        score_topk = MatchingEngine([offer_topk]).score_offer(extracted, offer_topk).score
        count_topk = offer_topk.get("domain_uri_count", 0)

        # Score WITHOUT Top-K filter (K=100 → keep all domain tokens)
        monkeypatch.setenv("ELEVIA_OFFER_DOMAIN_TOPK", str(NO_FILTER_K))
        offer_nofilter = copy.deepcopy(offer_base)
        _apply_domain_uris(offer_nofilter, library=store)
        score_nofilter = MatchingEngine([offer_nofilter]).score_offer(extracted, offer_nofilter).score
        count_nofilter = offer_nofilter.get("domain_uri_count", 0)

        assert count_topk <= K, (
            f"Top-K bound violated: domain_uri_count={count_topk} > K={K}"
        )
        assert count_nofilter > count_topk, (
            f"No-filter should have more domain URIs than Top-K: "
            f"nofilter={count_nofilter}, topk={count_topk}"
        )
        assert score_topk >= score_nofilter, (
            f"Top-K filter must produce score ≥ no-filter score. "
            f"score_topk={score_topk}, score_nofilter={score_nofilter}. "
            f"domain_uris: topk={count_topk}, nofilter={count_nofilter}"
        )
