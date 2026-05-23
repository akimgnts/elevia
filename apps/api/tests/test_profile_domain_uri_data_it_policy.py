from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass import domain_uris as du
from compass.canonical.esco_bridge import build_canonical_esco_promoted


class _StubLibrary:
    def __init__(self, active_tokens):
        self._active_tokens = list(active_tokens)

    def get_active_skills(self, cluster):
        return list(self._active_tokens)


def test_data_it_profile_domain_uris_skip_transverse_halo_tokens(monkeypatch):
    monkeypatch.setattr(
        du,
        "extract_candidate_tokens",
        lambda text, esco_skills: [
            "analyse",
            "analyste",
            "coordination",
            "relations",
            "postgresql",
        ],
    )

    tokens, uris, debug = du.build_domain_uris_for_text(
        "placeholder",
        [],
        "DATA_IT",
        library=_StubLibrary(
            ["analyse", "analyste", "coordination", "relations", "postgresql"]
        ),
    )

    assert tokens == ["postgresql"]
    assert uris == ["compass:skill:DATA_IT:postgresql"]
    assert debug["candidates_count"] == 5


def test_non_data_it_clusters_keep_same_tokens(monkeypatch):
    monkeypatch.setattr(
        du,
        "extract_candidate_tokens",
        lambda text, esco_skills: [
            "analyse",
            "coordination",
            "relations",
        ],
    )

    tokens, uris, _ = du.build_domain_uris_for_text(
        "placeholder",
        [],
        "FINANCE",
        library=_StubLibrary(["analyse", "coordination", "relations"]),
    )

    assert tokens == ["analyse", "coordination", "relations"]
    assert uris == [
        "compass:skill:FINANCE:analyse",
        "compass:skill:FINANCE:coordination",
        "compass:skill:FINANCE:relations",
    ]


def test_financial_analysis_bridge_remains_resolved():
    result = build_canonical_esco_promoted(
        ["skill:financial_analysis"],
        base_skills_uri=[],
        cluster="FINANCE_BUSINESS_OPERATIONS",
        _promote_override=True,
    )

    assert any(uri.startswith("http://data.europa.eu/esco/") for uri in result)
