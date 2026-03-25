from __future__ import annotations

from pathlib import Path


ANALYZE = Path("apps/web/src/pages/AnalyzePage.tsx").read_text(encoding="utf-8")
STORE = Path("apps/web/src/store/profileStore.ts").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_parse_success_persists_profile_immediately():
    assert "function buildPersistedAnalyzeProfile(result: ParseFileResponse)" in ANALYZE
    assert "await setIngestResult(buildPersistedAnalyzeProfile(result));" in ANALYZE


def test_run_matching_uses_same_persistence_path():
    assert "await setIngestResult(buildPersistedAnalyzeProfile(parseResult));" in ANALYZE
    assert 'navigate("/inbox");' in ANALYZE


def test_broken_direct_link_to_inbox_is_removed():
    assert 'to="/inbox"' not in ANALYZE
    assert "onClick={handleRunMatching}" in ANALYZE


def test_profile_intelligence_is_not_silently_dropped_on_persist():
    assert "profile.profile_intelligence = result.profile_intelligence;" in ANALYZE
    assert "profile.profile_intelligence_ai_assist = result.profile_intelligence_ai_assist;" in ANALYZE
    assert "profile_intelligence?: Record<string, unknown>;" in API


def test_refresh_persistence_still_relies_on_profile_store_storage():
    assert 'const STORAGE_KEY = "elevia.profile.v1";' in STORE
    assert "localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));" in STORE
    assert "const stored = loadFromStorage();" in STORE
