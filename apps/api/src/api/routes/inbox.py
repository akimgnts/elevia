"""
inbox.py - Inbox routes: POST /inbox + POST /offers/{offer_id}/decision
"""

import json
import logging
import os
import time
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
    RomeInferred,
    RomeLink,
)
from ..utils.db import get_connection
from ..utils.inbox_catalog import load_catalog_offers
from ..utils.rome_link import get_offer_rome_links, get_rome_competences_for_rome_codes
from ..utils.rome_inferred import infer_rome_for_offers

# Import matching engine
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from matching import MatchingEngine
from matching.extractors import extract_profile

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["inbox"])

PROFILE_FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "profiles"


def _debug_matching_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_MATCHING", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _sample_list(values, limit=20):
    if not isinstance(values, list):
        return []
    sample = []
    for item in values:
        if isinstance(item, str):
            sample.append(item)
        elif isinstance(item, dict):
            if "name" in item:
                sample.append(str(item.get("name")))
            elif "label" in item:
                sample.append(str(item.get("label")))
            elif "raw_skill" in item:
                sample.append(str(item.get("raw_skill")))
            else:
                sample.append(str(item))
        else:
            sample.append(str(item))
        if len(sample) >= limit:
            break
    return sample


def _load_profile_fixture(profile_id: str, payload: Dict) -> tuple[Dict, str]:
    """
    Returns (profile, status). Status: FOUND | NOT_FOUND | DISABLED
    Uses ENV ELEVIA_INBOX_PROFILE_FIXTURES=1 to enable.
    """
    enabled = os.getenv("ELEVIA_INBOX_PROFILE_FIXTURES", "").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return payload, "DISABLED"

    forced = os.getenv("ELEVIA_PROFILE_FIXTURE", "").strip()
    candidates: List[str] = []
    if forced:
        candidates.append(forced)
    if profile_id:
        candidates.append(profile_id)
        candidates.append(f"{profile_id}_matching")
    payload_id = payload.get("id") or payload.get("profile_id")
    if payload_id:
        candidates.append(str(payload_id))
        candidates.append(f"{payload_id}_matching")

    for name in candidates:
        path = PROFILE_FIXTURES_DIR / f"{name}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8")), "FOUND"
            except Exception:
                continue

    # Optional default fallback when payload has too few skills (DEV-only usage)
    min_skills_value = os.getenv("ELEVIA_PROFILE_FIXTURE_MIN_SKILLS", "3").strip()
    try:
        min_skills = max(0, int(min_skills_value))
    except ValueError:
        min_skills = 3
    default_name = os.getenv("ELEVIA_PROFILE_FIXTURE_DEFAULT", "akim_guentas_matching").strip()
    raw_skills = payload.get("matching_skills") or payload.get("skills") or []
    raw_count = len(raw_skills) if isinstance(raw_skills, list) else (1 if raw_skills else 0)
    if raw_count <= min_skills and default_name:
        path = PROFILE_FIXTURES_DIR / f"{default_name}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8")), "DEFAULT"
            except Exception:
                pass

    return payload, "NOT_FOUND"


def _timing_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_API_TIMING", "").strip().lower()
    return value in {"1", "true", "yes", "on"}

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
    """Load all offers from catalog loader (shared with scripts)."""
    return load_catalog_offers()


@router.post("/inbox", summary="Get inbox items for a profile")
async def get_inbox(req: InboxRequest) -> InboxResponse:
    """Score catalog offers against profile, excluding already-decided ones."""
    t0 = time.perf_counter()
    profile_payload, lookup_status = _load_profile_fixture(req.profile_id, req.profile)
    if _debug_matching_enabled():
        raw_skills = profile_payload.get("matching_skills") or profile_payload.get("skills") or []
        logger.info(
            "INBOX_MATCH_INPUT profile_id=%s lookup_status=%s profile_internal_id=%s "
            "profile_skills_raw_count=%s profile_skills_raw_sample=%s",
            req.profile_id,
            lookup_status,
            profile_payload.get("id") or profile_payload.get("profile_id"),
            len(raw_skills) if isinstance(raw_skills, list) else (1 if raw_skills else 0),
            _sample_list(raw_skills),
        )
    decided_ids = _load_decided_ids(req.profile_id)
    t_decisions = time.perf_counter()
    catalog = _load_catalog_offers()
    t_catalog = time.perf_counter()

    if not catalog:
        if _timing_enabled():
            logger.info(
                "inbox_timing profile_id=%s decided=%s catalog=%s total=%s",
                req.profile_id,
                int((t_decisions - t0) * 1000),
                int((t_catalog - t_decisions) * 1000),
                int((t_catalog - t0) * 1000),
            )
        return InboxResponse(
            profile_id=req.profile_id, items=[], total_matched=0, total_decided=len(decided_ids)
        )

    # Build engine + extract profile
    engine = MatchingEngine(offers=catalog)
    extracted = extract_profile(profile_payload)
    t_profile = time.perf_counter()

    items: List[InboxItem] = []
    source_map: Dict[str, str] = {str(offer.get("id") or ""): offer.get("source") or "" for offer in catalog}
    for offer in catalog:
        oid = str(offer.get("id") or "")
        if oid in decided_ids:
            continue

        result = engine.score_offer(extracted, offer)
        if result.score < req.min_score:
            continue

        match_debug = result.match_debug or {}
        skills_debug = match_debug.get("skills") if isinstance(match_debug, dict) else {}
        matched_skills = []
        missing_skills = []
        if isinstance(skills_debug, dict):
            matched_skills = skills_debug.get("matched") or []
            missing_skills = skills_debug.get("missing") or []

        items.append(
            InboxItem(
                offer_id=result.offer_id,
                title=offer.get("title") or "",
                company=offer.get("company"),
                country=offer.get("country"),
                city=offer.get("city"),
                score=result.score,
                reasons=result.reasons[:3],
                matched_skills=matched_skills[:3],
                missing_skills=missing_skills[:3],
            )
        )

    t_scoring = time.perf_counter()

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

    # Build offer lookup for rome_inferred enrichment
    offer_lookup = {str(o.get("id") or ""): o for o in catalog}

    # Infer ROME for offers without native ROME (Business France VIE)
    non_ft_offers = [
        {"id": item.offer_id, "title": item.title, "description": offer_lookup.get(item.offer_id, {}).get("description")}
        for item in items
        if source_map.get(item.offer_id) != "france_travail"
    ]
    inferred_rome = infer_rome_for_offers(non_ft_offers) if non_ft_offers else {}

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

        # Populate rome_inferred for offers without native ROME
        inferred = inferred_rome.get(item.offer_id)
        if inferred:
            item.rome_inferred = RomeInferred(**inferred)
        else:
            item.rome_inferred = None

    t_rome = time.perf_counter()

    if _timing_enabled():
        logger.info(
            "inbox_timing profile_id=%s decided=%s catalog=%s profile_extract=%s scoring=%s rome=%s total=%s "
            "catalog_count=%s matched=%s decided_count=%s",
            req.profile_id,
            int((t_decisions - t0) * 1000),
            int((t_catalog - t_decisions) * 1000),
            int((t_profile - t_catalog) * 1000),
            int((t_scoring - t_profile) * 1000),
            int((t_rome - t_scoring) * 1000),
            int((t_rome - t0) * 1000),
            len(catalog),
            total_matched,
            len(decided_ids),
        )

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
