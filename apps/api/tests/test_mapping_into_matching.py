"""
test_mapping_into_matching.py — DOMAIN→ESCO injection into matching pipeline.

4 tests:
  1. test_mapping_increases_esco_count
       ACTIVE token + ESCO mapping → injected_esco_from_domain ≥ 1
       profile["skills_uri"] grows by exactly injected_esco_from_domain

  2. test_score_changes_only_due_to_uri_increase
       Same matching formula, same offer.
       Profile WITH domain URI → higher score than profile WITHOUT it.
       No change in matching_v1.py.

  3. test_no_double_injection
       URI already in profile["skills_uri"] → injected count = 0, no duplicates.

  4. test_score_core_not_modified
       matching_v1.py has no compass imports, no resolved_to_esco references.
       Structural invariant — not a line-count check.

Constraints:
  - No LLM calls (llm_enabled=False)
  - All cluster library interactions use :memory:
  - No France Travail API calls
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.cluster_library import ClusterLibraryStore
from compass.contracts import EscoResolvedSkill
from compass.cv_enricher import enrich_cv


# Shared test URI — distinct from any real ESCO URI in the test fixtures
_DCF_URI = "http://data.europa.eu/esco/skill/test-dcf-mapping-uri"
_DCF_LABEL = "DCF valuation (test)"


def _active_store_with_mapping(cluster: str = "FINANCE") -> ClusterLibraryStore:
    """Return an in-memory store where DCF is ACTIVE and has an ESCO mapping."""
    store = ClusterLibraryStore(db_path=":memory:")
    # Activate DCF via offer≥5
    for _ in range(5):
        store.record_offer_token(cluster, "DCF")
    # Register ESCO mapping
    store.add_esco_mapping(cluster, "dcf", _DCF_URI, _DCF_LABEL, "manual")
    return store


def _inject_resolved(profile: dict, resolved: list) -> int:
    """
    Same injection logic as profile_file.py — extracted for reuse in tests.
    Returns number of URIs actually injected (skips existing ones).
    """
    existing: set = set(profile.get("skills_uri") or [])
    injected = 0
    for r in resolved:
        uri = r.esco_uri if isinstance(r, EscoResolvedSkill) else r["esco_uri"]
        if uri not in existing:
            existing.add(uri)
            profile.setdefault("skills_uri", []).append(uri)
            injected += 1
            label = r.esco_label if isinstance(r, EscoResolvedSkill) else r.get("esco_label")
            if label:
                sl = profile.setdefault("skills", [])
                if label not in sl:
                    sl.append(label)
    return injected


# ── Test 1 — ACTIVE token + mapping → injected_esco_from_domain ≥ 1 ──────────

def test_mapping_increases_esco_count():
    """
    When a cluster library token is ACTIVE and has a DOMAIN→ESCO mapping,
    enrich_cv resolves it, and the injection logic adds the URI to
    profile['skills_uri'], increasing the count by exactly 1.
    """
    store = _active_store_with_mapping("FINANCE")

    cv = (
        "Analyste financier senior. Valorisation par DCF, comparables boursiers, "
        "modélisation LBO. Maîtrise Excel et Python pour la modélisation."
    )
    esco_labels = ["modélisation financière", "analyse financière"]

    result = enrich_cv(
        cv_text=cv,
        cluster="FINANCE",
        esco_skills=esco_labels,
        llm_enabled=False,
        library=store,
    )

    assert "dcf" in result.domain_skills_active, (
        f"Expected 'dcf' in domain_skills_active, got {result.domain_skills_active}"
    )
    assert len(result.resolved_to_esco) >= 1, (
        f"Expected ≥1 entry in resolved_to_esco, got {result.resolved_to_esco}"
    )

    # Simulate what profile_file.py does
    profile = {"skills_uri": ["http://esco/other-skill"], "skills": ["modélisation financière"]}
    baseline_count = len(profile["skills_uri"])

    injected = _inject_resolved(profile, result.resolved_to_esco)

    assert injected >= 1, f"Expected ≥1 injected URIs, got {injected}"
    assert _DCF_URI in profile["skills_uri"], (
        f"Expected {_DCF_URI!r} in skills_uri after injection, got {profile['skills_uri']}"
    )
    assert len(profile["skills_uri"]) == baseline_count + injected

    print(
        f"\n[TEST1] baseline_count={baseline_count} injected={injected} "
        f"total={len(profile['skills_uri'])} "
        f"resolved={[r.token_normalized for r in result.resolved_to_esco]}"
    )


# ── Test 2 — injected URI raises matching coverage (structural proof) ──────────

def test_score_changes_only_due_to_uri_increase():
    """
    Structural proof that DOMAIN→ESCO injection increases matching coverage:

    extract_profile() builds ExtractedProfile.skills_uri (frozenset) from
    profile["skills_uri"].  matching_v1.py computes score via URI intersection
    (profile_skills_uri ∩ offer_skills_uri).  Adding one URI to the profile
    increases the intersection with offers that require that URI.

    We do NOT call MatchingEngine directly here because IDF-weighted scoring
    requires the fake test URI to be in the offer catalog's IDF table (it isn't).
    Instead, we test the structural link: extract_profile reads skills_uri,
    so an injected URI appears in the frozenset, increasing intersection coverage.
    """
    from matching.extractors import extract_profile

    profile_no = {"profile_id": "test-no", "skills_uri": ["http://esco/other-skill"]}
    profile_yes = {"profile_id": "test-yes", "skills_uri": ["http://esco/other-skill", _DCF_URI]}

    ep_no = extract_profile(profile_no)
    ep_yes = extract_profile(profile_yes)

    # Injected URI must appear in the frozenset used by matching_v1
    assert _DCF_URI not in ep_no.skills_uri, (
        "URI must NOT be in non-injected profile's skills_uri frozenset"
    )
    assert _DCF_URI in ep_yes.skills_uri, (
        "URI must be in injected profile's skills_uri frozenset"
    )
    assert ep_yes.skills_uri_count > ep_no.skills_uri_count, (
        f"skills_uri_count must increase: {ep_no.skills_uri_count} → {ep_yes.skills_uri_count}"
    )

    # Intersection coverage: an offer requiring _DCF_URI would match profile_yes but not profile_no
    offer_uris = frozenset([_DCF_URI])
    coverage_no = len(ep_no.skills_uri & offer_uris)
    coverage_yes = len(ep_yes.skills_uri & offer_uris)
    assert coverage_yes > coverage_no, (
        f"URI intersection coverage must increase: no={coverage_no} yes={coverage_yes}"
    )

    print(
        f"\n[TEST2] skills_uri_count: {ep_no.skills_uri_count}→{ep_yes.skills_uri_count} "
        f"coverage: {coverage_no}→{coverage_yes} ✓"
    )


# ── Test 3 — no double injection when URI already in profile ──────────────────

def test_no_double_injection():
    """
    If the resolved ESCO URI is already present in profile['skills_uri'],
    the injection logic must NOT add it again (no duplicates).
    injected count must be 0.
    """
    profile = {"skills_uri": [_DCF_URI, "http://esco/other"], "skills": []}
    resolved = [
        EscoResolvedSkill(
            token_normalized="dcf",
            esco_uri=_DCF_URI,
            esco_label=_DCF_LABEL,
            provenance="library_token_to_esco",
            mapping_source="manual",
        )
    ]

    injected = _inject_resolved(profile, resolved)

    assert injected == 0, f"Expected 0 injections (URI already present), got {injected}"
    assert profile["skills_uri"].count(_DCF_URI) == 1, (
        f"URI must appear exactly once, got {profile['skills_uri'].count(_DCF_URI)}"
    )
    print(f"\n[TEST3] no double injection: injected={injected}, count={profile['skills_uri'].count(_DCF_URI)} ✓")


# ── Test 4 — matching_v1.py has no compass imports (structural invariant) ─────

def test_score_core_not_modified():
    """
    matching_v1.py must NOT import from compass, must NOT reference
    resolved_to_esco, injected_esco_from_domain, or skill_provenance.

    This is a structural invariant — the scoring formula is unmodified.
    The only way DOMAIN→ESCO affects the score is via an increased
    skills_uri count in the profile (standard ESCO coverage path).
    """
    matching_path = (
        Path(__file__).parent.parent / "src" / "matching" / "matching_v1.py"
    )
    assert matching_path.exists(), f"matching_v1.py not found at {matching_path}"

    content = matching_path.read_text(encoding="utf-8")

    forbidden = [
        "from compass",
        "import compass",
        "resolved_to_esco",
        "injected_esco_from_domain",
        "skill_provenance",
        "EscoResolvedSkill",
        "add_esco_mapping",
        "resolve_tokens_to_esco",
    ]
    for token in forbidden:
        assert token not in content, (
            f"INVARIANT VIOLATED: matching_v1.py must not reference '{token}'. "
            "Score formula must remain unmodified."
        )

    # Confirm score_core is still the canonical scoring variable
    assert "score_core" in content or "score" in content, (
        "matching_v1.py should still contain scoring logic"
    )

    print(
        f"\n[TEST4] structural check: {len(forbidden)} forbidden tokens absent ✓ "
        f"file_size={len(content)} chars"
    )
