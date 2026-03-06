"""
test_analyze_recovery_button.py — Static analysis verifying that AnalyzePage.tsx
correctly wires the AI skill recovery feature.

These tests mirror the pattern of test_analyze_parse_request.py:
they read the source file and assert structural invariants without running JS.

Asserts:
  1. fetchRecoverSkills is imported from api
  2. recoveredSkills state and handleRecover function exist
  3. "Récupérer des compétences (IA)" button exists and is isDev-gated
  4. Recovered skills render with "IA" tag and display-only disclaimer
  5. Endpoint call sends cluster + ignored_tokens + validated_esco_labels
  6. Recovered skills are never pushed to skills_uri (score-invariance guarantee)
"""
from __future__ import annotations

from pathlib import Path

ANALYZE_PAGE = Path("apps/web/src/pages/AnalyzePage.tsx").read_text(encoding="utf-8")
API_TS = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


# ── Test 1: fetchRecoverSkills is imported ────────────────────────────────────

def test_fetch_recover_skills_imported():
    assert "fetchRecoverSkills" in ANALYZE_PAGE, (
        "AnalyzePage must import fetchRecoverSkills from api"
    )
    assert "fetchRecoverSkills" in API_TS, (
        "api.ts must export fetchRecoverSkills"
    )


# ── Test 2: state + handler wired ─────────────────────────────────────────────

def test_recovered_skills_state_and_handler_exist():
    assert "recoveredSkills" in ANALYZE_PAGE, (
        "AnalyzePage must declare recoveredSkills state"
    )
    assert "recoveringSkills" in ANALYZE_PAGE, (
        "AnalyzePage must declare recoveringSkills loading state"
    )
    assert "handleRecover" in ANALYZE_PAGE, (
        "AnalyzePage must declare handleRecover async function"
    )
    assert "setRecoveredSkills" in ANALYZE_PAGE, (
        "AnalyzePage must call setRecoveredSkills with response results"
    )


# ── Test 3: button is isDev-gated ─────────────────────────────────────────────

def test_recovery_button_is_dev_gated():
    source = ANALYZE_PAGE
    # Button text must exist
    assert "Récupérer des compétences (IA)" in source, (
        "Recovery button label 'Récupérer des compétences (IA)' must exist in AnalyzePage"
    )
    # Must be inside a block that checks isDev
    idx_button = source.find("Récupérer des compétences (IA)")
    # Search backwards for isDev in the 800 chars preceding the button
    # (className strings are long so we need a wider window)
    context_before = source[max(0, idx_button - 800): idx_button]
    assert "isDev" in context_before, (
        "Recovery button must be rendered inside an isDev-gated block"
    )
    # Button must be disabled when recoveringSkills (and may include cache gating)
    assert "disabled={recoveringSkills" in source, (
        "Recovery button must be disabled when recoveringSkills is true"
    )


def test_recovery_button_cache_label_present():
    source = ANALYZE_PAGE
    assert "Déjà récupéré" in source, (
        "Recovery button should display 'Déjà récupéré' when cache is hit"
    )


def test_ai_audit_button_is_dev_gated():
    source = ANALYZE_PAGE
    assert "Audit qualité IA" in source, (
        "AnalyzePage must render the 'Audit qualité IA' button"
    )
    idx_button = source.find("Audit qualité IA")
    context_before = source[max(0, idx_button - 800): idx_button]
    assert "isDev" in context_before, (
        "Audit quality button must be rendered inside an isDev-gated block"
    )


# ── Test 4: "IA" tag rendered + display-only disclaimer ───────────────────────

def test_recovered_skills_render_with_ia_tag_and_disclaimer():
    source = ANALYZE_PAGE
    assert "IA" in source, "Recovered skill pills must display an 'IA' tag"
    # Disclaimer must be present
    assert "non injectées" in source or "display-only" in source or "affichage uniquement" in source, (
        "A display-only disclaimer must appear near recovered skills to prevent confusion"
    )
    # The recovered pills section should reference recoveredSkills
    assert "recoveredSkills.map" in source, (
        "AnalyzePage must render recoveredSkills list with .map()"
    )


# ── Test 5: endpoint payload includes required fields ────────────────────────

def test_endpoint_call_sends_required_fields():
    source = ANALYZE_PAGE
    # cluster field
    assert "cluster" in source, "fetchRecoverSkills call must include cluster field"
    # ignored_tokens
    assert "ignored_tokens" in source, "fetchRecoverSkills call must include ignored_tokens"
    # validated_esco_labels
    assert "validated_esco_labels" in source, (
        "fetchRecoverSkills call must include validated_esco_labels for dedup guard"
    )


# ── Test 7: error codes mapped in UI ──────────────────────────────────────────

def test_recovery_error_code_mapping_present():
    source = ANALYZE_PAGE
    for code in [
        "DEV_TOOLS_DISABLED",
        "OPENAI_KEY_MISSING",
        "MODEL_MISSING",
        "LLM_CALL_FAILED",
        "INVALID_REQUEST",
        "NETWORK_ERROR",
        "AI_DISABLED",
        "UNKNOWN_ERROR",
    ]:
        assert code in source, f"AnalyzePage should map recovery error code {code}"


# ── Test 8: debug badge includes ai_available + ai_error ─────────────────────

def test_debug_badge_includes_ai_fields():
    source = ANALYZE_PAGE
    assert "ai_available" in source, "Debug badge must display ai_available"
    assert "ai_error" in source, "Debug badge must display ai_error"


# ── Test 6: score invariance — recovered skills never go to skills_uri ────────

def test_recovered_skills_not_injected_into_skills_uri():
    source = ANALYZE_PAGE
    # recoveredSkills must not be assigned to profile.skills_uri
    # Simple check: "recoveredSkills" should never appear in same line as "skills_uri"
    for line in source.splitlines():
        if "recoveredSkills" in line and "skills_uri" in line:
            raise AssertionError(
                f"Score-invariance violation: recoveredSkills appears on same line as skills_uri:\n  {line.strip()}"
            )
    # Also check api.ts definition: RecoverSkillsResponse has no skills_uri field
    assert "skills_uri" not in API_TS.split("RecoverSkillsResponse")[1].split("export")[0] if "RecoverSkillsResponse" in API_TS else True, (
        "RecoverSkillsResponse must not contain skills_uri field"
    )
