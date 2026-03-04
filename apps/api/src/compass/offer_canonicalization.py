"""
offer_canonicalization.py — Canonical offer skill normalization (ESCO + DOMAIN).

Used by:
  - inbox_catalog runtime
  - ingest_pipeline (deterministic normalization)
"""
from __future__ import annotations

import importlib
import logging
import os
from typing import Dict, List

from compass.cluster_library import get_library
from compass.domain_uris import build_domain_uris_for_text
from offer.offer_cluster import detect_offer_cluster

# ESCO extraction and mapping (referential-based normalization)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from esco.extract import extract_raw_skills_from_offer, SKILL_ALIASES as _OFFER_SKILL_ALIASES
    from esco.mapper import map_skill
    from esco.uri_collapse import collapse_to_uris
except ImportError:
    _esco_extract = importlib.import_module("esco.extract")
    _esco_mapper = importlib.import_module("esco.mapper")
    _esco_collapse = importlib.import_module("esco.uri_collapse")
    extract_raw_skills_from_offer = _esco_extract.extract_raw_skills_from_offer
    _OFFER_SKILL_ALIASES = _esco_extract.SKILL_ALIASES
    map_skill = _esco_mapper.map_skill
    collapse_to_uris = _esco_collapse.collapse_to_uris

logger = logging.getLogger(__name__)

MAX_DEBUG_TOKENS = 200

# ── Top-K rarity filter for offer domain URIs ─────────────────────────────────
# Prevents denominator explosion: skills_score = matched_uris / offer_total_uris.
# Only the K rarest domain tokens (lowest occurrences_offers) are kept per offer.
# Rarer tokens = more cluster-specific = better signal, less denominator noise.
_OFFER_DOMAIN_TOPK_DEFAULT = 5


def _get_offer_domain_topk() -> int:
    try:
        return max(1, int(os.getenv("ELEVIA_OFFER_DOMAIN_TOPK", str(_OFFER_DOMAIN_TOPK_DEFAULT))))
    except (ValueError, TypeError):
        return _OFFER_DOMAIN_TOPK_DEFAULT


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_offer_skills_via_esco(offer: Dict) -> Dict[str, object]:
    """
    Normalize offer skills via ESCO referential.

    Strategy: Preserve original skills and augment with ESCO-extracted terms.
    """
    # Collect all skill sources
    all_skills: List[str] = []
    sources_used = set()
    mapped_items: List[Dict[str, str]] = []
    unmapped_tokens: List[str] = []

    # 1. Keep existing skills (from fixtures or payload)
    existing_skills = offer.get("skills", [])
    if isinstance(existing_skills, list) and existing_skills:
        for s in existing_skills:
            if not s:
                continue
            raw = str(s)
            all_skills.append(raw.lower())
            mapped_any = False
            result = map_skill(raw, enable_fuzzy=False)
            if result:
                mapped_items.append({
                    "surface": raw,
                    "esco_uri": result.get("esco_id", ""),
                    "esco_label": result.get("label") or result.get("canonical") or raw,
                    "source": "explicit",
                })
                mapped_any = True

            # Alias expansion for explicit skills (improve mapping coverage)
            alias_key = raw.lower()
            if alias_key in _OFFER_SKILL_ALIASES:
                for alias in _OFFER_SKILL_ALIASES[alias_key]:
                    alias_result = map_skill(alias, enable_fuzzy=False)
                    if alias_result:
                        mapped_items.append({
                            "surface": alias,
                            "esco_uri": alias_result.get("esco_id", ""),
                            "esco_label": alias_result.get("label") or alias_result.get("canonical") or alias,
                            "source": "alias",
                        })
                        mapped_any = True

            if not mapped_any:
                unmapped_tokens.append(raw)
        sources_used.add("explicit")

    # 2. Extract raw skills from offer text (title, description, etc.)
    raw_skills = extract_raw_skills_from_offer(offer)

    if raw_skills:
        try:
            for token in raw_skills:
                if not token:
                    continue
                raw = str(token)
                result = map_skill(raw, enable_fuzzy=False)
                if result:
                    mapped_items.append({
                        "surface": raw,
                        "esco_uri": result.get("esco_id", ""),
                        "esco_label": result.get("label") or result.get("canonical") or raw,
                        "source": "referential",
                    })
                    if result.get("label"):
                        all_skills.append(str(result["label"]).lower())
                    if result.get("raw_skill"):
                        all_skills.append(str(result["raw_skill"]).lower())
                    sources_used.add("referential")
                else:
                    unmapped_tokens.append(raw)
                    all_skills.append(raw.lower())
                    sources_used.add("extracted")
        except Exception as exc:
            logger.warning("[esco] Failed to map skills for offer %s: %s", offer.get("id"), exc)
            # Fallback: add raw skills as-is
            all_skills.extend(str(s).lower() for s in raw_skills)
            unmapped_tokens.extend(str(s) for s in raw_skills)
            sources_used.add("extracted")

    # Deduplicate while preserving order
    deduped = _dedupe_preserve_order([s for s in all_skills if s])

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

    collapse = collapse_to_uris(mapped_items)
    skills_uri = collapse.get("uris") or []
    skills_display = collapse.get("display") or []
    unmapped_deduped_full = _dedupe_preserve_order([s for s in unmapped_tokens if s])
    skills_unmapped_count = len(unmapped_deduped_full)
    unmapped_deduped = unmapped_deduped_full
    if len(unmapped_deduped) > MAX_DEBUG_TOKENS:
        unmapped_deduped = unmapped_deduped[:MAX_DEBUG_TOKENS]

    return {
        "skills": deduped,
        "skills_source": source,
        "skills_uri": skills_uri,
        "skills_display": skills_display,
        "skills_uri_count": len(skills_uri),
        "skills_uri_collapsed_dupes": int(collapse.get("collapsed_dupes", 0) or 0),
        "skills_unmapped": unmapped_deduped,
        "skills_unmapped_count": skills_unmapped_count,
    }


