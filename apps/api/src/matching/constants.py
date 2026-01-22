"""
constants.py - Constantes pour le diagnostic
Sprint 9 - Conforme à docs/specs/diagnostic.md
"""

# Si > 50% des hard skills manquent → KO
HARD_SKILL_KO_RATIO = 0.5

# Ordre stable des piliers pour top_blocking_reasons
# VIE → Languages → Hard Skills → Education → Soft Skills
PILLAR_ORDER = [
    "vie_eligibility",
    "languages",
    "hard_skills",
    "education",
    "soft_skills",
]

# Pays UE pour éligibilité VIE
EU_COUNTRIES = {
    "france", "allemagne", "germany", "belgique", "belgium", "pays-bas",
    "netherlands", "luxembourg", "italie", "italy", "espagne", "spain",
    "portugal", "autriche", "austria", "irlande", "ireland", "grece",
    "greece", "pologne", "poland", "roumanie", "romania", "suede",
    "sweden", "finlande", "finland", "danemark", "denmark", "hongrie",
    "hungary", "republique tcheque", "czech republic", "slovaquie",
    "slovakia", "bulgarie", "bulgaria", "croatie", "croatia", "slovenie",
    "slovenia", "lettonie", "latvia", "lituanie", "lithuania", "estonie",
    "estonia", "chypre", "cyprus", "malte", "malta",
}

# Âge maximum pour VIE
VIE_MAX_AGE = 28
