"""
rome_inferred.py - Derive ROME codes from offer title using rule-based matching.

MVP v1: Simple keyword → ROME code mapping for Business France VIE offers.
Does NOT replace native ROME (for France Travail), only infers missing ROME.
"""

import re
import unicodedata
from typing import List, Optional, TypedDict


class RomeInferred(TypedDict):
    rome_code: str
    rome_label: str
    confidence: float
    source: str
    version: str


# ROME code mapping rules - ordered by priority (first match wins)
# Format: (pattern, rome_code, rome_label, confidence)
TITLE_RULES_V1 = [
    # Data roles
    (r"data\s*analyst", "M1403", "Analyse de données", 0.85),
    (r"analyste\s*donn[ée]es?", "M1403", "Analyse de données", 0.85),
    (r"data\s*engineer", "M1805", "Études et développement informatique", 0.80),
    (r"data\s*scientist", "M1403", "Analyse de données", 0.80),
    (r"business\s*intelligence|bi\s*analyst", "M1403", "Analyse de données", 0.75),

    # Business / Finance
    (r"business\s*analyst", "M1402", "Conseil en organisation et management", 0.80),
    (r"financial\s*analyst|analyste\s*financier", "M1201", "Analyse et ingénierie financière", 0.85),
    (r"finance|financier", "M1201", "Analyse et ingénierie financière", 0.70),
    (r"controller|contr[ôo]leur?\s*gestion", "M1206", "Management et ingénierie d'affaires", 0.75),

    # Marketing / Digital
    (r"marketing\s*analyst", "M1705", "Marketing", 0.80),
    (r"digital\s*marketing|marketing\s*digital", "E1101", "Animation de site multimédia", 0.75),
    (r"marketing", "M1705", "Marketing", 0.70),
    (r"community\s*manager|social\s*media", "E1101", "Animation de site multimédia", 0.75),
    (r"seo|referencement", "E1101", "Animation de site multimédia", 0.70),

    # Operations / Supply Chain
    (r"supply\s*chain|logistiqu|logistics", "N1301", "Transport et logistique", 0.80),
    (r"operations?\s*analyst", "M1402", "Conseil en organisation et management", 0.75),
    (r"procurement|achats?|buyer", "M1101", "Achats", 0.80),
    (r"quality\s*analyst|qualit[ée]", "H1502", "Management et ingénierie qualité", 0.75),

    # Research / R&D
    (r"research\s*analyst|chercheur", "K2401", "Recherche en sciences", 0.75),
    (r"r\s*[&e]\s*d|recherche", "K2401", "Recherche en sciences", 0.70),

    # IT / Dev
    (r"software\s*engineer|d[ée]veloppeur|developer", "M1805", "Études et développement informatique", 0.85),
    (r"devops|sre|infrastructure", "M1810", "Production et exploitation de systèmes", 0.80),
    (r"product\s*manager|chef\s*de\s*produit", "M1703", "Management produit", 0.80),
    (r"project\s*manager|chef\s*de\s*projet", "M1803", "Direction de projet", 0.80),

    # Sales / Commercial
    (r"sales|commercial|vente", "D1406", "Management commercial", 0.75),
    (r"account\s*manager|client", "D1406", "Management commercial", 0.70),

    # HR
    (r"human\s*resources?|rh|hr\s", "M1503", "Ressources humaines", 0.80),

    # Consulting
    (r"consultant", "M1402", "Conseil en organisation et management", 0.70),
]


def _normalize_text(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # Strip accents
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def infer_rome_from_title(title: str, description: Optional[str] = None) -> Optional[RomeInferred]:
    """
    Infer ROME code from offer title using rule-based matching.

    Args:
        title: Offer title
        description: Optional description for additional context (not used in v1)

    Returns:
        RomeInferred dict or None if no match
    """
    if not title:
        return None

    normalized = _normalize_text(title)

    for pattern, rome_code, rome_label, confidence in TITLE_RULES_V1:
        if re.search(pattern, normalized):
            return RomeInferred(
                rome_code=rome_code,
                rome_label=rome_label,
                confidence=confidence,
                source="title_rules",
                version="v1",
            )

    return None


def infer_rome_for_offers(offers: List[dict]) -> dict:
    """
    Batch infer ROME for multiple offers.

    Args:
        offers: List of offer dicts with 'id' and 'title' keys

    Returns:
        Dict mapping offer_id -> RomeInferred
    """
    results = {}
    for offer in offers:
        offer_id = offer.get("id") or offer.get("offer_id") or ""
        title = offer.get("title") or ""
        description = offer.get("description")

        inferred = infer_rome_from_title(title, description)
        if inferred:
            results[str(offer_id)] = inferred

    return results
