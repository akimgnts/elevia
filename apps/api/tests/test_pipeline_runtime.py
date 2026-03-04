"""
test_pipeline_runtime.py — Factual verification of Compass E pipeline wiring.

7 tests + 1 E2E:
  1. test_compass_e_on_sets_pipeline_tag
       ELEVIA_ENABLE_COMPASS_E=1 → pipeline_variant == "canonical_compass_with_compass_e"
  2. test_compass_e_off_uses_baseline
       ELEVIA_ENABLE_COMPASS_E=0 → pipeline_variant == "canonical_compass_baseline"
  3. test_llm_fires_for_sparse_cv
       Sparse ESCO → llm_triggered=True (mocked, no real OpenAI call)
  4. test_llm_does_not_fire_for_rich_cv
       Dense ESCO (count≥threshold + density≥0.02) → llm_triggered=False
  5. test_classify_tools_domain_pending
       opc/opcvm/tableau/… → DOMAIN_PENDING
  6. test_classify_noise_rejected
       akim/gmail/paris/after/… → REJECT_*
  7. test_classify_opcvm_with_punctuation
       "opcvm," → DOMAIN_PENDING after normalization
  E2E. test_opc_opcvm_go_to_pending_not_rejected
       CV with OPC/OPCVM → in domain_skills_pending, absent from rejected_tokens

Constraints:
  - No real LLM calls (mock for test 3)
  - No France Travail API calls
  - Score invariance maintained (no score_core changes)
  - All use in-memory SQLite for cluster library
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Shared CV fixtures ─────────────────────────────────────────────────────────

_FINANCE_CV = (
    "Juriste droit financier OPCVM OPC conformité réglementaire AMF "
    "reporting IFRS controlling budget audit interne gestion collective fonds"
)

_RICH_TECH_CV = (
    "Python SQL machine learning data analysis ETL statistics Docker "
    "Kubernetes data pipeline analytics neural network deep learning "
) * 3  # high token count → high density

# Fake LLM suggestion that will cause llm_triggered=True (content doesn't matter)
_LLM_MOCK_RETURN = [{"token": "FakeSkill", "evidence": "mocked for test"}]


# ── HTTP client fixture ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _post_txt(client, text: str, filename: str = "cv.txt"):
    return client.post(
        "/profile/parse-file",
        files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


# ── Test 1 — COMPASS_E ON → pipeline_used contains "compass_e" ────────────────

def test_compass_e_on_sets_pipeline_tag(client):
    """
    POST /profile/parse-file with ELEVIA_ENABLE_COMPASS_E=1 must return a
    response whose pipeline_variant field contains 'compass_e'.
    """
    with patch.dict("os.environ", {"ELEVIA_ENABLE_COMPASS_E": "1"}):
        resp = _post_txt(client, _FINANCE_CV)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()

    assert body["pipeline_used"] == "canonical_compass", (
        f"Expected pipeline_used='canonical_compass', got {body['pipeline_used']!r}"
    )
    assert body.get("pipeline_variant") == "canonical_compass_with_compass_e", (
        f"Expected pipeline_variant='canonical_compass_with_compass_e', got {body.get('pipeline_variant')!r}"
    )
    assert body["compass_e_enabled"] is True, (
        f"Expected compass_e_enabled=True in response, got {body['compass_e_enabled']}"
    )
    # Observability report
    print(
        f"\n[TEST1] pipeline_used={body['pipeline_used']} "
        f"pipeline_variant={body.get('pipeline_variant')} "
        f"llm_fired={body.get('llm_fired')} "
        f"esco_count={body.get('canonical_count')} "
        f"domain_active={len(body.get('domain_skills_active', []))} "
        f"domain_pending={body.get('domain_skills_pending_count', 0)}"
    )


# ── Test 2 — COMPASS_E OFF → pipeline_used == "baseline" ──────────────────────

def test_compass_e_off_uses_baseline(client):
    """
    POST /profile/parse-file with ELEVIA_ENABLE_COMPASS_E=0 (default) must
    return pipeline_variant == "baseline" exactly.
    """
    with patch.dict("os.environ", {"ELEVIA_ENABLE_COMPASS_E": "0"}):
        resp = _post_txt(client, _FINANCE_CV)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()

    assert body["pipeline_used"] == "canonical_compass", (
        f"Expected pipeline_used='canonical_compass' when COMPASS_E=0, got {body['pipeline_used']!r}"
    )
    assert body.get("pipeline_variant") == "canonical_compass_baseline", (
        f"Expected pipeline_variant='canonical_compass_baseline' when COMPASS_E=0, got {body.get('pipeline_variant')!r}"
    )
    assert body["compass_e_enabled"] is False, (
        f"Expected compass_e_enabled=False, got {body['compass_e_enabled']}"
    )
    print(
        f"\n[TEST2] pipeline_used={body['pipeline_used']} "
        f"pipeline_variant={body.get('pipeline_variant')} "
        f"compass_e_enabled={body['compass_e_enabled']}"
    )


# ── Test 3 — LLM fires for sparse CV ──────────────────────────────────────────

def test_llm_fires_for_sparse_cv():
    """
    When ESCO skill count is below the cluster threshold, enrich_cv() must
    set llm_triggered=True.  The LLM call is mocked — no real OpenAI request.
    """
    from compass.cv_enricher import enrich_cv
    from compass.cluster_library import ClusterLibraryStore

    store = ClusterLibraryStore(db_path=":memory:")
    sparse_cv = "Juriste OPC OPCVM AMF conformité"  # few words, 0 ESCO hits

    with patch("compass.llm_enricher.call_llm_for_skills", return_value=_LLM_MOCK_RETURN):
        result = enrich_cv(
            cv_text=sparse_cv,
            cluster="FINANCE",
            esco_skills=[],  # 0 skills → esco_count < threshold=2 → triggers LLM
            llm_enabled=True,
            library=store,
        )

    assert result.llm_triggered is True, (
        f"Expected llm_triggered=True for sparse CV (0 ESCO skills), got False.\n"
        f"domain_pending={result.domain_skills_pending}, rejected={result.rejected_tokens}"
    )
    print(
        f"\n[TEST3] llm_triggered={result.llm_triggered} "
        f"domain_pending={result.domain_skills_pending}"
    )


# ── Test 4 — LLM does NOT fire for rich CV ────────────────────────────────────

def test_llm_does_not_fire_for_rich_cv():
    """
    When ESCO skill count ≥ threshold AND skill density ≥ 2%, the LLM must
    NOT be triggered (no mock patch needed — should short-circuit).
    """
    from compass.cv_enricher import enrich_cv
    from compass.cluster_library import ClusterLibraryStore

    store = ClusterLibraryStore(db_path=":memory:")
    # 6 validated ESCO skills + a long dense CV → count≥3 AND density≥0.02
    rich_esco = [
        "Python (programmation informatique)", "SQL", "machine learning",
        "data analysis", "ETL", "statistiques",
    ]

    result = enrich_cv(
        cv_text=_RICH_TECH_CV,
        cluster="DATA_IT",
        esco_skills=rich_esco,
        llm_enabled=True,
        library=store,
    )

    assert result.llm_triggered is False, (
        f"Expected llm_triggered=False for rich CV ({len(rich_esco)} ESCO skills), "
        f"got True. This indicates the threshold check is misconfigured."
    )
    print(f"\n[TEST4] llm_triggered={result.llm_triggered} (correctly suppressed)")


# ── Test 5 — classify_token: tools → DOMAIN_PENDING ──────────────────────────

def test_classify_tools_domain_pending():
    """
    Spec-mandated tools must always be classified as DOMAIN_PENDING,
    even in lowercase and regardless of name-heuristic rules.
    """
    from compass.cluster_library import classify_token

    tools = ["opc", "opcvm", "tableau", "dashboards", "forecasting", "analytics", "api", "crm", "kpi"]
    for token in tools:
        decision, reason_code = classify_token(token)
        assert decision == "DOMAIN_PENDING", (
            f"FAIL: classify_token({token!r}) → ({decision!r}, {reason_code!r}). "
            f"Expected DOMAIN_PENDING."
        )
    print(f"\n[TEST5] All {len(tools)} tools → DOMAIN_PENDING ✓")


# ── Test 6 — classify_token: noise → REJECT_* ────────────────────────────────

def test_classify_noise_rejected():
    """
    Personal names, email tokens, city names, and generic English words
    must all be classified as REJECT with a REJECT_* reason code.
    """
    from compass.cluster_library import classify_token

    noise = [
        ("akim",     "REJECT_NAME_HANDLE"),
        ("gmail",    "REJECT_EMAIL"),
        ("paris",    "REJECT_NAME_HANDLE"),
        ("after",    "REJECT_GENERIC"),
        ("across",   "REJECT_GENERIC"),
        ("@foo",     "REJECT_EMAIL"),
        ("https://x.y", "REJECT_URL"),
    ]
    for token, expected_code in noise:
        decision, reason_code = classify_token(token)
        assert decision == "REJECT", (
            f"FAIL: classify_token({token!r}) → ({decision!r}, {reason_code!r}). "
            f"Expected REJECT."
        )
        assert reason_code == expected_code, (
            f"FAIL: classify_token({token!r}) reason_code={reason_code!r}, "
            f"expected {expected_code!r}."
        )
    print(f"\n[TEST6] All {len(noise)} noise tokens → REJECT_* ✓")


# ── Test 7 — classify_token: "opcvm," with trailing punct → DOMAIN_PENDING ───

def test_classify_opcvm_with_punctuation():
    """
    Tokens extracted from raw CV text often carry trailing punctuation.
    classify_token must strip it before evaluation.
    """
    from compass.cluster_library import classify_token

    punctuated = ["opcvm,", "tableau.", "opc;", "dashboards)"]
    for token in punctuated:
        decision, reason_code = classify_token(token)
        assert decision == "DOMAIN_PENDING", (
            f"FAIL: classify_token({token!r}) → ({decision!r}, {reason_code!r}). "
            f"Expected DOMAIN_PENDING after stripping punct."
        )
    print(f"\n[TEST7] All punctuated tokens normalised → DOMAIN_PENDING ✓")


# ── E2E — OPC/OPCVM in domain_pending, absent from rejected_tokens ────────────

def test_opc_opcvm_go_to_pending_not_rejected():
    """
    A CV mentioning OPC/OPCVM (finance domain) must:
    - route through pipeline_used containing "compass_e"
    - have opc / opcvm in domain_skills_pending (not rejected)
    - have NO mention of opc/opcvm in rejected_tokens
    """
    from compass.cv_enricher import enrich_cv
    from compass.cluster_library import ClusterLibraryStore, reset_library
    from compass.canonical_pipeline import run_cv_pipeline

    store = ClusterLibraryStore(db_path=":memory:")

    cv = (
        "Juriste droit financier OPCVM OPC conformité réglementaire AMF "
        "reporting IFRS controlling budget audit interne gestion collective fonds"
    )
    esco_skills = ["audit interne", "analyse financière", "conformité réglementaire"]

    # Direct enrichment call (exposes domain_skills_pending + rejected_tokens)
    result = enrich_cv(
        cv_text=cv,
        cluster="FINANCE_LEGAL",
        esco_skills=esco_skills,
        llm_enabled=False,
        library=store,
    )

    pending_norms = set(result.domain_skills_pending)
    rejected_norms = {r["token_norm"] for r in result.rejected_tokens}

    assert "opc" in pending_norms or "opcvm" in pending_norms, (
        f"FAIL: opc/opcvm should be in domain_skills_pending.\n"
        f"  domain_skills_pending = {sorted(pending_norms)}\n"
        f"  rejected_tokens = {[(r['token_norm'], r['reason_code']) for r in result.rejected_tokens]}"
    )

    for bad in ("opc", "opcvm"):
        assert bad not in rejected_norms, (
            f"FAIL: '{bad}' should NOT be in rejected_tokens but found: "
            f"{[(r['token_norm'], r['reason_code']) for r in result.rejected_tokens if r['token_norm'] == bad]}"
        )

    # Pipeline-level check via canonical pipeline
    result_pipe = run_cv_pipeline(cv, profile_id="test-opc-e2e", compass_e_override=True)
    assert "compass_e" in result_pipe.pipeline_used, (
        f"Expected pipeline_used to contain 'compass_e', got {result_pipe.pipeline_used!r}"
    )

    print(
        f"\n[E2E] pipeline_used={result_pipe.pipeline_used} "
        f"cluster={result_pipe.profile_cluster.get('dominant_cluster')} "
        f"domain_pending={sorted(pending_norms)} "
        f"rejected_count={len(result.rejected_tokens)}"
    )
