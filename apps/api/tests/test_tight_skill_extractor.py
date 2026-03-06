"""
test_tight_skill_extractor.py — Tests for phrase-level technical skill extraction.

Tests (8):
  1. test_deterministic_ordering          — same input → identical output
  2. test_machine_learning_survives       — 2-gram "machine learning" passes filter
  3. test_generic_words_dropped           — "business", "team", "paris" go to dropped_tokens
  4. test_candidate_cap                   — skill_candidates never exceeds MAX=120
  5. test_power_bi_survives               — "Power BI" passes as cluster-allowlisted bigram
  6. test_tech_separator_phrase_survives  — "scikit-learn" passes via tech separator boost
  7. test_metrics_structure               — metrics dict has required keys with valid ranges
  8. test_empty_input                     — empty text returns empty result without error
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import (
    MAX_SKILL_CANDIDATES,
    ExtractionResult,
    extract_tight_skills,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_EN = (
    "Data Analyst with 3 years of experience in machine learning and data engineering. "
    "Daily use of Python, SQL, Power BI. Skills in ETL, Airflow, dbt. "
    "Experience with TensorFlow for predictive models. Docker and Kubernetes deployment."
)

SAMPLE_FR = (
    "Analyste Data avec 3 ans d'expérience en machine learning et data engineering. "
    "Utilisation quotidienne de Python, SQL, Power BI. Compétences en ETL, Airflow, dbt. "
    "Expérience avec TensorFlow pour les modèles prédictifs."
)


# ── Test 1: deterministic ordering ────────────────────────────────────────────


def test_deterministic_ordering():
    r1 = extract_tight_skills(SAMPLE_EN, cluster="DATA_IT")
    r2 = extract_tight_skills(SAMPLE_EN, cluster="DATA_IT")
    assert r1.skill_candidates == r2.skill_candidates, (
        "Same input must produce identical skill_candidates"
    )
    assert r1.metrics == r2.metrics, (
        "Same input must produce identical metrics"
    )
    assert r1.raw_tokens == r2.raw_tokens, (
        "Same input must produce identical raw_tokens"
    )


# ── Test 2: multi-word phrase survives ────────────────────────────────────────


def test_machine_learning_survives():
    result = extract_tight_skills(SAMPLE_EN, cluster="DATA_IT")
    candidates_lower = [c.lower() for c in result.skill_candidates]
    assert "machine learning" in candidates_lower, (
        f"'machine learning' must be in skill_candidates.\n"
        f"Top 20: {result.skill_candidates[:20]}"
    )


def test_machine_learning_survives_fr():
    result = extract_tight_skills(SAMPLE_FR, cluster="DATA_IT")
    candidates_lower = [c.lower() for c in result.skill_candidates]
    assert "machine learning" in candidates_lower, (
        "'machine learning' must survive in French-language CV text"
    )


# ── Test 3: generic words dropped ────────────────────────────────────────────


def test_generic_words_dropped():
    text = "business management team paris experience communication leadership skills"
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates_lower = [c.lower() for c in result.skill_candidates]
    for generic in ("business", "management", "team", "paris", "experience",
                    "communication", "leadership", "skills"):
        assert generic not in candidates_lower, (
            f"Generic word '{generic}' must NOT appear in skill_candidates. "
            f"Got: {candidates_lower}"
        )


# ── Test 4: candidate cap ─────────────────────────────────────────────────────


def test_candidate_cap():
    # Generate text with many distinct tech-looking tokens
    big_text = " ".join(
        f"Technology{i} Framework{i} Platform{i} Solution{i} Tool{i}"
        for i in range(100)
    )
    result = extract_tight_skills(big_text, cluster="DATA_IT")
    assert len(result.skill_candidates) <= MAX_SKILL_CANDIDATES, (
        f"skill_candidates capped at {MAX_SKILL_CANDIDATES}, got {len(result.skill_candidates)}"
    )


# ── Test 5: Power BI survives as cluster-allowlisted bigram ──────────────────


def test_power_bi_survives():
    text = "Expert en Power BI et visualisation de données avec Tableau."
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates_lower = [c.lower() for c in result.skill_candidates]
    assert "power bi" in candidates_lower, (
        f"'power bi' (cluster allowlist bigram) must survive.\nGot: {candidates_lower}"
    )


# ── Test 6: tech separator phrase survives ────────────────────────────────────


def test_tech_separator_phrase_survives():
    text = "Experienced with scikit-learn, vue.js and ci/cd pipelines."
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates_lower = [c.lower() for c in result.skill_candidates]
    assert any("scikit" in c for c in candidates_lower), (
        f"'scikit-learn' (tech separator) must survive.\nGot: {candidates_lower}"
    )


# ── Test 7: metrics structure and validity ────────────────────────────────────


def test_metrics_structure():
    result = extract_tight_skills(SAMPLE_EN, cluster="DATA_IT")
    m = result.metrics
    assert "raw_count" in m, "metrics must have raw_count"
    assert "candidate_count" in m, "metrics must have candidate_count"
    assert "noise_ratio" in m, "metrics must have noise_ratio"
    assert "tech_density" in m, "metrics must have tech_density"
    assert "top_ngrams" in m, "metrics must have top_ngrams"
    assert m["candidate_count"] == len(result.skill_candidates), (
        "metrics.candidate_count must equal len(skill_candidates)"
    )
    assert 0.0 <= m["noise_ratio"] <= 1.0, (
        f"noise_ratio must be in [0, 1], got {m['noise_ratio']}"
    )
    assert 0.0 <= m["tech_density"] <= 1.0, (
        f"tech_density must be in [0, 1], got {m['tech_density']}"
    )
    assert m["raw_count"] > 0, "raw_count must be positive for non-empty text"


# ── Test 8: empty input ───────────────────────────────────────────────────────


def test_empty_input():
    for empty in ("", "   ", "\n\n"):
        result = extract_tight_skills(empty, cluster="DATA_IT")
        assert result.skill_candidates == [], f"Empty input must produce no candidates (input={repr(empty)})"
        assert result.raw_tokens == [], f"Empty input must produce no raw_tokens"
        assert result.metrics["raw_count"] == 0
        assert result.metrics["candidate_count"] == 0