def _extract_esco_labels(offer: Dict) -> List[str]:
    labels: List[str] = []
    display = offer.get("skills_display")
    if isinstance(display, list):
        for item in display:
            if isinstance(item, dict) and item.get("label"):
                labels.append(str(item.get("label")))
    if not labels:
        skills = offer.get("skills")
        if isinstance(skills, list):
            labels = [str(s) for s in skills if isinstance(s, str)]
    return labels


def _apply_domain_uris(offer: Dict, *, library=None) -> None:
    """Attach DOMAIN URIs derived from the active cluster library."""
    cluster, _, _ = detect_offer_cluster(
        offer.get("title"),
        offer.get("description") or offer.get("display_description"),
        offer.get("skills") or [],
    )
    offer["offer_cluster"] = cluster
    if not cluster or cluster == "OTHER":
        offer["domain_uris"] = []
        offer["domain_uri_count"] = 0
        return

    lib = library or get_library()
    esco_labels = _extract_esco_labels(offer)
    extra_tokens = offer.get("skills_unmapped") or []
    extra_tokens = [t for t in extra_tokens if isinstance(t, (str, int, float))]

    text_parts: List[str] = []
    for key in ("title", "description", "display_description"):
        val = offer.get(key)
        if isinstance(val, str) and val.strip():
            text_parts.append(val)
    combined_text = " ".join(text_parts)

    domain_tokens, domain_uris = build_domain_uris_for_text(
        combined_text,
        esco_labels,
        cluster,
        extra_tokens=extra_tokens,
        library=lib,
    )

    # TOP-K rarity filter: prevent denominator explosion.
    # Keep only the K rarest domain tokens (lowest occurrences_offers = most specific).
    # Sort: (occurrences_offers ASC, token ASC) — deterministic, stable.
    topk = _get_offer_domain_topk()
    if len(domain_tokens) > topk:
        rarity = lib.get_active_skills_with_rarity(cluster)
        pairs = sorted(
            zip(domain_tokens, domain_uris),
            key=lambda p: (rarity.get(p[0], 0), p[0]),
        )
        domain_tokens = [p[0] for p in pairs[:topk]]
        domain_uris = [p[1] for p in pairs[:topk]]

    offer["domain_uris"] = domain_uris
    offer["domain_uri_count"] = len(domain_uris)
    if not domain_uris:
        return

    combined = _dedupe_preserve_order((offer.get("skills_uri") or []) + domain_uris)
    offer["skills_uri"] = combined
    offer["skills_uri_count"] = len(combined)

    skills_display = offer.get("skills_display")
    if not isinstance(skills_display, list):
        skills_display = []
    existing_uris = {
        item.get("uri")
        for item in skills_display
        if isinstance(item, dict) and item.get("uri")
    }
    for token_norm, uri in zip(domain_tokens, domain_uris):
        if uri in existing_uris:
            continue
        skills_display.append({"uri": uri, "label": token_norm, "source": "domain"})
        existing_uris.add(uri)
    offer["skills_display"] = skills_display


def normalize_offers_to_uris(
    offers: List[Dict],
    *,
    library=None,
    include_domain_uris: bool = True,
) -> List[Dict]:
    """
    Canonical normalization for offers.

    Mutates offers in-place by attaching:
      skills / skills_uri / skills_display / skills_unmapped (+ counts)
      domain_uris (if include_domain_uris=True)
    """
    lib = library or (get_library() if include_domain_uris else None)

    for offer in offers:
        normalized = _normalize_offer_skills_via_esco(offer)
        normalized_skills = normalized.get("skills") or []
        skills_source = normalized.get("skills_source") or "none"
        if normalized_skills:
            offer["skills"] = normalized_skills
            offer["skills_source"] = skills_source
            offer["skills_uri"] = normalized.get("skills_uri") or []
            offer["skills_display"] = normalized.get("skills_display") or []
            offer["skills_uri_count"] = normalized.get("skills_uri_count") or 0
            offer["skills_uri_collapsed_dupes"] = normalized.get("skills_uri_collapsed_dupes") or 0
            offer["skills_unmapped"] = normalized.get("skills_unmapped") or []
            offer["skills_unmapped_count"] = normalized.get("skills_unmapped_count") or 0
        else:
            offer["skills_source"] = "none" if not offer.get("skills") else "payload"
            offer.setdefault("skills_uri", [])
            offer.setdefault("skills_display", [])
            offer.setdefault("skills_uri_count", 0)
            offer.setdefault("skills_uri_collapsed_dupes", 0)
            offer.setdefault("skills_unmapped", [])
            offer.setdefault("skills_unmapped_count", 0)

        if include_domain_uris:
            _apply_domain_uris(offer, library=lib)

    return offers
