"""
inbox.py - Inbox routes: POST /inbox + POST /offers/{offer_id}/decision
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, date, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas.inbox import (
    CompassExplainCompact,
    DecisionRequest,
    DecisionResponse,
    ExplainBlock,
    ExplainBreakdown,
    InboxItem,
    InboxMeta,
    InboxRequest,
    InboxResponse,
    OfferExplanation,
    OfferIntelligence,
    OfferSemanticRequest,
    OfferSemanticResponse,
    RomeCompetence,
    RomeInferred,
    RomeLink,
    ScoringV2,
    ScoringV3,
    SemanticExplainability,
    SkillExplainItem,
)
from ..deps.auth import AuthenticatedUser, get_optional_user
from ..utils.db import get_connection
from ..utils.inbox_catalog import load_catalog_offers, load_catalog_offers_filtered, count_catalog_offers_filtered
from ..utils.rome_link import get_offer_rome_links, get_rome_competences_for_rome_codes
from ..utils.rome_inferred import infer_rome_for_offers
from semantic.semantic_service import compute_semantic_for_offer
from offer.offer_cluster import detect_offer_cluster
from offer.generic_skill_stats import (
    get_offer_count,
    load_generic_skill_table,
    signal_score,
)
from profile.profile_cluster import detect_profile_cluster

# Import matching engine
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from matching import MatchingEngine
from matching.explanation_builder import build_explanation
from matching.extractors import extract_profile
from compass.contracts import SkillRef
from compass.explainability.explanation_builder import build_offer_explanation
from compass.explainability.semantic_explanation_builder import build_semantic_explainability
from compass.offer.offer_intelligence import (
    build_offer_intelligence,
    evaluate_role_domain_gate,
    is_role_domain_compatible,
)
from compass.scoring.scoring_v2 import build_scoring_v2
from compass.scoring.scoring_v3 import build_scoring_v3
from compass.signal_layer import build_explain_payload_v1, build_explain_compact, get_signal_cfg
from compass.matching_explainability import build_matching_explainability
from compass.cluster_signal import compute_cluster_skill_stats, compute_cluster_idf

logger = logging.getLogger("uvicorn.error")

router = APIRouter(tags=["inbox"])

PROFILE_FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "profiles"
GATE_TRACE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "eval" / "gate_rejection_trace.json"
MIN_RESULTS = 10
MIN_STRICT = 5   # below this, auto-widen to neighbors
SUSPICIOUS_SCORE_THRESHOLD = 95
SIGNAL_MIN_K = 1.0
PROFILE_INTELLIGENCE_WARM_LIMIT = 24
# Was 1 — intentionally low to avoid O(n²) fuzzy ESCO scan in build_offer_intelligence.
# After removing fuzzy scan in offer_canonical_mapping_stage, each offer takes ~1-3 ms,
# so we can now scan the full catalog (≤60 pages × 24 offers = 1,440 offers) safely.
# The while-loop early-exits as soon as candidate_items reaches page_size, so typical
# requests stop after 3–6 pages regardless of this ceiling.
PROFILE_INTELLIGENCE_MAX_PREFETCH_PAGES = 60
DEFAULT_MAX_PREFETCH_PAGES = 3

# Module-level cache for cluster IDF tables (built once, reused per request)
_cluster_idf_cache: Optional[Dict[str, Dict[str, float]]] = None
_engine_cache_catalog_id: Optional[int] = None
_engine_cache: Optional[MatchingEngine] = None


def _build_or_get_cluster_idf(catalog: List[Dict]) -> Dict[str, Dict[str, float]]:
    """
    Build and cache cluster-level IDF tables from the catalog.

    Detects cluster for each offer, then computes per-cluster skill frequency.
    Result is cached at module level (engine lifetime). Thread-safe for read-only use.
    """
    global _cluster_idf_cache
    if _cluster_idf_cache is not None:
        return _cluster_idf_cache

    # Detect cluster for every catalog offer (same logic as inbox scoring loop)
    offer_clusters: Dict[str, str] = {}
    for cat_offer in catalog:
        oid = str(cat_offer.get("id") or "")
        skill_labels = _extract_skill_labels(cat_offer.get("skills_display") or cat_offer.get("skills") or [])
        cluster, _, _ = detect_offer_cluster(
            cat_offer.get("title"),
            cat_offer.get("description") or cat_offer.get("display_description"),
            skill_labels,
        )
        offer_clusters[oid] = cluster or "OTHER"

    stats = compute_cluster_skill_stats(catalog, offer_clusters, skill_field="skills_uri")
    _cluster_idf_cache = compute_cluster_idf(stats)
    return _cluster_idf_cache


def _build_or_get_engine(catalog: List[Dict]) -> MatchingEngine:
    global _engine_cache_catalog_id, _engine_cache
    catalog_id = id(catalog)
    if _engine_cache is not None and _engine_cache_catalog_id == catalog_id:
        return _engine_cache
    _engine_cache = MatchingEngine(offers=catalog)
    _engine_cache_catalog_id = catalog_id
    return _engine_cache


def warm_inbox_runtime() -> Dict[str, int]:
    """
    Preload the heavy inbox runtime caches once.

    This avoids first-user cold-start spikes where catalog normalization,
    engine construction, and cluster IDF all happen inside a live request.
    """
    catalog = _load_catalog_offers()
    if not catalog:
        return {"catalog_count": 0, "cluster_count": 0}

    _build_or_get_engine(catalog)
    cluster_idf = _build_or_get_cluster_idf(catalog)
    # build_offer_intelligence warmup removed — takes 45 s/offer due to O(n²) fuzzy ESCO
    # scan inside run_offer_canonical_mapping_stage. Lazy first-request caching is acceptable.
    return {
        "catalog_count": len(catalog),
        "cluster_count": len(cluster_idf or {}),
        "offer_intelligence_warmed": 0,
    }


# Fixed adjacency matrix (cluster → neighbor clusters)
_ADJACENCY: Dict[str, List[str]] = {
    "DATA_IT": ["ENGINEERING_INDUSTRY"],
    "ENGINEERING_INDUSTRY": ["DATA_IT", "SUPPLY_OPS"],
    "MARKETING_SALES": ["SUPPLY_OPS"],
    "SUPPLY_OPS": ["ENGINEERING_INDUSTRY", "MARKETING_SALES"],
    "FINANCE_LEGAL": ["ADMIN_HR"],
    "ADMIN_HR": ["FINANCE_LEGAL"],
    "OTHER": [],
}


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


def _extract_skill_labels(raw_skills) -> List[str]:
    if not raw_skills:
        return []
    if isinstance(raw_skills, list):
        labels = []
        for item in raw_skills:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict) and item.get("label"):
                labels.append(str(item.get("label")))
        return labels
    if isinstance(raw_skills, str):
        return [s.strip() for s in raw_skills.split(",") if s.strip()]
    return []


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


def _debug_inbox_filters_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_INBOX_FILTERS", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _gate_trace_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_GATE_TRACE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _append_gate_trace(entries: List[Dict]) -> None:
    if not entries:
        return
    payload = {"entries": []}
    if GATE_TRACE_PATH.exists():
        try:
            payload = json.loads(GATE_TRACE_PATH.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                payload = {"entries": []}
        except Exception:
            payload = {"entries": []}
    current_entries = payload.get("entries")
    if not isinstance(current_entries, list):
        current_entries = []
    current_entries.extend(entries)
    payload["entries"] = current_entries
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    GATE_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GATE_TRACE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _map_match_strength(confidence: Optional[str]) -> Optional[str]:
    if not confidence:
        return None
    conf = confidence.strip().upper()
    if conf == "HIGH":
        return "STRONG"
    if conf == "MED":
        return "MEDIUM"
    return "WEAK"


def _derive_dominant_reason(
    confidence: Optional[str],
    *,
    near_match_count: int,
    rare_signal_level: Optional[str] = None,
) -> Optional[str]:
    if not confidence and not rare_signal_level and near_match_count <= 0:
        return None
    conf = (confidence or "LOW").strip().upper()
    rare = (rare_signal_level or "").strip().upper()
    if conf == "HIGH":
        return "Strong core alignment"
    if rare == "HIGH":
        return "Rare skill signal detected"
    if near_match_count > 0:
        return "Partial match with near skills"
    if conf == "MED":
        return "Partial match"
    return "Weak match"


def _apply_front_explanation(
    item: InboxItem,
    *,
    match_debug: Dict,
    confidence: Optional[str],
    profile_labels: List[str],
    offer_labels: List[str],
) -> None:
    explanation_payload = build_offer_explanation(
        match_debug,
        score=item.score,
        confidence=confidence,
        profile_effective_skills=profile_labels,
        job_required_skills=offer_labels,
    )
    item.explanation = OfferExplanation(**explanation_payload)

    legacy = build_explanation(
        match_debug,
        score=item.score,
        confidence=confidence,
    )
    item.fit_score = legacy.get("fit_score")
    if legacy.get("match_strength"):
        item.match_strength = legacy.get("match_strength")
    item.why_match = legacy.get("why_match") or []
    item.main_blockers = legacy.get("main_blockers") or []
    item.distance = legacy.get("distance")
    item.next_move = legacy.get("next_move")


def _extract_profile_intelligence_payload(profile_payload: Dict) -> Optional[Dict]:
    value = profile_payload.get("profile_intelligence")
    return value if isinstance(value, dict) else None


def _apply_offer_intelligence(
    item: InboxItem,
    *,
    offer_payload: Dict,
    precomputed_payload: Optional[Dict] = None,
    allow_recompute: bool = False,
) -> None:
    payload = precomputed_payload
    if payload is None and allow_recompute:
        try:
            payload = build_offer_intelligence(offer=offer_payload)
        except Exception:
            payload = None
    item.offer_intelligence = OfferIntelligence(**payload) if payload else None


def _apply_semantic_explainability(
    item: InboxItem,
    *,
    profile_intelligence: Optional[Dict],
) -> None:
    payload = build_semantic_explainability(
        profile_intelligence=profile_intelligence,
        offer_intelligence=item.offer_intelligence.model_dump() if item.offer_intelligence else None,
        explanation=item.explanation.model_dump() if item.explanation else None,
    )
    item.semantic_explainability = SemanticExplainability(**payload) if payload else None


def _apply_scoring_v2(
    item: InboxItem,
    *,
    profile_intelligence: Optional[Dict],
) -> None:
    payload = build_scoring_v2(
        profile_intelligence=profile_intelligence,
        offer_intelligence=item.offer_intelligence.model_dump() if item.offer_intelligence else None,
        semantic_explainability=item.semantic_explainability.model_dump() if item.semantic_explainability else None,
        matching_score=item.score_raw if item.score_raw is not None else item.score,
    )
    item.scoring_v2 = ScoringV2(**payload) if payload else None


def _apply_scoring_v3(
    item: InboxItem,
    *,
    profile_intelligence: Optional[Dict],
) -> None:
    payload = build_scoring_v3(
        profile_intelligence=profile_intelligence,
        offer_intelligence=item.offer_intelligence.model_dump() if item.offer_intelligence else None,
        semantic_explainability=item.semantic_explainability.model_dump() if item.semantic_explainability else None,
        explanation=item.explanation.model_dump() if item.explanation else None,
        matching_score=item.score_raw if item.score_raw is not None else item.score,
    )
    item.scoring_v3 = ScoringV3(**payload) if payload else None


def _parse_date_param(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        try:
            return datetime.fromisoformat(value).date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid date: {value}") from exc


def _normalize_contract_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    norm = value.strip().lower()
    if norm in {"vie", "v.i.e", "v i e"}:
        return "VIE"
    return value.strip()


def _build_explain(
    match_debug: Dict,
    rome_competence_list: List[RomeCompetence],
    *,
    near_matches: Optional[List[dict]] = None,
    near_match_summary: Optional[dict] = None,
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
    matched_core_raw: List[str] = skills_debug.get("matched_core", []) if isinstance(skills_debug, dict) else []
    missing_core_raw: List[str] = skills_debug.get("missing_core", []) if isinstance(skills_debug, dict) else []
    matched_secondary_raw: List[str] = skills_debug.get("matched_secondary", []) if isinstance(skills_debug, dict) else []
    missing_secondary_raw: List[str] = skills_debug.get("missing_secondary", []) if isinstance(skills_debug, dict) else []
    matched_context_raw: List[str] = skills_debug.get("matched_context", []) if isinstance(skills_debug, dict) else []
    missing_context_raw: List[str] = skills_debug.get("missing_context", []) if isinstance(skills_debug, dict) else []

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

    near_matches_list = near_matches or []
    near_summary = near_match_summary or {}

    if near_matches_list:
        logger.info(json.dumps({
            "event": "MATCH_EXPLAINABILITY_STATS",
            "exact_matches": len(matched_raw),
            "missing_core": len(missing_raw),
            "near_matches": len(near_matches_list),
            "max_near_strength": float(near_summary.get("max_strength", 0.0)),
        }))

    return ExplainBlock(
        matched_display=_to_explain_items(matched_raw, 6),
        missing_display=_to_explain_items(missing_raw, 6),
        matched_full=_to_explain_items(matched_raw, 30),
        missing_full=_to_explain_items(missing_raw, 30),
        matched_core=_to_explain_items(matched_core_raw, 30),
        missing_core=_to_explain_items(missing_core_raw, 30),
        matched_secondary=_to_explain_items(matched_secondary_raw, 30),
        missing_secondary=_to_explain_items(missing_secondary_raw, 30),
        matched_context=_to_explain_items(matched_context_raw, 30),
        missing_context=_to_explain_items(missing_context_raw, 30),
        breakdown=breakdown,
        near_matches=near_matches_list,
        near_match_count=int(near_summary.get("count", len(near_matches_list))),
        near_match_summary=near_summary if near_matches_list else None,
    )


def _unpack_explain_debug(payload: tuple) -> tuple[Dict, List[str], List[str], List[dict], dict]:
    match_debug = payload[0] if len(payload) > 0 else {}
    matched = payload[1] if len(payload) > 1 else []
    missing = payload[2] if len(payload) > 2 else []
    near_matches = payload[3] if len(payload) > 3 else []
    near_summary = payload[4] if len(payload) > 4 else {}
    return match_debug, matched, missing, near_matches, near_summary


def _score_offers(
    offers: List[Dict],
    *,
    decided_ids: Set[str],
    engine: MatchingEngine,
    extracted,
    profile_payload: Dict,
    profile_intelligence: Optional[Dict],
    explain_enabled: bool,
    min_score: int,
    freq_table: Dict,
    offer_count: int,
    contract_type_norm: Optional[str] = None,
) -> tuple[List[InboxItem], Dict[str, tuple], Dict[str, str], Dict[str, Dict], Dict[str, Dict], List[Dict]]:
    items: List[InboxItem] = []
    _explain_debug: Dict[str, tuple] = {}
    source_map: Dict[str, str] = {str(offer.get("id") or ""): offer.get("source") or "" for offer in offers}
    offer_lookup: Dict[str, Dict] = {str(o.get("id") or ""): o for o in offers}
    offer_intelligence_map: Dict[str, Dict] = {}
    gate_rejections: List[Dict] = []

    for offer in offers:
        oid = str(offer.get("id") or "")
        if oid in decided_ids:
            continue
        if contract_type_norm == "VIE":
            if offer.get("is_vie") is not True and offer.get("source") != "business_france":
                continue

        offer_intelligence_payload = None
        if profile_intelligence:
            try:
                offer_intelligence_payload = build_offer_intelligence(offer=offer)
            except Exception as _offer_int_exc:
                logger.warning("[inbox] offer_intelligence failed for offer %s: %s", oid, _offer_int_exc)
                continue
            gate_decision = evaluate_role_domain_gate(
                profile_intelligence=profile_intelligence,
                offer_intelligence=offer_intelligence_payload,
            )
            if not gate_decision.get("compatible"):
                if _gate_trace_enabled():
                    gate_rejections.append(
                        {
                            "profile_id": str(profile_payload.get("id") or profile_payload.get("profile_id") or ""),
                            "offer_id": oid,
                            "offer_title": offer.get("title") or "",
                            "profile_role": str(profile_intelligence.get("dominant_role_block") or ""),
                            "offer_role": str(offer_intelligence_payload.get("dominant_role_block") or ""),
                            "profile_domains": list(profile_intelligence.get("dominant_domains") or []),
                            "offer_domains": list(offer_intelligence_payload.get("dominant_domains") or []),
                            "role_match": gate_decision.get("role_match"),
                            "domain_overlap": bool(gate_decision.get("domain_overlap")),
                            "rejection_reason": gate_decision.get("rejection_reason"),
                            "was_potentially_valid": bool(gate_decision.get("was_potentially_valid")),
                            "shared_domains": list(gate_decision.get("shared_domains") or []),
                            "matched_signals": list((gate_decision.get("signal_overlap") or {}).get("matched_signals") or []),
                        }
                    )
                continue
            offer_intelligence_map[oid] = offer_intelligence_payload

        try:
            result = engine.score_offer(extracted, offer)
        except Exception as _score_exc:
            logger.warning("[inbox] score_offer failed for offer %s: %s", oid, _score_exc)
            continue
        if result.score < min_score:
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

        matched_skills_all = matched_skills if isinstance(matched_skills, list) else []
        offer_skill_labels = _extract_skill_labels(offer.get("skills_display") or offer.get("skills") or [])
        offer_cluster = offer.get("offer_cluster") or ""
        if not offer_cluster:
            offer_cluster, _, _ = detect_offer_cluster(
                offer.get("title"),
                offer.get("description") or offer.get("display_description"),
                offer_skill_labels,
            )
        signal = signal_score(matched_skills_all, freq_table, offer_count)
        coherence = (
            "suspicious"
            if result.score >= SUSPICIOUS_SCORE_THRESHOLD and signal < SIGNAL_MIN_K
            else "ok"
        )

        score_raw = None
        if isinstance(match_debug, dict) and isinstance(match_debug.get("total"), (int, float)):
            score_raw = float(match_debug["total"]) / 100.0
        else:
            score_raw = float(result.score) / 100.0

        near_matches = []
        near_summary = {}
        if explain_enabled:
            profile_labels = profile_payload.get("matching_skills") or profile_payload.get("skills") or []
            offer_labels = offer.get("skills_display") or offer.get("skills") or []
            near = build_matching_explainability(profile_labels, offer_labels)
            near_matches = near.get("near_matches", [])
            near_summary = near.get("near_match_summary", {})

        item = InboxItem(
                offer_id=result.offer_id,
                source=offer.get("source"),
                title=offer.get("title") or "",
                company=offer.get("company"),
                country=offer.get("country"),
                city=offer.get("city"),
                publication_date=offer.get("publication_date"),
                is_vie=offer.get("is_vie"),
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
                offer_cluster=offer_cluster,
                signal_score=signal,
                coherence=coherence,
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
            )
        if near_matches:
            item.near_match_count = len(near_matches)
        items.append(item)

        _explain_debug[result.offer_id] = (match_debug, matched_skills, missing_skills, near_matches, near_summary)

    return items, _explain_debug, source_map, offer_lookup, offer_intelligence_map, gate_rejections


def _apply_domain_gating(
    items: List[InboxItem],
    *,
    profile_cluster: Optional[str],
    domain_mode: str,
    sort_buckets: bool,
) -> tuple[List[InboxItem], Dict[str, object]]:
    coverage_before = len(items)
    is_strict_mode = domain_mode in ("strict", "in_domain")
    neighbors_of_profile: List[str] = _ADJACENCY.get(profile_cluster or "", [])
    neighbor_set = set(neighbors_of_profile)

    for item in items:
        oc = item.offer_cluster or "OTHER"
        if oc != "OTHER" and oc == profile_cluster:
            item.domain_bucket = "strict"
        elif oc in neighbor_set:
            item.domain_bucket = "neighbor"
        else:
            item.domain_bucket = "out"

    strict_items = [i for i in items if i.domain_bucket == "strict"]
    neighbor_items = [i for i in items if i.domain_bucket == "neighbor"]
    out_items = [i for i in items if i.domain_bucket == "out"]
    strict_count = len(strict_items)
    neighbor_count = len(neighbor_items)
    out_count = len(out_items)

    # Update coherence using domain_bucket (incoherent = suspicious score outside strict)
    for item in items:
        item.coherence = (
            "suspicious"
            if item.score >= SUSPICIOUS_SCORE_THRESHOLD
            and item.domain_bucket != "strict"
            and (item.signal_score or 0.0) < SIGNAL_MIN_K
            else "ok"
        )

    def _bucket_sort(bucket: List[InboxItem]) -> List[InboxItem]:
        return sorted(bucket, key=lambda i: (-i.score, -(i.signal_score or 0.0), i.offer_id))

    if not is_strict_mode:
        gating_mode = "OUT_OF_DOMAIN"
        if sort_buckets:
            items = _bucket_sort(strict_items) + _bucket_sort(neighbor_items) + _bucket_sort(out_items)
        else:
            items = [i for i in items if i.domain_bucket in {"strict", "neighbor", "out"}]
    elif strict_count >= MIN_STRICT:
        gating_mode = "IN_DOMAIN"
        if sort_buckets:
            items = _bucket_sort(strict_items)
        else:
            items = [i for i in items if i.domain_bucket == "strict"]
    else:
        gating_mode = "STRICT_PLUS_NEIGHBORS"
        if sort_buckets:
            items = _bucket_sort(strict_items) + _bucket_sort(neighbor_items)
        else:
            items = [i for i in items if i.domain_bucket in {"strict", "neighbor"}]

    coverage_after = len(items)
    suggest_out_of_domain = (
        is_strict_mode
        and coverage_after < MIN_RESULTS
        and out_count > 0
    )
    out_of_domain_count = out_count

    cluster_distribution_top20: Dict[str, int] = {}
    for item in items[:20]:
        key = item.offer_cluster or "UNKNOWN"
        cluster_distribution_top20[key] = cluster_distribution_top20.get(key, 0) + 1

    suspicious_items = [item for item in items if item.coherence == "suspicious"]
    suspicious_count = len(suspicious_items)
    suspicious_sample_ids = [item.offer_id for item in suspicious_items[:5]]

    meta = {
        "gating_mode": gating_mode,
        "coverage_before": coverage_before,
        "coverage_after": coverage_after,
        "suggest_out_of_domain": suggest_out_of_domain,
        "out_of_domain_count": out_of_domain_count,
        "cluster_distribution_top20": cluster_distribution_top20,
        "strict_count": strict_count,
        "neighbor_count": neighbor_count,
        "out_count": out_count,
        "suspicious_count": suspicious_count,
        "suspicious_sample_ids": suspicious_sample_ids,
    }
    return items, meta


def _apply_compass_filters(
    items: List[InboxItem],
    *,
    domain_bucket: Optional[str],
    confidence: Optional[str],
    rare_level: Optional[str],
    sector_level: Optional[str],
    has_tool_unspecified: Optional[bool],
) -> List[InboxItem]:
    filtered: List[InboxItem] = []
    for item in items:
        if domain_bucket and item.domain_bucket != domain_bucket:
            continue
        ev1 = item.explain_v1
        if confidence and (ev1 is None or ev1.confidence != confidence):
            continue
        if rare_level and (ev1 is None or ev1.rare_signal_level != rare_level):
            continue
        if sector_level and (ev1 is None or ev1.sector_signal_level != sector_level):
            continue
        if has_tool_unspecified is not None:
            reasons = ev1.incoherence_reasons if ev1 else []
            flagged = any(str(r).startswith("TOOL_UNSPECIFIED") for r in reasons)
            if has_tool_unspecified != flagged:
                continue
        filtered.append(item)
    return filtered

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
def get_inbox(
    req: InboxRequest,
    domain_mode: str = Query(default="in_domain", pattern="^(strict|in_domain|all)$"),
    q_company: Optional[str] = Query(default=None, min_length=1),
    country: Optional[str] = Query(default=None, min_length=1),
    city: Optional[str] = Query(default=None, min_length=1),
    contract_type: Optional[str] = Query(default=None, min_length=1),
    published_from: Optional[str] = Query(default=None, min_length=1),
    published_to: Optional[str] = Query(default=None, min_length=1),
    domain_bucket: Optional[str] = Query(default=None, pattern="^(strict|neighbor|out)$"),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    confidence: Optional[str] = Query(default=None, pattern="^(LOW|MED|HIGH)$"),
    rare_level: Optional[str] = Query(default=None, pattern="^(LOW|MED|HIGH)$"),
    sector_level: Optional[str] = Query(default=None, pattern="^(LOW|MED|HIGH)$"),
    has_tool_unspecified: Optional[bool] = Query(default=None),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=100),
    sort: Optional[str] = Query(default=None, pattern="^(published_desc|score_desc|confidence_desc)$"),
) -> InboxResponse:
    """Score catalog offers against profile, excluding already-decided ones."""
    t0 = time.perf_counter()
    profile_payload, lookup_status = _load_profile_fixture(req.profile_id, req.profile)
    profile_intelligence = _extract_profile_intelligence_payload(profile_payload)
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
    use_filters = any(
        value is not None
        for value in (
            q_company,
            country,
            city,
            contract_type,
            published_from,
            published_to,
            domain_bucket,
            min_score,
            confidence,
            rare_level,
            sector_level,
            has_tool_unspecified,
            page,
            page_size,
            sort,
        )
    )
    if use_filters:
        return _get_inbox_filtered(
            req=req,
            profile_payload=profile_payload,
            domain_mode=domain_mode,
            q_company=q_company,
            country=country,
            city=city,
            contract_type=contract_type,
            published_from=published_from,
            published_to=published_to,
            domain_bucket=domain_bucket,
            min_score=min_score,
            confidence=confidence,
            rare_level=rare_level,
            sector_level=sector_level,
            has_tool_unspecified=has_tool_unspecified,
            page=page,
            page_size=page_size,
            sort=sort,
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
    engine = _build_or_get_engine(catalog)
    extracted = extract_profile(profile_payload)
    t_profile = time.perf_counter()
    profile_cluster = detect_profile_cluster(list(getattr(extracted, "skills", []))).get("dominant_cluster")

    freq_table = load_generic_skill_table()
    offer_count = get_offer_count()

    # Compass config + cluster IDF (cached, built once per catalog load)
    _inbox_cfg = get_signal_cfg()
    _sector_enabled = _inbox_cfg.get("sector_signal_enabled", False)
    _rerank_enabled = _inbox_cfg.get("rerank_use_sector_signal", False)
    _cluster_idf: Optional[Dict[str, Dict[str, float]]] = (
        _build_or_get_cluster_idf(catalog) if _sector_enabled else None
    )

    items, _explain_debug, source_map, offer_lookup, offer_intelligence_map, gate_rejections = _score_offers(
        catalog,
        decided_ids=decided_ids,
        engine=engine,
        extracted=extracted,
        profile_payload=profile_payload,
        profile_intelligence=profile_intelligence,
        explain_enabled=req.explain,
        min_score=req.min_score,
        freq_table=freq_table,
        offer_count=offer_count,
    )
    if _gate_trace_enabled():
        _append_gate_trace(gate_rejections)

    t_scoring = time.perf_counter()

    # ── Post-layer: cluster ladder (no scoring changes) ───────────────────────
    coverage_before = len(items)
    is_strict_mode = domain_mode in ("strict", "in_domain")
    neighbors_of_profile: List[str] = _ADJACENCY.get(profile_cluster or "", [])
    neighbor_set = set(neighbors_of_profile)

    # Assign domain_bucket to every item
    for item in items:
        oc = item.offer_cluster or "OTHER"
        if oc != "OTHER" and oc == profile_cluster:
            item.domain_bucket = "strict"
        elif oc in neighbor_set:
            item.domain_bucket = "neighbor"
        else:
            item.domain_bucket = "out"

    strict_items = [i for i in items if i.domain_bucket == "strict"]
    neighbor_items = [i for i in items if i.domain_bucket == "neighbor"]
    out_items = [i for i in items if i.domain_bucket == "out"]
    strict_count = len(strict_items)
    neighbor_count = len(neighbor_items)
    out_count = len(out_items)

    # Update coherence using domain_bucket (incoherent = suspicious score outside strict)
    for item in items:
        item.coherence = (
            "suspicious"
            if item.score >= SUSPICIOUS_SCORE_THRESHOLD
            and item.domain_bucket != "strict"
            and (item.signal_score or 0.0) < SIGNAL_MIN_K
            else "ok"
        )

    def _bucket_sort(bucket: List[InboxItem]) -> List[InboxItem]:
        return sorted(bucket, key=lambda i: (-i.score, -(i.signal_score or 0.0), i.offer_id))

    # Apply ladder
    if not is_strict_mode:
        gating_mode = "OUT_OF_DOMAIN"
        items = _bucket_sort(strict_items) + _bucket_sort(neighbor_items) + _bucket_sort(out_items)
    elif strict_count >= MIN_STRICT:
        gating_mode = "IN_DOMAIN"
        items = _bucket_sort(strict_items)
    else:
        # Auto-widen to neighbors
        gating_mode = "STRICT_PLUS_NEIGHBORS"
        items = _bucket_sort(strict_items) + _bucket_sort(neighbor_items)

    coverage_after = len(items)
    suggest_out_of_domain = (
        is_strict_mode
        and coverage_after < MIN_RESULTS
        and out_count > 0
    )
    out_of_domain_count = out_count

    total_matched = len(items)

    cluster_distribution_top20: Dict[str, int] = {}
    for item in items[:20]:
        key = item.offer_cluster or "UNKNOWN"
        cluster_distribution_top20[key] = cluster_distribution_top20.get(key, 0) + 1

    suspicious_items = [item for item in items if item.coherence == "suspicious"]
    suspicious_count = len(suspicious_items)
    suspicious_sample_ids = [item.offer_id for item in suspicious_items[:5]]

    items = items[: req.limit]

    # OBS: INBOX_DOMAIN_LAYER_APPLIED
    top_generic_skills = sorted(
        freq_table.items(), key=lambda x: (-x[1], x[0])
    )[:5] if freq_table else []
    top_clusters = sorted(cluster_distribution_top20.items(), key=lambda x: (-x[1], x[0]))[:3]
    logger.info("INBOX_DOMAIN_LAYER_APPLIED %s", json.dumps({
        "event": "INBOX_DOMAIN_LAYER_APPLIED",
        "profile_id": req.profile_id,
        "profile_cluster": profile_cluster,
        "domain_mode": gating_mode,
        "strict_count": strict_count,
        "neighbor_count": neighbor_count,
        "out_count": out_count,
        "top_generic_skills": [s for s, _ in top_generic_skills],
        "total_offers_db": offer_count,
    }))
    if suspicious_count > 0:
        logger.info("SUSPICIOUS_HIGH_SCORE %s", json.dumps({
            "event": "SUSPICIOUS_HIGH_SCORE",
            "count": suspicious_count,
            "sample_offer_ids": suspicious_sample_ids,
            "profile_cluster": profile_cluster,
            "domain_mode": gating_mode,
        }))

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
            debug, _matched, _missing, near_matches, near_summary = _unpack_explain_debug(
                _explain_debug[item.offer_id]
            )
            item.explain = _build_explain(
                debug,
                item.rome_competences,
                near_matches=near_matches,
                near_match_summary=near_summary,
            )
            if item.explain.matched_core or item.explain.missing_core:
                item.core_matched_count = len(item.explain.matched_core)
                item.core_total_count = len(item.explain.matched_core) + len(item.explain.missing_core)
            else:
                matched_core = [s for s in item.explain.matched_full if s.weighted]
                missing_core = [s for s in item.explain.missing_full if s.weighted]
                item.core_matched_count = len(matched_core)
                item.core_total_count = len(matched_core) + len(missing_core)

        # Compass signal (always computed, compact — no scoring impact)
        _c_stash = _explain_debug.get(item.offer_id)
        if _c_stash is not None:
            _match_debug_c = _c_stash[0]
            _offer_c = offer_lookup.get(item.offer_id, {})
            _offer_uris: List[str] = _offer_c.get("skills_uri") or []

            # Build URI→label from skills_display
            _label_map: Dict[str, str] = {}
            for _sd in (_offer_c.get("skills_display") or []):
                if isinstance(_sd, dict) and _sd.get("uri"):
                    _label_map[str(_sd["uri"])] = str(_sd.get("label") or _sd["uri"])

            if _offer_uris:
                # URI scoring: matched = profile_uris ∩ offer_uris
                _prof_uris: Set[str] = set(extracted.skills_uri)
                _off_uri_set: Set[str] = set(_offer_uris)
                _match_uri_set: Set[str] = _prof_uris & _off_uri_set
                _compass_offer_skills = [
                    SkillRef(uri=u, label=_label_map.get(u, u)) for u in _offer_uris
                ]
                _compass_matched_skills = [
                    SkillRef(uri=u, label=_label_map.get(u, u)) for u in _match_uri_set
                ]
            else:
                # Label scoring fallback
                _s_dbg = _match_debug_c.get("skills", {}) if isinstance(_match_debug_c, dict) else {}
                _m_lbls: List[str] = (_s_dbg.get("matched") or []) if isinstance(_s_dbg, dict) else []
                _miss_lbls: List[str] = (_s_dbg.get("missing") or []) if isinstance(_s_dbg, dict) else []
                _compass_offer_skills = [SkillRef(uri=None, label=l) for l in _m_lbls + _miss_lbls]
                _compass_matched_skills = [SkillRef(uri=None, label=l) for l in _m_lbls]

            _compass_full = build_explain_payload_v1(
                score_core=item.score_raw or (item.score / 100.0),
                matched_skills=_compass_matched_skills,
                offer_skills=_compass_offer_skills,
                offer_text=_offer_c.get("description") or "",
                domain_bucket=item.domain_bucket or "out",
                idf_map=engine.idf_table,
                cfg=_inbox_cfg,
                offer_cluster=item.offer_cluster,
                cluster_idf_table=_cluster_idf,
            )
            _compact = build_explain_compact(_compass_full, len(_offer_uris))
            item.explain_v1 = CompassExplainCompact(**_compact.model_dump())
            item.match_strength = _map_match_strength(item.explain_v1.confidence if item.explain_v1 else None)
            item.dominant_reason = _derive_dominant_reason(
                item.explain_v1.confidence if item.explain_v1 else None,
                near_match_count=int(item.near_match_count or 0),
                rare_signal_level=item.explain_v1.rare_signal_level if item.explain_v1 else None,
            )
            _profile_labels = profile_payload.get("matching_skills") or profile_payload.get("skills") or []
            _offer_labels = _offer_c.get("skills_display") or _offer_c.get("skills") or []
            _offer_labels = _extract_skill_labels(_offer_labels)
            _apply_front_explanation(
                item,
                match_debug=_match_debug_c,
                confidence=item.explain_v1.confidence if item.explain_v1 else None,
                profile_labels=_profile_labels,
                offer_labels=_offer_labels,
            )
            _apply_offer_intelligence(
                item,
                offer_payload=_offer_c,
                precomputed_payload=offer_intelligence_map.get(item.offer_id),
                allow_recompute=False,
            )
            _apply_semantic_explainability(
                item,
                profile_intelligence=profile_intelligence,
            )
            _apply_scoring_v2(
                item,
                profile_intelligence=profile_intelligence,
            )
            _apply_scoring_v3(
                item,
                profile_intelligence=profile_intelligence,
            )

    # Optional sector-aware rerank (no score change — secondary sort only)
    if _rerank_enabled and items:
        _conf_rank = {"HIGH": 2, "MED": 1, "LOW": 0}
        _sig_rank = {"HIGH": 2, "MED": 1, "LOW": 0}
        _bucket_rank = {"strict": 2, "neighbor": 1, "out": 0}

        def _rerank_key(item: InboxItem) -> tuple:
            ev1 = item.explain_v1
            return (
                -_bucket_rank.get(item.domain_bucket or "out", 0),
                -item.score,
                -_conf_rank.get(ev1.confidence if ev1 else "LOW", 0),
                -_sig_rank.get(ev1.rare_signal_level if ev1 else "LOW", 0),
                -(ev1.sector_signal if ev1 and ev1.sector_signal is not None else 0.0),
                item.offer_id,  # stable tie-break
            )

        items = sorted(items, key=_rerank_key)

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

    meta = InboxMeta(
        profile_cluster=profile_cluster,
        gating_mode=gating_mode,
        coverage_before=coverage_before,
        coverage_after=coverage_after,
        suggest_out_of_domain=suggest_out_of_domain,
        out_of_domain_count=out_of_domain_count,
        cluster_distribution_top20=cluster_distribution_top20,
        strict_count=strict_count,
        neighbor_count=neighbor_count,
        out_count=out_count,
    )

    return InboxResponse(
        profile_id=req.profile_id,
        items=items,
        total_matched=total_matched,
        total_decided=len(decided_ids),
        meta=meta,
    )


def _get_inbox_filtered(
    *,
    req: InboxRequest,
    profile_payload: Dict,
    domain_mode: str,
    q_company: Optional[str],
    country: Optional[str],
    city: Optional[str],
    contract_type: Optional[str],
    published_from: Optional[str],
    published_to: Optional[str],
    domain_bucket: Optional[str],
    min_score: Optional[int],
    confidence: Optional[str],
    rare_level: Optional[str],
    sector_level: Optional[str],
    has_tool_unspecified: Optional[bool],
    page: Optional[int],
    page_size: Optional[int],
    sort: Optional[str],
) -> InboxResponse:
    t0 = time.perf_counter()
    decided_ids = _load_decided_ids(req.profile_id)
    t_decisions = time.perf_counter()
    profile_intelligence = _extract_profile_intelligence_payload(profile_payload)

    # Parse dates (inclusive end-date via next-day boundary)
    published_from_iso = None
    published_to_iso = None
    if published_from:
        published_from_iso = _parse_date_param(published_from).isoformat()
    if published_to:
        published_to_iso = (_parse_date_param(published_to) + timedelta(days=1)).isoformat()

    contract_type_norm = _normalize_contract_type(contract_type)
    source_filter = "business_france" if contract_type_norm == "VIE" else None

    min_score_effective = min_score if min_score is not None else req.min_score
    page_effective = page or 1
    page_size_effective = page_size or req.limit
    sort_mode = sort or "published_desc"

    # Load full catalog for IDF stability (no score changes)
    catalog_full = _load_catalog_offers()
    t_catalog = time.perf_counter()
    if not catalog_full:
        return InboxResponse(
            profile_id=req.profile_id,
            items=[],
            total_matched=0,
            total_decided=len(decided_ids),
            total_estimate=0,
            applied_filters=None,
            page=page_effective,
            page_size=page_size_effective,
        )

    # Build engine + extract profile
    engine = _build_or_get_engine(catalog_full)
    extracted = extract_profile(profile_payload)
    t_profile = time.perf_counter()
    profile_cluster = detect_profile_cluster(list(getattr(extracted, "skills", []))).get("dominant_cluster")

    freq_table = load_generic_skill_table()
    offer_count = get_offer_count()

    # Compass config + cluster IDF (cached, built once per catalog load)
    _inbox_cfg = get_signal_cfg()
    _sector_enabled = _inbox_cfg.get("sector_signal_enabled", False)
    _cluster_idf: Optional[Dict[str, Dict[str, float]]] = (
        _build_or_get_cluster_idf(catalog_full) if _sector_enabled else None
    )

    total_estimate = count_catalog_offers_filtered(
        q_company=q_company,
        country=country,
        city=city,
        source=source_filter,
        published_from=published_from_iso,
        published_to=published_to_iso,
    )

    # Fetch up to 3 pages to fill after post-filters
    candidate_items: List[InboxItem] = []
    _explain_debug: Dict[str, tuple] = {}
    source_map: Dict[str, str] = {}
    offer_lookup: Dict[str, Dict] = {}
    offer_intelligence_map: Dict[str, Dict] = {}
    seen_ids: Set[str] = set()

    max_prefetch_pages = (
        PROFILE_INTELLIGENCE_MAX_PREFETCH_PAGES if profile_intelligence else DEFAULT_MAX_PREFETCH_PAGES
    )
    pages_fetched = 0
    cursor_page = page_effective
    while pages_fetched < max_prefetch_pages and len(candidate_items) < page_size_effective:
        offset = (cursor_page - 1) * page_size_effective
        offers_page = load_catalog_offers_filtered(
            q_company=q_company,
            country=country,
            city=city,
            source=source_filter,
            published_from=published_from_iso,
            published_to=published_to_iso,
            limit=page_size_effective,
            offset=offset,
        )
        if not offers_page:
            break

        items_page, explain_page, source_page, lookup_page, intelligence_page, gate_rejections_page = _score_offers(
            offers_page,
            decided_ids=decided_ids,
            engine=engine,
            extracted=extracted,
            profile_payload=profile_payload,
            profile_intelligence=profile_intelligence,
            explain_enabled=req.explain,
            min_score=min_score_effective,
            freq_table=freq_table,
            offer_count=offer_count,
            contract_type_norm=contract_type_norm,
        )

        for item in items_page:
            if item.offer_id in seen_ids:
                continue
            seen_ids.add(item.offer_id)
            candidate_items.append(item)

        _explain_debug.update(explain_page)
        source_map.update(source_page)
        offer_lookup.update(lookup_page)
        offer_intelligence_map.update(intelligence_page)
        if _gate_trace_enabled():
            _append_gate_trace(gate_rejections_page)

        pages_fetched += 1
        cursor_page += 1

    t_scoring = time.perf_counter()

    # Domain gating without reordering (stable pagination)
    gated_items, gating_meta = _apply_domain_gating(
        candidate_items,
        profile_cluster=profile_cluster,
        domain_mode=domain_mode,
        sort_buckets=False,
    )

    needs_compass_filter_eval = bool(
        confidence
        or rare_level
        or sector_level
        or has_tool_unspecified is not None
    )

    if needs_compass_filter_eval:
        for item in gated_items:
            _c_stash = _explain_debug.get(item.offer_id)
            if _c_stash is None:
                continue
            _match_debug_c = _c_stash[0]
            _offer_c = offer_lookup.get(item.offer_id, {})
            _offer_uris: List[str] = _offer_c.get("skills_uri") or []

            _label_map: Dict[str, str] = {}
            for _sd in (_offer_c.get("skills_display") or []):
                if isinstance(_sd, dict) and _sd.get("uri"):
                    _label_map[str(_sd["uri"])] = str(_sd.get("label") or _sd["uri"])

            if _offer_uris:
                _prof_uris: Set[str] = set(extracted.skills_uri)
                _off_uri_set: Set[str] = set(_offer_uris)
                _match_uri_set: Set[str] = _prof_uris & _off_uri_set
                _compass_offer_skills = [
                    SkillRef(uri=u, label=_label_map.get(u, u)) for u in _offer_uris
                ]
                _compass_matched_skills = [
                    SkillRef(uri=u, label=_label_map.get(u, u)) for u in _match_uri_set
                ]
            else:
                _s_dbg = _match_debug_c.get("skills", {}) if isinstance(_match_debug_c, dict) else {}
                _m_lbls: List[str] = (_s_dbg.get("matched") or []) if isinstance(_s_dbg, dict) else []
                _miss_lbls: List[str] = (_s_dbg.get("missing") or []) if isinstance(_s_dbg, dict) else []
                _compass_offer_skills = [SkillRef(uri=None, label=l) for l in _m_lbls + _miss_lbls]
                _compass_matched_skills = [SkillRef(uri=None, label=l) for l in _m_lbls]

            _compass_full = build_explain_payload_v1(
                score_core=item.score_raw or (item.score / 100.0),
                matched_skills=_compass_matched_skills,
                offer_skills=_compass_offer_skills,
                offer_text=_offer_c.get("description") or "",
                domain_bucket=item.domain_bucket or "out",
                idf_map=engine.idf_table,
                cfg=_inbox_cfg,
                offer_cluster=item.offer_cluster,
                cluster_idf_table=_cluster_idf,
            )
            _compact = build_explain_compact(_compass_full, len(_offer_uris))
            item.explain_v1 = CompassExplainCompact(**_compact.model_dump())

        filtered_items = _apply_compass_filters(
            gated_items,
            domain_bucket=domain_bucket,
            confidence=confidence,
            rare_level=rare_level,
            sector_level=sector_level,
            has_tool_unspecified=has_tool_unspecified,
        )
    else:
        filtered_items = gated_items

    # Optional sort on filtered set
    if sort_mode == "score_desc":
        filtered_items = sorted(
            filtered_items,
            key=lambda i: (-i.score, -(i.signal_score or 0.0), i.offer_id),
        )
    elif sort_mode == "confidence_desc":
        rank = {"HIGH": 2, "MED": 1, "LOW": 0}
        filtered_items = sorted(
            filtered_items,
            key=lambda i: (
                -rank.get(i.explain_v1.confidence if i.explain_v1 else "LOW", 0),
                -i.score,
                i.offer_id,
            ),
        )

    total_matched = len(filtered_items)
    items = filtered_items[:page_size_effective]

    for item in items:
        _c_stash = _explain_debug.get(item.offer_id)
        _match_debug_c = _c_stash[0] if _c_stash is not None else {}
        offer = offer_lookup.get(item.offer_id, {})
        _offer_uris: List[str] = offer.get("skills_uri") or []
        _label_map: Dict[str, str] = {}
        for _sd in (offer.get("skills_display") or []):
            if isinstance(_sd, dict) and _sd.get("uri"):
                _label_map[str(_sd["uri"])] = str(_sd.get("label") or _sd["uri"])
        if _offer_uris:
            _prof_uris: Set[str] = set(extracted.skills_uri)
            _off_uri_set: Set[str] = set(_offer_uris)
            _match_uri_set: Set[str] = _prof_uris & _off_uri_set
            _compass_offer_skills = [SkillRef(uri=u, label=_label_map.get(u, u)) for u in _offer_uris]
            _compass_matched_skills = [SkillRef(uri=u, label=_label_map.get(u, u)) for u in _match_uri_set]
        else:
            _s_dbg = _match_debug_c.get("skills", {}) if isinstance(_match_debug_c, dict) else {}
            _m_lbls: List[str] = (_s_dbg.get("matched") or []) if isinstance(_s_dbg, dict) else []
            _miss_lbls: List[str] = (_s_dbg.get("missing") or []) if isinstance(_s_dbg, dict) else []
            _compass_offer_skills = [SkillRef(uri=None, label=l) for l in _m_lbls + _miss_lbls]
            _compass_matched_skills = [SkillRef(uri=None, label=l) for l in _m_lbls]
        _compass_full = build_explain_payload_v1(
            score_core=item.score_raw or (item.score / 100.0),
            matched_skills=_compass_matched_skills,
            offer_skills=_compass_offer_skills,
            offer_text=offer.get("description") or "",
            domain_bucket=item.domain_bucket or "out",
            idf_map=engine.idf_table,
            cfg=_inbox_cfg,
            offer_cluster=item.offer_cluster,
            cluster_idf_table=_cluster_idf,
        )
        _compact = build_explain_compact(_compass_full, len(_offer_uris))
        item.explain_v1 = CompassExplainCompact(**_compact.model_dump())
        item.match_strength = _map_match_strength(item.explain_v1.confidence if item.explain_v1 else None)
        item.dominant_reason = _derive_dominant_reason(
            item.explain_v1.confidence if item.explain_v1 else None,
            near_match_count=int(item.near_match_count or 0),
            rare_signal_level=item.explain_v1.rare_signal_level if item.explain_v1 else None,
        )
        _profile_labels = profile_payload.get("matching_skills") or profile_payload.get("skills") or []
        _offer_labels = offer.get("skills_display") or offer.get("skills") or []
        _offer_labels = _extract_skill_labels(_offer_labels)
        _apply_front_explanation(
            item,
            match_debug=_match_debug_c,
            confidence=item.explain_v1.confidence if item.explain_v1 else None,
            profile_labels=_profile_labels,
            offer_labels=_offer_labels,
        )
        _apply_offer_intelligence(
            item,
            offer_payload=offer,
            precomputed_payload=offer_intelligence_map.get(item.offer_id),
            allow_recompute=False,
        )
        _apply_semantic_explainability(
            item,
            profile_intelligence=profile_intelligence,
        )
        _apply_scoring_v2(
            item,
            profile_intelligence=profile_intelligence,
        )
        _apply_scoring_v3(
            item,
            profile_intelligence=profile_intelligence,
        )

    # Observability (domain layer)
    top_generic_skills = sorted(freq_table.items(), key=lambda x: (-x[1], x[0]))[:5] if freq_table else []
    top_clusters = sorted(
        (gating_meta.get("cluster_distribution_top20") or {}).items(),
        key=lambda x: (-x[1], x[0]),
    )[:3]
    logger.info(
        "INBOX_DOMAIN_LAYER_APPLIED %s",
        json.dumps(
            {
                "event": "INBOX_DOMAIN_LAYER_APPLIED",
                "profile_id": req.profile_id,
                "profile_cluster": profile_cluster,
                "domain_mode": gating_meta.get("gating_mode"),
                "strict_count": gating_meta.get("strict_count"),
                "neighbor_count": gating_meta.get("neighbor_count"),
                "out_count": gating_meta.get("out_count"),
                "top_generic_skills": [s for s, _ in top_generic_skills],
                "top_clusters": [c for c, _ in top_clusters],
                "total_offers_db": offer_count,
            }
        ),
    )
    if gating_meta.get("suspicious_count", 0) > 0:
        logger.info(
            "SUSPICIOUS_HIGH_SCORE %s",
            json.dumps(
                {
                    "event": "SUSPICIOUS_HIGH_SCORE",
                    "count": gating_meta.get("suspicious_count"),
                    "sample_offer_ids": gating_meta.get("suspicious_sample_ids"),
                    "profile_cluster": profile_cluster,
                    "domain_mode": gating_meta.get("gating_mode"),
                }
            ),
        )

    # ROME enrichment only for final items
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

        inferred = inferred_rome.get(item.offer_id)
        if inferred:
            item.rome_inferred = RomeInferred(**inferred)
        else:
            item.rome_inferred = None

        if req.explain and item.offer_id in _explain_debug:
            debug, _matched, _missing, near_matches, near_summary = _unpack_explain_debug(
                _explain_debug[item.offer_id]
            )
            item.explain = _build_explain(
                debug,
                item.rome_competences,
                near_matches=near_matches,
                near_match_summary=near_summary,
            )

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
            len(catalog_full),
            total_matched,
            len(decided_ids),
        )

    applied_filters = {
        "q_company": q_company,
        "country": country,
        "city": city,
        "contract_type": contract_type_norm,
        "published_from": published_from,
        "published_to": published_to,
        "domain_bucket": domain_bucket,
        "min_score": min_score_effective,
        "confidence": confidence,
        "rare_level": rare_level,
        "sector_level": sector_level,
        "has_tool_unspecified": has_tool_unspecified,
        "sort": sort_mode,
    }

    if _debug_inbox_filters_enabled():
        logger.info(
            "INBOX_FILTERS %s",
            json.dumps(
                {
                    "event": "INBOX_FILTERS",
                    "profile_id": req.profile_id,
                    "filters": applied_filters,
                    "page": page_effective,
                    "page_size": page_size_effective,
                    "candidate": len(candidate_items),
                    "returned": len(items),
                    "total_estimate": total_estimate,
                }
            ),
        )

    meta = InboxMeta(
        profile_cluster=profile_cluster,
        gating_mode=gating_meta.get("gating_mode"),
        coverage_before=gating_meta.get("coverage_before"),
        coverage_after=gating_meta.get("coverage_after"),
        suggest_out_of_domain=gating_meta.get("suggest_out_of_domain"),
        out_of_domain_count=gating_meta.get("out_of_domain_count"),
        cluster_distribution_top20=gating_meta.get("cluster_distribution_top20"),
        strict_count=gating_meta.get("strict_count"),
        neighbor_count=gating_meta.get("neighbor_count"),
        out_count=gating_meta.get("out_count"),
    )

    return InboxResponse(
        profile_id=req.profile_id,
        items=items,
        total_matched=total_matched,
        total_decided=len(decided_ids),
        total_estimate=total_estimate,
        applied_filters=applied_filters,
        page=page_effective,
        page_size=page_size_effective,
        meta=meta,
    )


@router.post("/offers/{offer_id}/decision", summary="Record a decision on an offer")
async def post_decision(
    offer_id: str,
    req: DecisionRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> DecisionResponse:
    """
    Upsert a SHORTLISTED or DISMISSED decision.

    Always writes to offer_decisions (inbox filter — backward compat).
    When authenticated, also writes a compat row to application_tracker:
      SHORTLISTED → saved
      DISMISSED   → archived
    """
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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

        # ── Compat layer: mirror decision into application_tracker ────────────
        # offer_decisions remains the source of truth for inbox filtering.
        # application_tracker is the user-facing candidature tracker.
        tracker_user_id = current_user.user_id if current_user is not None else "__anonymous__"
        _decision_status_map = {
            "SHORTLISTED": "saved",
            "DISMISSED": "archived",
        }
        tracker_status = _decision_status_map.get(req.status)
        if tracker_status:
            try:
                existing = conn.execute(
                    "SELECT id, status FROM application_tracker "
                    "WHERE offer_id = ? AND user_id = ?",
                    (offer_id, tracker_user_id),
                ).fetchone()

                if existing is None:
                    app_id = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO application_tracker "
                        "(id, user_id, offer_id, status, source, note, "
                        "created_at, updated_at, last_status_change_at) "
                        "VALUES (?, ?, ?, ?, 'assisted', ?, ?, ?, ?)",
                        (
                            app_id,
                            tracker_user_id,
                            offer_id,
                            tracker_status,
                            req.note,
                            now, now, now,
                        ),
                    )
                    conn.execute(
                        "INSERT INTO application_status_history "
                        "(id, application_id, from_status, to_status, changed_at) "
                        "VALUES (?, ?, NULL, ?, ?)",
                        (str(uuid.uuid4()), app_id, tracker_status, now),
                    )
                else:
                    app_id = existing["id"]
                    old_status = existing["status"]
                    if old_status != tracker_status:
                        conn.execute(
                            "UPDATE application_tracker SET "
                            "status = ?, source = 'assisted', note = COALESCE(?, note), "
                            "updated_at = ?, last_status_change_at = ? "
                            "WHERE id = ?",
                            (tracker_status, req.note, now, now, app_id),
                        )
                        conn.execute(
                            "INSERT INTO application_status_history "
                            "(id, application_id, from_status, to_status, changed_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), app_id, old_status, tracker_status, now),
                        )
                conn.commit()
            except Exception as exc:
                logger.warning(
                    "decision_compat_tracker_error offer_id=%s error=%s",
                    offer_id,
                    type(exc).__name__,
                )
        # ── End compat layer ──────────────────────────────────────────────────

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
