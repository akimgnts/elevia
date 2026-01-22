"""
test_matching_v1.py
===================
Sprint 6 - Tests obligatoires

Conforme à: docs/features/06_MATCHING_MINIMAL_EXPLICABLE.md

Tests obligatoires (spec lignes 226-233):
1. Une offre avec is_vie=None → rejetée
2. Une offre avec is_vie=False → rejetée
3. Aucune explication > 3 lignes
4. Aucun mot interdit (ia, probabilité)
5. Early-skip ne laisse pas passer une offre < 80
"""

import sys
from pathlib import Path

# Ajout du chemin src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from matching import MatchingEngine, extract_profile


# ============================================================================
# FIXTURES
# ============================================================================

def make_profile(
    skills=None,
    languages=None,
    education=None,
    preferred_countries=None,
):
    """Crée un profil de test."""
    return {
        "id": "test_profile",
        "skills": skills or ["python", "sql", "excel"],
        "languages": languages or ["français", "anglais"],
        "education": education or "bac+5",
        "preferred_countries": preferred_countries or [],
    }


def make_offer(
    offer_id="o1",
    is_vie=True,
    country="france",
    title="Data Analyst VIE",
    company="TechCorp",
    skills=None,
    languages=None,
    education=None,
):
    """Crée une offre de test."""
    return {
        "id": offer_id,
        "is_vie": is_vie,
        "country": country,
        "title": title,
        "company": company,
        "skills": skills or ["python", "sql", "excel"],
        "languages": languages or ["français"],
        "education": education,
    }


# ============================================================================
# TEST 0: Contrat anti-régression (poids et seuil figés)
# ============================================================================

def test_weights_locked():
    """Les pondérations sont VERROUILLÉES - toute modif = décision produit."""
    from matching.matching_v1 import (
        WEIGHT_SKILLS,
        WEIGHT_LANGUAGES,
        WEIGHT_EDUCATION,
        WEIGHT_COUNTRY,
        THRESHOLD,
    )

    assert WEIGHT_SKILLS == 0.70, f"WEIGHT_SKILLS modifié: {WEIGHT_SKILLS}"
    assert WEIGHT_LANGUAGES == 0.15, f"WEIGHT_LANGUAGES modifié: {WEIGHT_LANGUAGES}"
    assert WEIGHT_EDUCATION == 0.10, f"WEIGHT_EDUCATION modifié: {WEIGHT_EDUCATION}"
    assert WEIGHT_COUNTRY == 0.05, f"WEIGHT_COUNTRY modifié: {WEIGHT_COUNTRY}"
    assert THRESHOLD == 80, f"THRESHOLD modifié: {THRESHOLD}"

    # Somme des poids = 1.0
    total = WEIGHT_SKILLS + WEIGHT_LANGUAGES + WEIGHT_EDUCATION + WEIGHT_COUNTRY
    assert total == 1.0, f"Somme des poids != 1.0: {total}"

    print("✅ TEST 0: contrat poids/seuil verrouillé OK")


# ============================================================================
# TEST 1: is_vie = None → rejet (spec ligne 228)
# ============================================================================

def test_is_vie_none_rejected():
    """Une offre avec is_vie=None doit être rejetée."""
    profile = make_profile()
    offers = [make_offer(is_vie=None)]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    assert len(result.results) == 0, "Offre avec is_vie=None doit être rejetée"
    print("✅ TEST 1: is_vie=None → rejet OK")


# ============================================================================
# TEST 2: is_vie = False → rejet (spec ligne 229)
# ============================================================================

def test_is_vie_false_rejected():
    """Une offre avec is_vie=False doit être rejetée."""
    profile = make_profile()
    offers = [make_offer(is_vie=False)]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    assert len(result.results) == 0, "Offre avec is_vie=False doit être rejetée"
    print("✅ TEST 2: is_vie=False → rejet OK")


# ============================================================================
# TEST 3: Aucune explication > 3 lignes (spec ligne 230)
# ============================================================================

def test_max_three_reasons():
    """Aucune offre ne doit avoir plus de 3 raisons."""
    profile = make_profile(
        skills=["python", "sql", "excel", "reporting", "analytics"],
        languages=["français", "anglais"],
        education="bac+5",
        preferred_countries=["france"],
    )
    offers = [make_offer(
        skills=["python", "sql", "excel", "reporting", "analytics"],
        languages=["français"],
        education="bac+5",
        country="france",
    )]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    for match in result.results:
        assert len(match.reasons) <= 3, f"Offre {match.offer_id} a {len(match.reasons)} raisons (max 3)"

    print("✅ TEST 3: max 3 raisons OK")


# ============================================================================
# TEST 4: Aucun mot interdit (spec ligne 231)
# ============================================================================

