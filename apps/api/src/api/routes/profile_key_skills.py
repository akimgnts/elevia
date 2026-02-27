"""
profile_key_skills.py — POST /profile/key-skills

Display-only skill ranking for AnalyzePage "signal-first" UI.

Rules (deterministic, read-only):
1. Load IDF from fact_offer_skills (graceful fallback to {}).
2. If rome_code provided: find skills appearing in offers for that ROME code
   and mark them "weighted". (Graceful fallback → weighted=False for all.)
3. Rank: weighted → IDF desc → alphabetical.
4. Reason: "weighted" | "idf" (top quartile) | "standard".

NON-NEGOTIABLE: does NOT modify any matching/* files or scoring logic.
Always returns 200 with best-effort results.
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Set

from fastapi import APIRouter

from ..schemas.profile_key_skills import (
    KeySkillItem,
    KeySkillsRequest,
    KeySkillsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])

MAX_KEY_SKILLS = 12
MAX_ALL_SKILLS = 40


# ── IDF loader (read-only, graceful) ──────────────────────────────────────────

def _load_idf_from_db() -> Dict[str, float]:
    """
    Compute IDF table from fact_offer_skills.

    IDF(skill) = log(N / (1 + df(skill)))
    where N = distinct offer count, df = docs containing skill.

    Returns empty dict on any error (graceful fallback).
    """
    try:
        from ..utils.db import get_connection
        conn = get_connection()

        row = conn.execute(
            "SELECT COUNT(DISTINCT offer_id) FROM fact_offer_skills"
        ).fetchone()
        N: int = row[0] if row and row[0] else 0

        if N == 0:
            return {}

        rows = conn.execute(
            "SELECT skill, COUNT(DISTINCT offer_id) AS df "
            "FROM fact_offer_skills GROUP BY skill"
        ).fetchall()

        return {r[0]: math.log(N / (1 + r[1])) for r in rows}

    except Exception as exc:
        logger.debug("[key-skills] IDF load failed (graceful fallback): %s", exc)
        return {}


def _load_rome_skills(rome_code: str) -> Set[str]:
    """
    Return the set of normalised skill labels that appear in offers
    associated with rome_code.

    Uses rome_link table if available. Graceful fallback → empty set.
    """
    try:
        from ..utils.db import get_connection
        conn = get_connection()

        # Try to find offers linked to this ROME code
        rows = conn.execute(
            """
            SELECT DISTINCT fos.skill
            FROM fact_offer_skills fos
            JOIN offer_rome_links orl ON orl.offer_id = fos.offer_id
            WHERE orl.rome_code = ?
            """,
            (rome_code,),
        ).fetchall()

        return {r[0].lower().strip() for r in rows}

    except Exception as exc:
        logger.debug(
            "[key-skills] ROME skills load failed for %s (graceful fallback): %s",
            rome_code, exc,
        )
        return set()


# ── Ranking ───────────────────────────────────────────────────────────────────

def _rank_skills(
    validated_items: list,
    idf_table: Dict[str, float],
    rome_skills: Set[str],
) -> List[KeySkillItem]:
    """
    Deterministic skill ranking — display only, no scoring impact.

    Sort order: weighted first → IDF desc → alphabetical.
    Reason assignment:
    - "weighted" if skill in rome_skills
    - "idf"      if IDF >= top-quartile threshold among the profile skills
    - "standard" otherwise
    """
    # Compute IDF threshold: 75th percentile of IDF values in the profile
    idf_vals = [
        idf_table.get(item.label.lower().strip())
        for item in validated_items
    ]
    idf_vals_valid = sorted(v for v in idf_vals if v is not None)

    if len(idf_vals_valid) >= 4:
        # 75th percentile index
        idx_75 = 3 * len(idf_vals_valid) // 4
        idf_threshold: float | None = idf_vals_valid[idx_75]
    elif idf_vals_valid:
        idf_threshold = min(idf_vals_valid)
    else:
        idf_threshold = None

    items: List[KeySkillItem] = []
    for item in validated_items:
        norm = item.label.lower().strip()
        idf_val = idf_table.get(norm)
        is_weighted = norm in rome_skills

        if is_weighted:
            reason = "weighted"
        elif (
            idf_val is not None
            and idf_threshold is not None
            and idf_val >= idf_threshold
        ):
            reason = "idf"
        else:
            reason = "standard"

        items.append(
            KeySkillItem(
                label=item.label,
                reason=reason,
                idf=round(idf_val, 4) if idf_val is not None else None,
                weighted=is_weighted,
            )
        )

    # Deterministic sort: weighted → IDF desc → alpha
    items.sort(
        key=lambda x: (
            0 if x.weighted else 1,
            -(x.idf or 0.0),
            x.label.lower(),
        )
    )
    return items


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/profile/key-skills", response_model=KeySkillsResponse)
async def key_skills(body: KeySkillsRequest) -> KeySkillsResponse:
    """
    Rank validated ESCO skills by signal importance for AnalyzePage display.

    - Uses IDF from offers corpus (read-only, no scoring change).
    - Optionally uses ROME code to detect "weighted" skills.
    - Always returns HTTP 200 with best-effort results.
    - Deterministic: same inputs → same output.
    """
    # Guard: empty list is valid
    if not body.validated_items:
        return KeySkillsResponse(key_skills=[], all_skills_ranked=[])

    # Load IDF (graceful fallback → empty dict)
    idf_table = _load_idf_from_db()

    # Load ROME-weighted skills (graceful fallback → empty set)
    rome_skills: Set[str] = set()
    if body.rome_code:
        rome_skills = _load_rome_skills(body.rome_code)

    # Rank all validated items
    all_ranked = _rank_skills(body.validated_items, idf_table, rome_skills)

    return KeySkillsResponse(
        key_skills=all_ranked[:MAX_KEY_SKILLS],
        all_skills_ranked=all_ranked[:MAX_ALL_SKILLS],
    )
