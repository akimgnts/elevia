"""
test_pipeline_wiring.py — Canonical pipeline wiring tests.

4 required tests:
  1. test_parse_file_uses_compass_e_when_enabled    — ELEVIA_ENABLE_COMPASS_E=1 sets correct pipeline_used
  2. test_parse_file_uses_baseline_when_disabled    — ELEVIA_ENABLE_COMPASS_E=0 → pipeline_used="baseline"
  3. test_score_invariance_compass_e_on_off         — CVEnrichmentResult has no score_core field
  4. test_no_parallel_pipeline_routing              — parse routes import canonical_pipeline, not enrich_cv directly

Constraints:
  - No LLM calls (llm_enabled=False or mocked)
  - No France Travail API calls
  - Deterministic
"""
from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.canonical_pipeline import (
    CVPipelineResult,
    is_compass_e_enabled,
    is_trace_enabled,
    run_cv_pipeline,
)
from compass.cluster_library import ClusterLibraryStore
from compass.cv_enricher import enrich_cv
from compass.contracts import CVEnrichmentResult


# ── Shared fixture text ────────────────────────────────────────────────────────

_SAMPLE_CV = (
    "Développeur Python senior avec 5 ans d'expérience. "
    "Compétences: Python, SQL, Docker, Kubernetes, Machine Learning, TensorFlow. "
    "Expérience en gestion de projet et management d'équipe. "
    "Diplômé d'un Master en Informatique de l'École Polytechnique."
)


# ── Test 1 — Compass E enabled: pipeline_used reflects enrichment ──────────────

def test_parse_file_uses_compass_e_when_enabled():
    """
    When ELEVIA_ENABLE_COMPASS_E=1, run_cv_pipeline() sets pipeline_used
    to 'baseline+compass_e' (or '+llm' if LLM fired).
    Uses in-memory store, no LLM calls.
    """
    store = ClusterLibraryStore(db_path=":memory:")

    with patch.dict("os.environ", {"ELEVIA_ENABLE_COMPASS_E": "1"}):
        result = run_cv_pipeline(
            _SAMPLE_CV,
            profile_id="test-compass-e-on",
            compass_e_override=True,
        )

    assert isinstance(result, CVPipelineResult)
    assert result.compass_e_enabled is True
    assert result.pipeline_used.startswith("baseline+compass_e"), (
        f"Expected pipeline_used to start with 'baseline+compass_e', got {result.pipeline_used!r}"
    )
    # domain_skills_active is a list (possibly empty with empty library, that's ok)
    assert isinstance(result.domain_skills_active, list)
    assert isinstance(result.domain_skills_pending_count, int)


# ── Test 2 — Compass E disabled: pipeline_used = "baseline" ──────────────────

def test_parse_file_uses_baseline_when_disabled():
    """
    When ELEVIA_ENABLE_COMPASS_E=0 (default), run_cv_pipeline() must return
    pipeline_used='baseline' and compass_e_enabled=False.
    """
    with patch.dict("os.environ", {"ELEVIA_ENABLE_COMPASS_E": "0"}):
        result = run_cv_pipeline(
            _SAMPLE_CV,
            profile_id="test-compass-e-off",
            compass_e_override=False,
        )

    assert isinstance(result, CVPipelineResult)
    assert result.compass_e_enabled is False
    assert result.pipeline_used == "baseline", (
        f"Expected pipeline_used='baseline', got {result.pipeline_used!r}"
    )
    assert result.domain_skills_active == []
    assert result.domain_skills_pending_count == 0
    assert result.llm_fired is False


# ── Test 3 — Score invariance: enrichment output has no score_core ─────────────

def test_score_invariance_compass_e_on_off():
    """
    CVEnrichmentResult must not have a score_core, score, or weight field.
    CVPipelineResult must not have a score_core field either.
    domain_skills_active is display-only — it does NOT affect score_core.
    """
    # 1) Contract-level: CVEnrichmentResult has no score field
    enrichment_fields = set(CVEnrichmentResult.model_fields.keys())
    score_fields = {"score_core", "score", "match_score", "weight", "idf"}
    intersection = enrichment_fields & score_fields
    assert not intersection, (
        f"CVEnrichmentResult must not have score fields, found: {intersection}"
    )

    # 2) CVPipelineResult has no score_core field
    pipeline_result_fields = {f.name for f in CVPipelineResult.__dataclass_fields__.values()}
    pipeline_score_fields = pipeline_result_fields & score_fields
    assert not pipeline_score_fields, (
        f"CVPipelineResult must not have score fields, found: {pipeline_score_fields}"
    )

    # 3) Running pipeline with and without Compass E on same CV yields
    #    the same baseline_result (same ESCO skills)
    result_off = run_cv_pipeline(_SAMPLE_CV, profile_id="score-inv-off", compass_e_override=False)
    result_on = run_cv_pipeline(_SAMPLE_CV, profile_id="score-inv-on", compass_e_override=True)

    skills_off = set(result_off.baseline_result.get("skills_canonical") or [])
    skills_on = set(result_on.baseline_result.get("skills_canonical") or [])

    assert skills_off == skills_on, (
        f"ESCO skills must be identical regardless of Compass E flag.\n"
        f"COMPASS_E=0: {sorted(skills_off)}\n"
        f"COMPASS_E=1: {sorted(skills_on)}"
    )


# ── Test 4 — No parallel pipeline: routes import canonical_pipeline ────────────

def test_no_parallel_pipeline_routing():
    """
    profile_baseline.py and profile_file.py must delegate to the shared modular
    pipeline rather than re-implementing parsing orchestration locally.
    """
    baseline_path = Path(__file__).parent.parent / "src/api/routes/profile_baseline.py"
    file_path = Path(__file__).parent.parent / "src/api/routes/profile_file.py"

    baseline_source = baseline_path.read_text(encoding="utf-8")
    file_source = file_path.read_text(encoding="utf-8")
    assert "build_parse_baseline_response_payload" in baseline_source
    assert "build_parse_file_response_payload" in file_source

    pipeline_source = (Path(__file__).parent.parent / "src/compass/pipeline/profile_parse_pipeline.py").read_text(encoding="utf-8")
    assert "run_cv_pipeline" in pipeline_source, "shared pipeline must own canonical pipeline orchestration"

    # Also assert matching_v1.py is NOT imported by any enrichment module
    enricher_path = Path(__file__).parent.parent / "src/compass/cv_enricher.py"
    enricher_source = enricher_path.read_text(encoding="utf-8")
    assert "matching_v1" not in enricher_source, (
        "compass/cv_enricher.py must NEVER import matching_v1 — score invariance violation"
    )
    # score_core may appear in docstrings as an invariance note ("score_core is NEVER..."),
    # but must never be assigned, returned, or used as a variable.
    import re
    code_usage = re.search(
        r"score_core\s*=|=\s*score_core\b|score_core\s*\(|\.score_core\b|\[.score_core.\]",
        enricher_source,
    )
    assert code_usage is None, (
        "compass/cv_enricher.py must NEVER assign or call score_core in actual code"
    )