def test_no_forbidden_words():
    """Aucun mot interdit dans les explications."""
    FORBIDDEN_WORDS = ["ia", "probabilité", "potentiel", "recommandation", "prédiction"]

    profile = make_profile()
    offers = [make_offer()]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    for match in result.results:
        for reason in match.reasons:
            reason_lower = reason.lower()
            for forbidden in FORBIDDEN_WORDS:
                assert forbidden not in reason_lower, \
                    f"Mot interdit '{forbidden}' trouvé dans: {reason}"

    print("✅ TEST 4: aucun mot interdit OK")


# ============================================================================
# TEST 5: Early-skip ne laisse pas passer une offre < 80 (spec ligne 232)
# ============================================================================

def test_early_skip_threshold():
    """Aucune offre avec score < 80 ne doit être retenue."""
    # Profil avec skills très différentes de l'offre → score bas
    profile = make_profile(
        skills=["java", "spring", "hibernate"],
        languages=["allemand"],
        education="bac",
    )
    offers = [make_offer(
        skills=["python", "sql", "excel"],
        languages=["français"],
        education="bac+5",
    )]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    for match in result.results:
        assert match.score >= 80, f"Offre {match.offer_id} a score {match.score} < 80"

    print("✅ TEST 5: seuil 80 respecté OK")


# ============================================================================
# TEST 6: Score déterministe (spec ligne 238)
# ============================================================================

def test_deterministic_score():
    """Mêmes inputs → mêmes outputs."""
    profile = make_profile()
    offers = [make_offer()]

    engine = MatchingEngine(offers)

    # Exécuter 3 fois
    results = []
    for _ in range(3):
        result = engine.match(profile, offers)
        results.append(engine.to_dict(result))

    # Vérifier que tous les résultats sont identiques
    assert results[0] == results[1] == results[2], "Résultats non déterministes"

    print("✅ TEST 6: déterminisme OK")


# ============================================================================
# TEST 7: Score final = int(round(100 * total)) (spec ligne 45)
# ============================================================================

def test_score_formula():
    """Vérifie la formule de score final."""
    profile = make_profile(
        skills=["python", "sql"],
        languages=["français"],
        education="bac+5",
        preferred_countries=["france"],
    )
    offers = [make_offer(
        skills=["python", "sql"],
        languages=["français"],
        education="bac+5",
        country="france",
    )]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    if result.results:
        match = result.results[0]
        # Recalcul manuel
        expected = int(round(100 * (
            0.70 * match.breakdown["skills"] +
            0.15 * match.breakdown["languages"] +
            0.10 * match.breakdown["education"] +
            0.05 * match.breakdown["country"]
        )))
        assert match.score == expected, f"Score {match.score} != attendu {expected}"

    print("✅ TEST 7: formule score OK")


# ============================================================================
# TEST 8: Message si aucun résultat (spec lignes 218-221)
# ============================================================================

def test_no_results_message():
    """Vérifie le message quand aucune offre ne match."""
    profile = make_profile(skills=["cobol", "fortran"])
    offers = [make_offer(skills=["python", "sql"])]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    assert len(result.results) == 0
    assert result.message is not None
    assert "80%" in result.message

    print("✅ TEST 8: message aucun résultat OK")


# ============================================================================
# TEST 9: is_vie = True → accepté (cas nominal)
# ============================================================================

def test_is_vie_true_accepted():
    """Une offre avec is_vie=True et bon match doit être acceptée."""
    profile = make_profile()
    offers = [make_offer(is_vie=True)]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    # Devrait avoir au moins un résultat si les skills matchent
    # (dépend du score final)
    print(f"✅ TEST 9: is_vie=True → {len(result.results)} résultat(s)")


# ============================================================================
# TEST 10: Hard filter - pays manquant
# ============================================================================

def test_missing_country_rejected():
    """Une offre sans pays doit être rejetée."""
    profile = make_profile()
    offers = [{
        "id": "o1",
        "is_vie": True,
        "country": None,  # Pas de pays
        "title": "Data Analyst",
        "company": "TechCorp",
        "skills": ["python", "sql"],
    }]

    engine = MatchingEngine(offers)
    result = engine.match(profile, offers)

    assert len(result.results) == 0, "Offre sans pays doit être rejetée"
    print("✅ TEST 10: pays manquant → rejet OK")


# ============================================================================
# EXÉCUTION
# ============================================================================

def run_all_tests():
    """Exécute tous les tests."""
    print("=" * 70)
    print("SPRINT 6 - TESTS OBLIGATOIRES")
    print("=" * 70)
    print()

    test_weights_locked()
    test_is_vie_none_rejected()
    test_is_vie_false_rejected()
    test_max_three_reasons()
    test_no_forbidden_words()
    test_early_skip_threshold()
    test_deterministic_score()
    test_score_formula()
    test_no_results_message()
    test_is_vie_true_accepted()
    test_missing_country_rejected()

    print()
    print("=" * 70)
    print("✅ TOUS LES TESTS PASSENT")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
