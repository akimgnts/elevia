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
    ExplainBlock,
    ExplainBreakdown,
    InboxItem,
    InboxRequest,
    InboxResponse,
    OfferSemanticRequest,
    OfferSemanticResponse,
    RomeCompetence,
    RomeInferred,
    RomeLink,
    SkillExplainItem,
)
from ..utils.db import get_connection
from ..utils.inbox_catalog import load_catalog_offers
from ..utils.rome_link import get_offer_rome_links, get_rome_competences_for_rome_codes
from ..utils.rome_inferred import infer_rome_for_offers
from semantic.semantic_service import compute_semantic_for_offer

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


def _build_explain(
    match_debug: Dict,
    rome_competence_list: List[RomeCompetence],
) -> ExplainBlock:
    """
    Build a display-only ExplainBlock from existing match_debug data.

    Does NOT modify or recompute any score. Read-only packaging.
    'weighted' flag = skill label matches a ROME competence label (case-insensitive).
    """
    # Build ROME competence label set for 'weighted' detection
    rome_labels: set = {
        c.competence_label.lower().strip()
        for c in rome_competence_list
        if c.competence_label
    }

    skills_debug = match_debug.get("skills", {}) if isinstance(match_debug, dict) else {}
    matched_raw: List[str] = skills_debug.get("matched", []) if isinstance(skills_debug, dict) else []
    missing_raw: List[str] = skills_debug.get("missing", []) if isinstance(skills_debug, dict) else []

    def _to_explain_items(skills: List[str], limit: int) -> List[SkillExplainItem]:
        return [
            SkillExplainItem(
                label=s,
                weighted=s.lower().strip() in rome_labels,
            )
            for s in skills[:limit]
        ]

    lang_d = match_debug.get("language", {}) if isinstance(match_debug, dict) else {}
    edu_d = match_debug.get("education", {}) if isinstance(match_debug, dict) else {}
    country_d = match_debug.get("country", {}) if isinstance(match_debug, dict) else {}

    breakdown = ExplainBreakdown(
        skills_score=float(skills_debug.get("score", 0.0)) if isinstance(skills_debug, dict) else 0.0,
        skills_weight=int(skills_debug.get("weight", 70)) if isinstance(skills_debug, dict) else 70,
        language_score=float(lang_d.get("score", 0.0)) if isinstance(lang_d, dict) else 0.0,
        language_weight=int(lang_d.get("weight", 15)) if isinstance(lang_d, dict) else 15,
        language_match=bool(lang_d.get("match", False)) if isinstance(lang_d, dict) else False,
        education_score=float(edu_d.get("score", 0.0)) if isinstance(edu_d, dict) else 0.0,
        education_weight=int(edu_d.get("weight", 10)) if isinstance(edu_d, dict) else 10,
        education_match=bool(edu_d.get("match", False)) if isinstance(edu_d, dict) else False,
        country_score=float(country_d.get("score", 0.0)) if isinstance(country_d, dict) else 0.0,
        country_weight=int(country_d.get("weight", 5)) if isinstance(country_d, dict) else 5,
        country_match=bool(country_d.get("match", False)) if isinstance(country_d, dict) else False,
        total=float(match_debug.get("total", 0.0)) if isinstance(match_debug, dict) else 0.0,
    )

    return ExplainBlock(
        matched_display=_to_explain_items(matched_raw, 6),
        missing_display=_to_explain_items(missing_raw, 6),
        matched_full=_to_explain_items(matched_raw, 30),
        missing_full=_to_explain_items(missing_raw, 30),
        breakdown=breakdown,
    )

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
    _explain_debug: Dict[str, tuple] = {}  # offer_id → (match_debug, matched, missing)
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
        matched_display = []
        missing_display = []
        scoring_unit = None
        intersection_count = None
        offer_uri_count = None
        profile_uri_count = None
        if isinstance(skills_debug, dict):
            matched_skills = skills_debug.get("matched") or []
            missing_skills = skills_debug.get("missing") or []
            matched_display = matched_skills
            missing_display = missing_skills
            scoring_unit = skills_debug.get("scoring_unit")
            intersection_count = skills_debug.get("intersection_count")
            offer_uri_count = skills_debug.get("offer_skill_uri_count")
            profile_uri_count = skills_debug.get("profile_skill_uri_count")
        if scoring_unit is None:
            scoring_unit = "uri" if offer.get("skills_uri") is not None else "string"
        if intersection_count is None:
            intersection_count = len(matched_display)
        if profile_uri_count is None:
            profile_uri_count = getattr(extracted, "skills_uri_count", None)

        score_raw = None
        if isinstance(match_debug, dict) and isinstance(match_debug.get("total"), (int, float)):
            score_raw = float(match_debug["total"]) / 100.0
        else:
            score_raw = float(result.score) / 100.0

        items.append(
            InboxItem(
                offer_id=result.offer_id,
                title=offer.get("title") or "",
                company=offer.get("company"),
                country=offer.get("country"),
                city=offer.get("city"),
                score=result.score,
                score_pct=result.score,
                score_raw=round(score_raw, 4),
                reasons=result.reasons[:3],
                description=offer.get("description"),
                display_description=offer.get("display_description"),
                description_snippet=offer.get("description_snippet"),
                matched_skills=matched_skills[:3],
                missing_skills=missing_skills[:3],
                matched_skills_display=matched_display,
                missing_skills_display=missing_display,
                unmapped_tokens=offer.get("skills_unmapped") or [],
                offer_uri_count=offer_uri_count
                if offer_uri_count is not None
                else (
                    offer.get("skills_uri_count")
                    if offer.get("skills_uri_count") is not None
                    else len(offer.get("skills_uri") or [])
                ),
                profile_uri_count=profile_uri_count if profile_uri_count is not None else None,
                intersection_count=intersection_count if intersection_count is not None else None,
                scoring_unit=scoring_unit if scoring_unit is not None else None,
                skills_uri_count=offer.get("skills_uri_count"),
                skills_uri_collapsed_dupes=offer.get("skills_uri_collapsed_dupes"),
                skills_unmapped_count=offer.get("skills_unmapped_count"),
                # explain is populated after ROME enrichment below
            )
        )
        # Stash full debug for explain enrichment after ROME is resolved
        if req.explain:
            _explain_debug[result.offer_id] = (match_debug, matched_skills, missing_skills)

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

        # Populate explain block (display-only, no scoring change)
        if req.explain and item.offer_id in _explain_debug:
            debug, _matched, _missing = _explain_debug[item.offer_id]
            item.explain = _build_explain(debug, item.rome_competences)

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


@router.post("/offers/{offer_id}/semantic", summary="Semantic similarity + relevant passages")
async def offer_semantic(offer_id: str, req: OfferSemanticRequest) -> OfferSemanticResponse:
    catalog = _load_catalog_offers()
    target = None
    for offer in catalog:
        oid = str(offer.get("id") or offer.get("offer_id") or offer.get("offer_uid") or "")
        if oid == str(offer_id):
            target = offer
            break
    if not target:
        raise HTTPException(status_code=404, detail="Offer not found")

    payload = compute_semantic_for_offer(req.profile_id, target)
    return OfferSemanticResponse(offer_id=str(offer_id), **payload)
