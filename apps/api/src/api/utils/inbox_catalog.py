"""
Inbox catalog loader (shared by runtime route and smoke scripts).

Sprint 7 - ESCO extraction + normalization for offers.
"""

import json
import os
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List

from .offer_skills import get_offer_skills_by_offer_ids

# ESCO extraction and mapping (referential-based normalization)
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from esco.extract import extract_raw_skills_from_offer
from esco.mapper import map_skills

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"
VIE_FIXTURES_PATH = Path(__file__).parent.parent.parent.parent / "fixtures" / "offers" / "vie_catalog.json"
VIE_FIXTURES_ENV = "ELEVIA_INBOX_USE_VIE_FIXTURES"


def _use_vie_fixtures() -> bool:
    value = os.getenv(VIE_FIXTURES_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _load_vie_fixtures() -> List[Dict]:
    if not VIE_FIXTURES_PATH.exists():
        logger.warning(f"[inbox] VIE fixtures missing at {VIE_FIXTURES_PATH}")
        return []
    try:
        raw = VIE_FIXTURES_PATH.read_text(encoding="utf-8")
        offers = json.loads(raw)
        if not isinstance(offers, list):
            logger.warning(f"[inbox] VIE fixtures not a list: {type(offers)}")
            return []
        return offers
    except Exception as e:
        logger.warning(f"[inbox] Failed to load VIE fixtures: {e}")
        return []


def _extract_skills_from_payload(payload: Dict) -> List[str]:
    skills = payload.get("skills") or payload.get("required_skills") or []
    if isinstance(skills, list) and skills:
        return [str(s) for s in skills if isinstance(s, (str, int, float))]
    competences = payload.get("competences") or []
    if isinstance(competences, list) and competences:
        extracted = []
        for comp in competences:
            if isinstance(comp, dict) and comp.get("libelle"):
                extracted.append(str(comp["libelle"]))
            elif isinstance(comp, str):
                extracted.append(comp)
        return extracted
    return []


def _extract_languages_from_payload(payload: Dict) -> List[str]:
    languages = payload.get("languages") or payload.get("required_languages") or []
    if isinstance(languages, list) and languages:
        return [str(l) for l in languages if isinstance(l, (str, int, float))]
    if isinstance(languages, str):
        return [l.strip() for l in languages.split(",") if l.strip()]
    return []


def _extract_education_from_payload(payload: Dict) -> str | None:
    education = payload.get("education_level") or payload.get("education")
    if isinstance(education, str):
        return education
    return None


def _normalize_offer_skills_via_esco(offer: Dict) -> tuple[List[str], str]:
    """
    Normalize offer skills via ESCO referential.

    Strategy: Preserve original skills and augment with ESCO-extracted terms.
    This ensures:
    - Explicit skills from fixtures/payload are kept as-is
    - ESCO extraction adds coverage from title/description
    - Both English (profile) and French (ESCO) terms are available for matching

    Returns:
        (normalized_skills, skills_source)
        - normalized_skills: list of skill labels (original + ESCO)
        - skills_source: classification of where skills came from
    """
    # Collect all skill sources
    all_skills: List[str] = []
    sources_used = set()

    # 1. Keep existing skills (from fixtures or payload) - they're usually good quality
    existing_skills = offer.get("skills", [])
    if isinstance(existing_skills, list) and existing_skills:
        all_skills.extend(str(s).lower() for s in existing_skills if s)
        sources_used.add("explicit")

    # 2. Extract raw skills from offer text (title, description, etc.)
    raw_skills = extract_raw_skills_from_offer(offer)

    if raw_skills:
        try:
            # Map to ESCO labels for additional coverage
            # NOTE: Fuzzy matching disabled for performance (O(n*m) comparisons too slow)
            mapping_result = map_skills(raw_skills, enable_fuzzy=False)
            mapped = mapping_result.get("mapped", [])
            unmapped = mapping_result.get("unmapped", [])

            # Add ESCO labels (might be French, adds semantic coverage)
            for m in mapped:
                if m.get("label"):
                    all_skills.append(m["label"].lower())
                # Also keep the raw skill to match English profile
                if m.get("raw_skill"):
                    all_skills.append(m["raw_skill"].lower())

            # Add unmapped skills as-is
            all_skills.extend(s.lower() for s in unmapped)

            if mapped:
                sources_used.add("referential")
            if unmapped:
                sources_used.add("extracted")

        except Exception as e:
            logger.warning("[esco] Failed to map skills for offer %s: %s", offer.get("id"), e)
            # Fallback: add raw skills as-is
            all_skills.extend(s.lower() for s in raw_skills)
            sources_used.add("extracted")

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for skill in all_skills:
        if skill and skill not in seen:
            seen.add(skill)
            deduped.append(skill)

    # Determine source classification
    if not deduped:
        source = "none"
    elif "explicit" in sources_used and "referential" in sources_used:
        source = "explicit|referential"
    elif "explicit" in sources_used:
        source = "explicit"
    elif "referential" in sources_used:
        source = "referential"
    else:
        source = "extracted"

    logger.debug(
        "[esco] offer=%s existing=%d extracted=%d final=%d source=%s",
        offer.get("id", "?"),
        len(existing_skills) if isinstance(existing_skills, list) else 0,
        len(raw_skills),
        len(deduped),
        source,
    )

    return deduped, source


def _attach_payload_fields(offer: Dict) -> None:
    payload_raw = offer.get("payload_json")
    if not payload_raw or not isinstance(payload_raw, str):
        return
    try:
        payload = json.loads(payload_raw)
    except Exception:
        return

    if offer.get("is_vie") is None and isinstance(payload.get("is_vie"), bool):
        offer["is_vie"] = payload.get("is_vie")

    if not offer.get("skills"):
        offer["skills"] = _extract_skills_from_payload(payload)

    if not offer.get("languages"):
        offer["languages"] = _extract_languages_from_payload(payload)

    if not offer.get("education"):
        education = _extract_education_from_payload(payload)
        if education:
            offer["education"] = education


def _apply_esco_normalization(offers: List[Dict]) -> List[Dict]:
    """Apply ESCO extraction + normalization to all offers."""
    for offer in offers:
        normalized_skills, skills_source = _normalize_offer_skills_via_esco(offer)
        if normalized_skills:
            offer["skills"] = normalized_skills
            offer["skills_source"] = skills_source
        else:
            # Keep existing skills if ESCO extraction yields nothing
            offer["skills_source"] = "none" if not offer.get("skills") else "payload"

    return offers


def load_catalog_offers() -> List[Dict]:
    """Load offers from fact_offers with payload mapping + fixture fallback.

    Pipeline:
    1. Load from DB or VIE fixtures
    2. Extract skills from payload_json (if not already present)
    3. Normalize all skills via ESCO referential
    """
    if _use_vie_fixtures():
        fixtures = _load_vie_fixtures()
        if fixtures:
            return _apply_esco_normalization(fixtures)

    if not DB_PATH.exists():
        fixtures = _load_vie_fixtures()
        return _apply_esco_normalization(fixtures) if fixtures else []

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=2000;")
        rows = conn.execute(
            "SELECT id, source, title, description, company, city, country, "
            "publication_date, contract_duration, start_date, payload_json FROM fact_offers"
        ).fetchall()
        offers = [dict(r) for r in rows]

        offer_ids = [str(o.get("id") or "") for o in offers]
        skills_map = get_offer_skills_by_offer_ids(conn, offer_ids)
        for offer in offers:
            offer_id = str(offer.get("id") or "")
            if offer_id in skills_map:
                offer["skills"] = skills_map[offer_id]
            _attach_payload_fields(offer)
            offer.pop("payload_json", None)

        conn.close()

        if not offers:
            fixtures = _load_vie_fixtures()
            return _apply_esco_normalization(fixtures) if fixtures else []

        if not any(offer.get("is_vie") is True for offer in offers):
            fixtures = _load_vie_fixtures()
            if fixtures:
                return _apply_esco_normalization(fixtures)

        return _apply_esco_normalization(offers)
    except Exception as e:
        logger.warning(f"[inbox] Failed to load catalog: {e}")
        fixtures = _load_vie_fixtures()
        return _apply_esco_normalization(fixtures) if fixtures else []
