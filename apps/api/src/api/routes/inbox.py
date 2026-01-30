"""
inbox.py - Inbox routes: POST /inbox + POST /offers/{offer_id}/decision
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

from fastapi import APIRouter, HTTPException

from ..schemas.inbox import (
    DecisionRequest,
    DecisionResponse,
    InboxItem,
    InboxRequest,
    InboxResponse,
    RomeCompetence,
    RomeLink,
)
from ..utils.db import get_connection
from ..utils.offer_skills import get_offer_skills_by_offer_ids
from ..utils.rome_link import get_offer_rome_links, get_rome_competences_for_rome_codes

# Import matching engine
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from matching import MatchingEngine
from matching.extractors import extract_profile

logger = logging.getLogger(__name__)

router = APIRouter(tags=["inbox"])

# Same DB_PATH as offers.py
DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"


def _load_decided_ids(profile_id: str) -> Set[str]:
    """Load offer IDs already decided by this profile."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT offer_id FROM offer_decisions WHERE profile_id = ?",
            (profile_id,),
        ).fetchall()
        return {r["offer_id"] for r in rows}
    finally:
        conn.close()


def _load_catalog_offers() -> List[Dict]:
    """Load all offers from fact_offers table."""
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, source, title, description, company, city, country, "
            "publication_date, contract_duration, start_date FROM fact_offers"
        ).fetchall()
        offers = [dict(r) for r in rows]

        offer_ids = [str(o.get("id") or "") for o in offers]
        skills_map = get_offer_skills_by_offer_ids(conn, offer_ids)
        for offer in offers:
            offer_id = str(offer.get("id") or "")
            if offer_id in skills_map:
                offer["skills"] = skills_map[offer_id]

        conn.close()
        return offers
    except Exception as e:
        logger.warning(f"[inbox] Failed to load catalog: {e}")
        return []


@router.post("/inbox", summary="Get inbox items for a profile")
async def get_inbox(req: InboxRequest) -> InboxResponse:
    """Score catalog offers against profile, excluding already-decided ones."""
    decided_ids = _load_decided_ids(req.profile_id)
    catalog = _load_catalog_offers()

    if not catalog:
        return InboxResponse(
            profile_id=req.profile_id, items=[], total_matched=0, total_decided=len(decided_ids)
        )

    # Build engine + extract profile
    engine = MatchingEngine(offers=catalog)
    extracted = extract_profile(req.profile)

    items: List[InboxItem] = []
    source_map: Dict[str, str] = {str(offer.get("id") or ""): offer.get("source") or "" for offer in catalog}
    for offer in catalog:
        oid = str(offer.get("id") or "")
        if oid in decided_ids:
            continue

        result = engine.score_offer(extracted, offer)
        if result.score < req.min_score:
            continue

        items.append(
            InboxItem(
                offer_id=result.offer_id,
                title=offer.get("title") or "",
                company=offer.get("company"),
                country=offer.get("country"),
                city=offer.get("city"),
                score=result.score,
                reasons=result.reasons[:3],
            )
        )

    # Sort desc by score
    items.sort(key=lambda x: x.score, reverse=True)
    total_matched = len(items)
    items = items[: req.limit]

    ft_ids = [item.offer_id for item in items if source_map.get(item.offer_id) == "france_travail"]
    rome_links: Dict[str, Dict[str, str]] = {}
    rome_competences: Dict[str, List[Dict[str, str]]] = {}
    if ft_ids:
        conn = get_connection()
        try:
            rome_links = get_offer_rome_links(conn, ft_ids)
            rome_codes = [link["rome_code"] for link in rome_links.values() if link.get("rome_code")]
            if rome_codes:
                rome_competences = get_rome_competences_for_rome_codes(conn, rome_codes, limit_per_rome=3)
        finally:
            conn.close()

    for item in items:
        link = rome_links.get(item.offer_id)
        if link and link.get("rome_code") and link.get("rome_label"):
            item.rome = RomeLink(rome_code=link["rome_code"], rome_label=link["rome_label"])
        else:
            item.rome = None
        if item.rome and item.rome.rome_code:
            item.rome_competences = [
                RomeCompetence(**competence)
                for competence in rome_competences.get(item.rome.rome_code, [])
            ]
        else:
            item.rome_competences = []

    return InboxResponse(
        profile_id=req.profile_id,
        items=items,
        total_matched=total_matched,
        total_decided=len(decided_ids),
    )


@router.post("/offers/{offer_id}/decision", summary="Record a decision on an offer")
async def post_decision(offer_id: str, req: DecisionRequest) -> DecisionResponse:
    """Upsert a SHORTLISTED or DISMISSED decision."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO offer_decisions (profile_id, offer_id, status, note, decided_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(profile_id, offer_id) DO UPDATE SET
                status = excluded.status,
                note = excluded.note,
                decided_at = excluded.decided_at
            """,
            (req.profile_id, offer_id, req.status, req.note, now),
        )
        conn.commit()
    finally:
        conn.close()

    return DecisionResponse(
        profile_id=req.profile_id,
        offer_id=offer_id,
        status=req.status,
        decided_at=now,
    )
