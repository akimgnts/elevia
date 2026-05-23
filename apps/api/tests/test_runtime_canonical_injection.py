from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

import matching.extractors as extractors


def _canonical_skill(
    *,
    canonical_id: str,
    label: str,
    strategy: str = "synonym_match",
) -> dict:
    return {
        "canonical_id": canonical_id,
        "label": label,
        "strategy": strategy,
        "confidence": 1.0,
    }


def test_runtime_canonical_injection_adds_anchor_uri(monkeypatch):
    monkeypatch.setenv("ELEVIA_RUNTIME_CANONICAL_INJECTION", "1")
    monkeypatch.setenv("ELEVIA_PROMOTE_ESCO", "0")
    monkeypatch.setenv("ELEVIA_DEBUG_PROFILE_EFFECTIVE", "1")

    calls: dict[str, object] = {}

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        calls["resolved_canonical_ids"] = list(resolved_canonical_ids)
        calls["base_skills_uri"] = list(base_skills_uri or [])
        trace = kwargs.get("trace")
        if isinstance(trace, dict):
            trace["canonical_resolution_success"] = list(resolved_canonical_ids)
            trace["unresolved_canonical_ids"] = []
            trace["canonical_bridge_source"] = {
                resolved_canonical_ids[0]: ["explicit_runtime_exact"]
            }
            trace["promoted_runtime_uris"] = ["http://data.europa.eu/esco/skill/runtime-recruitment"]
        return ["http://data.europa.eu/esco/skill/runtime-recruitment"]

    monkeypatch.setattr(extractors, "build_canonical_esco_promoted", fake_bridge)

    profile = {
        "id": "p-runtime-1",
        "matching_skills": ["recrutement"],
        "skills_uri": ["http://data.europa.eu/esco/skill/base-1"],
        "canonical_skills": [
            _canonical_skill(
                canonical_id="skill:recruitment",
                label="Recruitment",
            )
        ],
    }

    extracted = extractors.extract_profile(profile)

    assert calls["resolved_canonical_ids"] == ["skill:recruitment"]
    assert "http://data.europa.eu/esco/skill/runtime-recruitment" in extracted.skills_uri
    debug = profile.get("profile_effective_skills_debug") or {}
    assert debug.get("canonical_runtime_injected_count") == 1
    assert debug.get("canonical_runtime_ids") == ["skill:recruitment"]
    assert debug.get("canonical_resolution_success") == ["skill:recruitment"]
    assert debug.get("unresolved_canonical_ids") == []
    assert debug.get("canonical_bridge_source", {}).get("skill:recruitment")


def test_runtime_canonical_injection_dedupes_existing_uris(monkeypatch):
    monkeypatch.setenv("ELEVIA_RUNTIME_CANONICAL_INJECTION", "1")
    monkeypatch.setenv("ELEVIA_PROMOTE_ESCO", "0")

    duplicate_uri = "http://data.europa.eu/esco/skill/base-1"

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        return [duplicate_uri]

    monkeypatch.setattr(extractors, "build_canonical_esco_promoted", fake_bridge)

    profile = {
        "id": "p-runtime-2",
        "matching_skills": ["analyse financière"],
        "skills_uri": [duplicate_uri],
        "canonical_skills": [
            _canonical_skill(
                canonical_id="skill:financial_analysis",
                label="Financial Analysis",
            )
        ],
    }

    extracted = extractors.extract_profile(profile)

    assert list(extracted.skills_uri).count(duplicate_uri) == 1
    assert len(extracted.skills_uri) == 1


def test_runtime_canonical_injection_keeps_matching_skills_path(monkeypatch):
    monkeypatch.setenv("ELEVIA_RUNTIME_CANONICAL_INJECTION", "1")
    monkeypatch.setenv("ELEVIA_PROMOTE_ESCO", "0")

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        return ["http://data.europa.eu/esco/skill/runtime-compliance"]

    monkeypatch.setattr(extractors, "build_canonical_esco_promoted", fake_bridge)

    profile = {
        "id": "p-runtime-3",
        "matching_skills": ["conformité", "reporting"],
        "skills_uri": ["http://data.europa.eu/esco/skill/base-1"],
        "canonical_skills": [
            _canonical_skill(
                canonical_id="skill:compliance",
                label="Compliance",
            )
        ],
    }

    extracted = extractors.extract_profile(profile)

    assert extracted.skill_source == "matching_skills"
    assert "conformité" in extracted.skills
    assert "reporting" in extracted.skills
    assert "http://data.europa.eu/esco/skill/runtime-compliance" in extracted.skills_uri


def test_runtime_canonical_injection_skips_generic_canonicals(monkeypatch):
    monkeypatch.setenv("ELEVIA_RUNTIME_CANONICAL_INJECTION", "1")
    monkeypatch.setenv("ELEVIA_PROMOTE_ESCO", "0")

    calls: dict[str, object] = {}

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        calls["resolved_canonical_ids"] = list(resolved_canonical_ids)
        return ["http://data.europa.eu/esco/skill/runtime-recruitment"]

    monkeypatch.setattr(extractors, "build_canonical_esco_promoted", fake_bridge)

    profile = {
        "id": "p-runtime-4",
        "matching_skills": ["anglais", "recrutement"],
        "skills_uri": ["http://data.europa.eu/esco/skill/base-1"],
        "canonical_skills": [
            _canonical_skill(
                canonical_id="skill:english",
                label="English",
            ),
            _canonical_skill(
                canonical_id="skill:recruitment",
                label="Recruitment",
            ),
        ],
    }

    extracted = extractors.extract_profile(profile)

    assert calls["resolved_canonical_ids"] == ["skill:recruitment"]
    assert "http://data.europa.eu/esco/skill/runtime-recruitment" in extracted.skills_uri


def test_runtime_canonical_injection_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("ELEVIA_RUNTIME_CANONICAL_INJECTION", raising=False)
    monkeypatch.setenv("ELEVIA_PROMOTE_ESCO", "0")

    def fake_bridge(resolved_canonical_ids, base_skills_uri=None, **kwargs):
        raise AssertionError("bridge should not be called when runtime injection flag is OFF")

    monkeypatch.setattr(extractors, "build_canonical_esco_promoted", fake_bridge)

    profile = {
        "id": "p-runtime-5",
        "matching_skills": ["recrutement"],
        "skills_uri": ["http://data.europa.eu/esco/skill/base-1"],
        "canonical_skills": [
            _canonical_skill(
                canonical_id="skill:recruitment",
                label="Recruitment",
            )
        ],
    }

    extracted = extractors.extract_profile(profile)

    assert extracted.skills_uri == frozenset({"http://data.europa.eu/esco/skill/base-1"})
