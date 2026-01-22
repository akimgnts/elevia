"""
idf.py
======
Sprint 6 - Calcul IDF (Inverse Document Frequency)

Conforme à: docs/features/06_MATCHING_MINIMAL_EXPLICABLE.md
"""

import math
from typing import Dict, List, Set
from collections import Counter


def compute_idf(offers: List[Dict], skill_field: str = "skills") -> Dict[str, float]:
    """
    Calcule l'IDF (rareté) de chaque compétence sur le corpus d'offres.

    IDF(skill) = log(N / (1 + df(skill)))

    où:
    - N = nombre total d'offres
    - df(skill) = nombre d'offres contenant cette skill

    Args:
        offers: Liste des offres (dictionnaires)
        skill_field: Nom du champ contenant les skills

    Returns:
        Dict[str, float]: IDF par skill normalisée

    Spec: "IDF (rareté) calculée sur le corpus d'offres" (ligne 105)
    """
    if not offers:
        return {}

    N = len(offers)
    skill_doc_count: Counter = Counter()

    for offer in offers:
        raw_skills = offer.get(skill_field, [])

        # Normalisation des skills
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

        # Set pour compter chaque skill une seule fois par offre
        normalized_skills = set()
        for skill in raw_skills:
            if skill:
                normalized_skills.add(skill.lower().strip())

        # Incrémenter le compteur pour chaque skill unique dans cette offre
        for skill in normalized_skills:
            skill_doc_count[skill] += 1

    # Calcul IDF
    idf: Dict[str, float] = {}
    for skill, df in skill_doc_count.items():
        # IDF standard avec smoothing +1 pour éviter division par zéro
        idf[skill] = math.log(N / (1 + df))

    return idf


def get_skill_idf(skill: str, idf_table: Dict[str, float], default: float = 1.0) -> float:
    """
    Récupère l'IDF d'une skill.

    Args:
        skill: Compétence normalisée
        idf_table: Table IDF pré-calculée
        default: Valeur par défaut si skill inconnue

    Returns:
        float: Valeur IDF
    """
    return idf_table.get(skill.lower().strip(), default)
