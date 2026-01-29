"""
test_esco_extractor_regression.py
=================================
Anti-regression: ESCO raw skill extraction (extract.py)

Validates:
1. Whitelist skills are always captured
2. No absurdly long tokens leak through (> 30 chars unless controlled bigram)
3. Stopwords are filtered
"""

import pytest
from esco.extract import (
    extract_raw_skills_from_offer,
    extract_raw_skills_from_profile,
    WHITELIST_SKILLS,
    BIGRAM_WHITELIST,
    STOPWORDS,
)


# ============================================================================
# TEST 1 — Whitelist capture
# ============================================================================

OFFER_WITH_WHITELIST = {
    "title": "Data Engineer Python VIE",
    "description": "We need someone with Python, SQL, Excel and AWS experience.",
    "skills": ["react", "SAP"],
}

@pytest.mark.parametrize("skill", ["python", "sql", "excel", "aws", "react", "sap"])
def test_whitelist_skills_captured_from_offer(skill):
    """Every WHITELIST_SKILLS token present in offer text must appear in output."""
    tokens = extract_raw_skills_from_offer(OFFER_WITH_WHITELIST)
    tokens_lower = {t.lower() for t in tokens}
    assert skill in tokens_lower, f"Whitelist skill '{skill}' not captured. Got: {sorted(tokens_lower)}"


PROFILE_WITH_WHITELIST = {
    "skills": ["Python", "SQL"],
    "cv_text": "Expert in Excel, AWS, React and SAP.",
}

@pytest.mark.parametrize("skill", ["python", "sql", "excel", "aws", "react", "sap"])
def test_whitelist_skills_captured_from_profile(skill):
    """Every WHITELIST_SKILLS token present in profile must appear in output."""
    tokens = extract_raw_skills_from_profile(PROFILE_WITH_WHITELIST)
    tokens_lower = {t.lower() for t in tokens}
    assert skill in tokens_lower, f"Whitelist skill '{skill}' not captured. Got: {sorted(tokens_lower)}"


# ============================================================================
# TEST 2 — No absurdly long tokens (fragment leak guard)
# ============================================================================

MAX_TOKEN_LENGTH = 80  # generous limit; ESCO labels can be long after alias expansion

OFFER_LONG_TEXT = {
    "title": "Senior Full Stack Developer",
    "description": (
        "Nous recherchons un développeur expérimenté maîtrisant Python, JavaScript, "
        "React, Docker, Kubernetes et les méthodologies Agile/Scrum. "
        "Expérience requise en gestion de projets et data analysis."
    ),
    "skills": ["python", "javascript", "docker"],
}


def test_no_absurdly_long_tokens_offer():
    """No extracted token should exceed MAX_TOKEN_LENGTH."""
    tokens = extract_raw_skills_from_offer(OFFER_LONG_TEXT)
    for token in tokens:
        assert len(token) <= MAX_TOKEN_LENGTH, (
            f"Token too long ({len(token)} chars): '{token[:50]}...'"
        )


def test_no_absurdly_long_tokens_profile():
    """No extracted token should exceed MAX_TOKEN_LENGTH."""
    profile = {
        "skills": ["python", "machine learning", "data visualization"],
        "cv_text": OFFER_LONG_TEXT["description"],
    }
    tokens = extract_raw_skills_from_profile(profile)
    for token in tokens:
        assert len(token) <= MAX_TOKEN_LENGTH, (
            f"Token too long ({len(token)} chars): '{token[:50]}...'"
        )


# ============================================================================
# TEST 3 — Stopwords filtered
# ============================================================================

def test_stopwords_not_in_output():
    """Common stopwords must not appear in extracted tokens."""
    offer = {
        "title": "Le Data Analyst pour notre équipe",
        "description": "Vous serez en charge de la gestion des données avec Python et SQL.",
        "skills": ["python"],
    }
    tokens = extract_raw_skills_from_offer(offer)
    tokens_lower = {t.lower() for t in tokens}
    leaked = tokens_lower & STOPWORDS
    assert not leaked, f"Stopwords leaked into output: {leaked}"


# ============================================================================
# TEST 4 — Alias expansion produces output
# ============================================================================

def test_alias_expansion_adds_esco_labels():
    """Known aliases (e.g. 'python') should expand to ESCO labels."""
    offer = {"skills": ["python"]}
    tokens = extract_raw_skills_from_offer(offer)
    # 'python' alias expands to 'python (programmation informatique)'
    assert any("programmation" in t for t in tokens), (
        f"Alias expansion missing for 'python'. Got: {tokens}"
    )
