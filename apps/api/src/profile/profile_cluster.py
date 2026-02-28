"""
profile_cluster.py — Deterministic macro-cluster detection for profiles.

No LLM. No external calls. Pure keyword scoring.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional

CLUSTERS = [
    "DATA_IT",
    "FINANCE_LEGAL",
    "SUPPLY_OPS",
    "MARKETING_SALES",
    "ENGINEERING_INDUSTRY",
    "ADMIN_HR",
    "OTHER",
]

# Tie-break order (first wins on equal score)
TIE_BREAK = CLUSTERS[:]

# Keyword dictionary (small, explicit, deterministic)
_CLUSTER_KEYWORDS: Dict[str, List[str]] = {
    "DATA_IT": [
        "analyse de données",
        "data analysis",
        "data analyst",
        "data engineer",
        "data scientist",
        "informatique décisionnelle",
        "exploration de données",
        "programmation informatique",
        "cycle de développement logiciel",
        "python",
        "sql",
        "etl",
        "bi",
        "business intelligence",
        "machine learning",
    ],
    "FINANCE_LEGAL": [
        "finance",
        "financier",
        "comptabilité",
        "audit",
        "contrôle de gestion",
        "risk",
        "risk management",
        "juridique",
        "legal",
        "droit",
        "compliance",
        "trésorerie",
        "fiscal",
    ],
    "SUPPLY_OPS": [
        "supply chain",
        "logistique",
        "procurement",
        "achats",
        "operations",
        "opérations",
        "qualité",
        "lean",
        "stock",
        "inventory",
        "transport",
        "gestion des stocks",
    ],
    "MARKETING_SALES": [
        "marketing",
        "communication",
        "crm",
        "sales",
        "vente",
        "business development",
        "prospection",
        "relation client",
        "gestion de la relation client",
        "seo",
        "social media",
        "growth",
    ],
    "ENGINEERING_INDUSTRY": [
        "ingénierie",
        "engineering",
        "mécanique",
        "electrique",
        "électrique",
        "electronique",
        "électronique",
        "production",
        "industrial",
        "manufacturing",
        "r&d",
        "recherche",
        "cao",
        "simulation",
        "maintenance",
    ],
    "ADMIN_HR": [
        "rh",
        "ressources humaines",
        "administratif",
        "administration",
        "assistant",
        "office",
        "recrutement",
        "paie",
        "formation",
        "onboarding",
    ],
    "OTHER": [],
}


_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", lowered)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return _WS_RE.sub(" ", no_accents).strip()


_KEYWORDS_NORM: Dict[str, List[str]] = {
    cluster: [_normalize(k) for k in keys if k]
    for cluster, keys in _CLUSTER_KEYWORDS.items()
}


def detect_profile_cluster(skills: Optional[List[str]]) -> Dict[str, object]:
    """
    Detect macro-cluster from a list of skill labels.

    Scoring:
      - exact match: +2
      - substring: +1
    """
    if not skills:
        skills = []

    # Normalize + dedupe
    normalized_skills: List[str] = []
    seen = set()
    for s in skills:
        if not isinstance(s, str):
            continue
        norm = _normalize(s)
        if norm and norm not in seen:
            seen.add(norm)
            normalized_skills.append(norm)

    skills_count = len(normalized_skills)

    scores: Dict[str, int] = {c: 0 for c in CLUSTERS}

    for skill in normalized_skills:
        for cluster in CLUSTERS:
            for kw in _KEYWORDS_NORM.get(cluster, []):
                if not kw:
                    continue
                if skill == kw:
                    scores[cluster] += 2
                elif kw in skill:
                    scores[cluster] += 1

    total_points = sum(scores.values())

    if total_points == 0:
        dominant = "OTHER"
        distribution = {c: 0 for c in CLUSTERS}
        dominance_percent = 0
    else:
        # Tie-break by fixed order
        dominant = max(
            CLUSTERS,
            key=lambda c: (scores[c], -TIE_BREAK.index(c)),
        )
        # Build distribution (rounded) and adjust to 100
        raw = {c: (scores[c] / total_points) * 100 for c in CLUSTERS}
        distribution = {c: int(round(raw[c])) for c in CLUSTERS}
        diff = 100 - sum(distribution.values())
        if diff != 0:
            distribution[dominant] = max(0, distribution[dominant] + diff)
        dominance_percent = distribution.get(dominant, 0)

    note: Optional[str] = None
    if skills_count < 15:
        note = "LOW_SIGNAL"
    elif dominance_percent < 50:
        note = "TRANSVERSAL"

    confidence = round(dominance_percent / 100, 2)

    return {
        "dominant_cluster": dominant,
        "dominance_percent": dominance_percent,
        "distribution_percent": distribution,
        "skills_count": skills_count,
        "confidence": confidence,
        "note": note,
    }
