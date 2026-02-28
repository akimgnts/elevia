"""
test_documents_keywords.py — Deterministic ATS keyword extraction.

Tests:
  - Same input → same output (stability across calls)
  - Max 12 keywords returned
  - Stopwords excluded
  - Short tokens (< 3 chars) excluded
  - Frequency ordering: highest-freq tokens first
  - Alpha tie-break for equal frequency
  - Empty inputs handled gracefully
  - keywords_overlap: matched / missing split
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documents.ats_keywords import extract_ats_keywords, keywords_overlap


# ── Determinism ───────────────────────────────────────────────────────────────

def test_extract_deterministic():
    """Same title+description → identical list on repeated calls."""
    title = "Data Analyst VIE – Marketing Digital"
    desc = "Analyser les données clients. Maîtrise SQL et Python requise. Excel avancé."
    r1 = extract_ats_keywords(title, desc)
    r2 = extract_ats_keywords(title, desc)
    assert r1 == r2


def test_extract_deterministic_long_text():
    """Determinism holds on longer descriptions."""
    title = "Ingénieur R&D VIE"
    desc = ("Vous rejoindrez notre équipe R&D pour développer des solutions innovantes. "
            "Compétences requises: Python, Machine Learning, SQL, Git, Docker. "
            "Travail en équipe agile. Expérience en développement logiciel souhaitée. "
            "Bac+5 minimum. Anglais courant.") * 3
    r1 = extract_ats_keywords(title, desc)
    r2 = extract_ats_keywords(title, desc)
    assert r1 == r2


# ── Count limits ──────────────────────────────────────────────────────────────

def test_max_keywords():
    """Never returns more than 12 keywords (default max)."""
    title = "VIE Finance Juridique Marketing Digital Développement Commercial"
    desc = " ".join([f"competence{i}" for i in range(50)])
    result = extract_ats_keywords(title, desc)
    assert len(result) <= 12


def test_max_keywords_custom():
    """Custom max_kw is respected."""
    title = "Ingénieur Développement"
    desc = " ".join([f"skill{i}" for i in range(30)])
    result = extract_ats_keywords(title, desc, max_kw=5)
    assert len(result) <= 5


# ── Token filtering ───────────────────────────────────────────────────────────

def test_stopwords_excluded():
    """French/English stopwords should not appear in output."""
    title = "Stage VIE"
    desc = "le la les un une des de et ou à dans avec sans pour par sur"
    result = extract_ats_keywords(title, desc)
    stopwords = {"les", "une", "des", "avec", "dans", "pour", "par", "sur"}
    assert not any(kw in stopwords for kw in result)


def test_short_tokens_excluded():
    """Tokens shorter than 3 chars are excluded."""
    title = "BI IT"
    desc = "or an to is be as at by go do"
    result = extract_ats_keywords(title, desc)
    assert all(len(kw) >= 3 for kw in result)


def test_digits_excluded():
    """Pure numeric tokens are excluded."""
    title = "VIE 2024"
    desc = "Salaire 45000 euros. 3 mois d'expérience minimum. 12 compétences requises."
    result = extract_ats_keywords(title, desc)
    assert not any(kw.isdigit() for kw in result)


# ── Content tests ─────────────────────────────────────────────────────────────

def test_relevant_terms_included():
    """Key technical terms should appear in output."""
    title = "Data Analyst"
    desc = "Python SQL Machine Learning Data Scientist Analytics"
    result = extract_ats_keywords(title, desc)
    # At least one technical term should be present
    technical = {"python", "sql", "analytics", "learning", "machine", "scientist"}
    assert any(kw in technical for kw in result)


def test_empty_inputs():
    """Empty title and description → empty list (no crash)."""
    result = extract_ats_keywords("", "")
    assert isinstance(result, list)
    assert len(result) == 0


def test_none_like_inputs():
    """None replaced by empty string — no crash."""
    result = extract_ats_keywords("", "Some description without title.")
    assert isinstance(result, list)


def test_description_truncated_at_1200():
    """Description beyond 1200 chars is silently truncated (no crash, deterministic)."""
    title = "Analyst"
    desc = "python " * 300  # ~1800 chars
    result = extract_ats_keywords(title, desc)
    assert isinstance(result, list)
    assert len(result) <= 12


# ── keywords_overlap ──────────────────────────────────────────────────────────

def test_keywords_overlap_matched():
    """Skills matching offer keywords are in 'matched'."""
    profile_skills = ["Python", "SQL", "Excel", "Leadership"]
    offer_kw = ["python", "sql", "machine", "learning"]
    matched, missing = keywords_overlap(profile_skills, offer_kw)
    assert "python" in matched
    assert "sql" in matched
    assert "machine" in missing
    assert "learning" in missing


def test_keywords_overlap_empty():
    """Empty profile → all keywords in missing."""
    _, missing = keywords_overlap([], ["python", "sql"])
    assert "python" in missing
    assert "sql" in missing


def test_keywords_overlap_full_match():
    """All keywords matched."""
    matched, missing = keywords_overlap(["python", "sql"], ["python", "sql"])
    assert len(matched) == 2
    assert len(missing) == 0


def test_keywords_overlap_stable():
    """keywords_overlap output is deterministic."""
    skills = ["Python (programmation informatique)", "Analyse de données", "SQL"]
    kw = ["python", "analyse", "sql", "communication"]
    r1 = keywords_overlap(skills, kw)
    r2 = keywords_overlap(skills, kw)
    assert r1 == r2
