from __future__ import annotations

from compass.extraction.precanonical_recovery import (
    build_precanonical_recovery,
    clean_text_for_skill_recovery,
    extract_candidate_phrases,
    filter_relevant_skill_phrases,
)


def test_clean_text_for_skill_recovery_repairs_spaced_tokens():
    text = "S I R H\nA D P\nC P A M\nC P"

    cleaned = clean_text_for_skill_recovery(text)

    assert "SIRH" in cleaned
    assert "ADP" in cleaned
    assert "CPAM" in cleaned
    assert "C P" not in cleaned


def test_extract_candidate_phrases_recovers_expected_rh_phrases():
    text = "Gestion du temps de travail des salariés absences congés maladie"

    phrases = extract_candidate_phrases(text)

    assert "gestion du temps de travail" in phrases
    assert "absences" in phrases
    assert "conges" in phrases
    assert "maladie" in phrases


def test_build_precanonical_recovery_rh_signal_survives_before_canonical_mapping():
    text = (
        "recrutement\n"
        "documents préalable à l'embauche\n"
        "variables de paie\n"
        "plan de formation\n"
        "gestion du temps de travail\n"
        "S I R H\n"
        "A D P\n"
    )

    recovery = build_precanonical_recovery(text)
    phrases = recovery["relevant_phrases"]

    assert len(phrases) >= 6
    assert "recrutement" in phrases
    assert "documents prealable a l embauche" in recovery["candidate_phrases"]
    assert "variables de paie" in phrases
    assert "plan de formation" in phrases
    assert "gestion du temps de travail" in phrases
    assert "sirh" in phrases
    assert "adp" in phrases


def test_build_precanonical_recovery_finance_signal_survives():
    text = "analyse financière\nreporting mensuel\nécarts budgétaires\nconsolidation\n"

    recovery = build_precanonical_recovery(text)
    phrases = recovery["relevant_phrases"]

    assert "analyse financiere" in phrases
    assert "reporting mensuel" in phrases
    assert "ecarts budgetaires" in phrases
    assert "consolidation" in phrases


def test_filter_relevant_skill_phrases_removes_noise():
    phrases = ["c p", "le", "de", "avec", "super", "sirh", "variables de paie"]

    filtered = filter_relevant_skill_phrases(phrases)

    assert "sirh" in filtered
    assert "variables de paie" in filtered
    assert "c p" not in filtered
    assert "le" not in filtered
    assert "de" not in filtered
    assert "avec" not in filtered
    assert "super" not in filtered
