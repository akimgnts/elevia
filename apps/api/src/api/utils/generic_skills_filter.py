"""
generic_skills_filter.py — Filter high-frequency generic ESCO URIs from skills_uri.

Skills like "anglais", "communication", "utiliser un logiciel de tableur" appear in
15–41 % of all BF offers with concentration ratios near 1.0 — they carry no
cluster-specific signal and cause false-positive matches across unrelated roles.

This module removes them from skills_uri (used for scoring) while leaving
skills_display untouched (user-visible labels are preserved).

Feature flag: ELEVIA_FILTER_GENERIC_URIS=1  (default: 0 — off during rollout)

Calibration source: 500-offer BF corpus frequency analysis, 2026-04-18.
"""

from __future__ import annotations

import os
from typing import List

# Minimum scorable URIs required after filtering. Offers reduced below this
# threshold carry too little signal to score reliably (e.g. [ANG COM TAB INF SQL]
# collapsing to [SQL] would match any SQL-carrying profile at 100 %).
MIN_SCORING_URIS = 2

# ── Hard generics: always removed from scoring ────────────────────────────────
# Criterion: df > 6 % AND concentration < 1.6 in BF 500-offer sample.
HARD_GENERIC_URIS: frozenset = frozenset({
    # Language prerequisites — employer requirement, not a professional skill
    "http://data.europa.eu/esco/skill/6d3edede-8951-4621-a835-e04323300fa0",  # anglais       41%
    "http://data.europa.eu/esco/skill/14ee9f76-3524-43d5-8a1a-5ba8283f8bd7",  # espagnol       5.4%
    "http://data.europa.eu/esco/skill/4812a4ea-dc55-4dc6-b9b0-4a59bba2c647",  # allemand       3.6%
    "http://data.europa.eu/esco/skill/e747e77e-0ea1-4001-8b07-1d11946b5f1b",  # français  (low but same logic)
    # Generic soft / office skills — present in all role types
    "http://data.europa.eu/esco/skill/15d76317-c71a-4fa2-aadc-2ecc34e627b7",  # communication  35%
    "http://data.europa.eu/esco/skill/1973c966-f236-40c9-b2d4-5d71a89019be",  # utiliser logiciel tableur  16%
    "http://data.europa.eu/esco/skill/7b5cce4d-c7fe-4119-b48f-70aa05391787",  # informatique   7.8%
})

# ── Weakly generic: removed only when no strong data signal is present ────────
# "analyse de données" (df=28.8 %, conc=0.83) is legitimate in a data-cluster offer
# but fires as a false positive on engineering/finance offers via the "analyse" alias.
WEAKLY_GENERIC_URIS: frozenset = frozenset({
    "http://data.europa.eu/esco/skill/97bd1c21-66b2-4b7e-ad0f-e3cda590e378",  # analyse de données
})

# ── Strong data URIs: anchors "analyse de données" as a legitimate signal ─────
# Presence of any of these means the offer is genuinely data-oriented.
# Criterion: concentration >= 3.5 in the data cluster.
STRONG_DATA_URIS: frozenset = frozenset({
    "http://data.europa.eu/esco/skill/25f0ea33-b4a2-4f31-b7b4-7d20e827b180",  # exploration de données  conc=3.76
    "http://data.europa.eu/esco/skill/598de5b0-5b58-4ea7-8058-a4bc4d18c742",  # SQL                     conc=4.81
    "http://data.europa.eu/esco/skill/4da171e5-779c-4983-a76f-91c16751e99f",  # MySQL
    "http://data.europa.eu/esco/skill/a8d07b5a-c1a1-42c6-9d53-db9c7a2ca996",  # PostgreSQL
    "http://data.europa.eu/esco/skill/ccd0a1d9-afda-43d9-b901-96344886e14d",  # Python                  conc=3.85
    "http://data.europa.eu/esco/skill/3a2d5b45-56e4-4f5a-a55a-4a4a65afdc43",  # apprentissage automatique
    "http://data.europa.eu/esco/skill/edebd83d-35f6-4ed5-a940-6c203d178c01",  # science des big data
    "http://data.europa.eu/esco/skill/7ee4c2ea-b349-4bd2-81a3-ec31475d4833",  # statistiques
    "http://data.europa.eu/esco/skill/65e58886-bd1e-4c5b-8ca5-8d9b353c8aa1",  # logiciel de visualisation des données
})


def is_enabled() -> bool:
    return os.getenv("ELEVIA_FILTER_GENERIC_URIS", "0").strip() == "1"


def filter_skills_uri_for_scoring(skills_uri: List[str]) -> List[str]:
    """Remove generic URIs from skills_uri used for scoring.

    skills_display is NOT touched — user-visible labels are unaffected.

    Rules applied when ELEVIA_FILTER_GENERIC_URIS=1:
      1. HARD_GENERIC_URIS are always removed.
      2. WEAKLY_GENERIC_URIS ("analyse de données") are removed unless at least
         one STRONG_DATA_URI is present after step 1.
      3. Anti-inflation guard: if fewer than MIN_SCORING_URIS remain, return an
         empty list — the matching engine treats this as a non-scorable offer
         (skills_score = 0), preventing single-URI offers from producing
         artificial 100 % matches.

    Original list order is preserved.
    Returns the input list unchanged when the flag is off or the list is empty.
    """
    if not is_enabled() or not skills_uri:
        return skills_uri

    all_uris = set(skills_uri)
    scoring_uris = all_uris - HARD_GENERIC_URIS

    has_strong_data = bool(scoring_uris & STRONG_DATA_URIS)
    if not has_strong_data:
        scoring_uris -= WEAKLY_GENERIC_URIS

    if len(scoring_uris) < MIN_SCORING_URIS:
        return []

    if scoring_uris == all_uris:
        return skills_uri

    return [u for u in skills_uri if u in scoring_uris]
