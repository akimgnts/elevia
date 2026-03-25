from __future__ import annotations

import copy
import json
from typing import Any, Dict, Iterable, List, Sequence
import csv
import io
import re

from compass.canonical.canonical_store import get_canonical_store
from compass.contracts import OfferDescriptionStructuredV1
from compass.pipeline.structured_extraction_stage import run_structured_extraction_stage
from compass.profile.profile_intelligence import (
    ROLE_BLOCKS,
    _BLOCK_DISPLAY,
    _BLOCK_KEYWORDS,
    _BLOCK_PRIMARY_ROLE,
    _BLOCK_SECONDARY_ROLE,
    _BLOCK_TO_DOMAINS,
    _CLUSTER_TO_BLOCK_WEIGHTS,
    _DOMAIN_KEYWORDS,
    _DOMAIN_TO_BLOCK,
    _ROLE_FAMILY_TO_BLOCK,
    _TITLE_BLOCK_HINTS,
    _TITLE_FAMILY_TO_BLOCK,
    _add_domain_votes,
    _add_text_votes,
    _count_anchor_hits,
    _dominant_domain,
    _domain_penalty_for_block,
    _extract_signal_text_from_unit,
    _infer_title_block,
    _is_generic_signal,
    _normalize,
    _score_text_against_block,
    _select_top_profile_signals,
    _sorted_block_scores,
    _tool_like,
    _BlockAccumulator,
    _BUSINESS_ANALYSIS_ANCHORS,
    _DATA_ANCHORS,
    _DATA_SUPPORT_SIGNALS,
    _FINANCE_ANCHORS,
    _MARKETING_ANCHORS,
    _SUPPLY_CHAIN_ANCHORS,
)
from offer.offer_description_structurer import structure_offer_description
from compass.text_structurer import structure_offer_text_v1
from offer.offer_cluster import detect_offer_cluster
from .offer_parse_pipeline import build_offer_canonical_representation

_MAX_TOP_SIGNALS = 5
_MAX_REQUIRED = 5
_MAX_OPTIONAL = 4
_MAX_SECONDARY = 2
_MAX_ROLE_HYPOTHESES = 3
_INTELLIGENCE_CACHE_CAP = 256
_INTELLIGENCE_CACHE: Dict[str, Dict[str, Any]] = {}

_REQUIRED_MARKERS = (
    "requis",
    "requise",
    "required",
    "must",
    "maitrise",
    "maîtrise",
    "experience en",
    "experience",
    "compétences",
    "competences",
    "profil recherche",
    "profil recherché",
    "you have",
)
_OPTIONAL_MARKERS = (
    "souhaite",
    "souhaitee",
    "souhaitee",
    "souhaité",
    "apprecie",
    "apprécié",
    "apprécie",
    "bonus",
    "plus",
    "nice to have",
    "would be a plus",
    "serait un plus",
)
_REQUIREMENT_SPLIT_RE = re.compile(r"\s*,\s*|\s*;\s*")
_TOOL_OPTIONAL_BLOCKLIST = {"excel", "power bi", "sql", "python", "word", "powerpoint"}
_GENERIC_SIGNAL_BLOCKLIST = {
    "communication",
    "gestion de projets",
    "gestion",
    "analyse",
    "projets",
    "processus",
    "anglais",
    "cycle de développement logiciel",
    "volontaire",
    "volontaire international",
    "formation bac",
    "rejoindre",
    "principales",
    "maitrise",
    "premiere experience souhaitee",
    "première expérience souhaitée",
    "anglais professionnel requis",
    "formation bac",
    "amelioration",
    "utiliser un logiciel de tableur",
    "relations",
    "informatique",
    "informatique décisionnelle",
    "ingenieur",
}
_GENERIC_SIGNAL_BLOCKLIST_NORM = {_normalize(value) for value in _GENERIC_SIGNAL_BLOCKLIST}
_GENERIC_SHARED_DOMAINS = {"business", "operations", "project", "communication"}
_GENERIC_DOMAIN_DRIFT = {"business", "operations", "project"}
_BRIDGE_SHARED_DOMAIN_BLOCKLIST = {"data", "software", "it"}
_WEAK_MATCH_DOMAIN_BLOCKLIST = {"data", "software", "it"}
_DATA_SOFTWARE_TITLE_MARKERS = ("data", "bi", "analytics", "analytic", "reporting")
_DATA_SOFTWARE_SIGNAL_MARKERS = (
    "data analysis",
    "business intelligence",
    "sql",
    "query",
    "analytics",
    "reporting",
    "etl",
    "power bi",
    "machine learning",
    "python",
    "dashboard",
)
_ROLE_ADJACENCY = {
    "data_analytics": {"business_analysis", "software_it"},
    "business_analysis": {"finance_ops", "sales_business_dev", "marketing_communication", "supply_chain_ops", "project_ops"},
    "finance_ops": {"business_analysis", "legal_compliance"},
    "legal_compliance": {"finance_ops"},
    "sales_business_dev": {"business_analysis", "marketing_communication"},
    "marketing_communication": {"business_analysis", "sales_business_dev"},
    "hr_ops": {"project_ops"},
    "supply_chain_ops": {"business_analysis", "project_ops"},
    "project_ops": {"business_analysis", "hr_ops", "supply_chain_ops"},
    "software_it": {"data_analytics"},
    "generalist_other": set(),
}
_BRIDGE_ROLE_PAIRS = {
    frozenset({"data_analytics", "finance_ops"}),
    frozenset({"data_analytics", "supply_chain_ops"}),
    frozenset({"data_analytics", "hr_ops"}),
    frozenset({"data_analytics", "marketing_communication"}),
    frozenset({"data_analytics", "sales_business_dev"}),
    frozenset({"data_analytics", "business_analysis"}),
    frozenset({"project_ops", "hr_ops"}),
    frozenset({"project_ops", "supply_chain_ops"}),
}


def _extract_skill_labels(skills_display: Iterable[Any] | None, skills: Iterable[Any] | None) -> List[str]:
    labels: List[str] = []
    seen: set[str] = set()
    for item in list(skills_display or []):
        label = ""
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
        elif isinstance(item, str):
            label = item.strip()
        if not label:
            continue
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    for item in list(skills or []):
        label = str(item or "").strip()
        if not label:
            continue
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def _extract_requirement_skill_candidates(lines: Sequence[str]) -> List[str]:
    candidates: List[str] = []
    seen: set[str] = set()
    for line in lines:
        text = str(line or "").strip()
        if not text:
            continue
        normalized = _normalize(text)
        if normalized.startswith("competences") or normalized.startswith("compétences"):
            _, _, tail = text.partition(":")
            pieces = _REQUIREMENT_SPLIT_RE.split(tail or text)
        else:
            pieces = [text]
        for piece in pieces:
            label = piece.strip(" -•*")
            label = re.sub(r"\b(apprecie|apprécié|souhaite|souhaité|required|requireds?)\b.*$", "", label, flags=re.I).strip(" -,:;")
            key = _normalize(label)
            if not key or key in seen:
                continue
            if len(key.split()) > 5:
                continue
            if key in _GENERIC_SIGNAL_BLOCKLIST_NORM:
                continue
            if key.startswith("formation ") or "experience" in key or "anglais" in key:
                continue
            seen.add(key)
            candidates.append(label)
    return candidates


def _infer_offer_title_block(title: str) -> tuple[str | None, float]:
    key = _normalize(title)
    if not key:
        return None, 0.0
    exact_patterns: tuple[tuple[str, str, float], ...] = (
        ("legal counsel", "legal_compliance", 0.99),
        ("counsel", "legal_compliance", 0.95),
        ("lawyer", "legal_compliance", 0.95),
        ("juridique", "legal_compliance", 0.98),
        ("compliance", "legal_compliance", 0.98),
        ("financial controller", "finance_ops", 0.99),
        ("controleur financier", "finance_ops", 0.99),
        ("contrôleur financier", "finance_ops", 0.99),
        ("finance", "finance_ops", 0.98),
        ("controle de gestion", "finance_ops", 0.99),
        ("commerce", "sales_business_dev", 0.98),
        ("commercial", "sales_business_dev", 0.96),
        ("business development", "sales_business_dev", 0.98),
        ("supply chain", "supply_chain_ops", 0.99),
        ("logistique", "supply_chain_ops", 0.97),
        ("transport", "supply_chain_ops", 0.95),
        ("rh", "hr_ops", 0.98),
        ("human resources", "hr_ops", 0.98),
        ("marketing", "marketing_communication", 0.98),
        ("communication", "marketing_communication", 0.98),
        ("engineering", "software_it", 0.94),
        ("ingenieur", "software_it", 0.94),
        ("informatique", "software_it", 0.97),
        ("data", "data_analytics", 0.96),
        ("bi", "data_analytics", 0.94),
    )
    for marker, block, confidence in exact_patterns:
        if re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", key):
            return block, confidence
    return _infer_title_block(title, None)


def _clean_signal_list(values: Sequence[str]) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for value in values:
        label = str(value or "").strip(" -•*")
        key = _normalize(label)
        if not key or key in seen:
            continue
        if key in _GENERIC_SIGNAL_BLOCKLIST_NORM:
            continue
        if "experience" in key or key.startswith("formation ") or key.startswith("maitrise "):
            continue
        seen.add(key)
        cleaned.append(label)
    return cleaned


def _role_neighbors(block: str) -> set[str]:
    return set(_ROLE_ADJACENCY.get(block, set()))


def _is_bridge_role_pair(profile_block: str, offer_block: str) -> bool:
    if not profile_block or not offer_block or profile_block == offer_block:
        return False
    return frozenset({profile_block, offer_block}) in _BRIDGE_ROLE_PAIRS


def _signal_lists_for_gate(
    profile_intelligence: Dict[str, Any] | None,
    offer_intelligence: Dict[str, Any] | None,
) -> tuple[List[str], List[str], List[str]]:
    profile_signals = [
        str(value).strip()
        for value in list((profile_intelligence or {}).get("top_profile_signals") or [])
        if str(value).strip()
    ]
    offer_top = [
        str(value).strip()
        for value in list((offer_intelligence or {}).get("top_offer_signals") or [])
        if str(value).strip()
    ]
    offer_required = [
        str(value).strip()
        for value in list((offer_intelligence or {}).get("required_skills") or [])
        if str(value).strip()
    ]
    return profile_signals[:8], offer_top[:8], offer_required[:8]


def _signal_keys_overlap(left: str, right: str) -> bool:
    left_key = _normalize(left)
    right_key = _normalize(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    if len(left_key) >= 5 and len(right_key) >= 5:
        if left_key in right_key or right_key in left_key:
            return True
    return False


def _signal_overlap_details(
    profile_intelligence: Dict[str, Any] | None,
    offer_intelligence: Dict[str, Any] | None,
) -> Dict[str, Any]:
    profile_signals, offer_top, offer_required = _signal_lists_for_gate(
        profile_intelligence,
        offer_intelligence,
    )
    overlap_labels: List[str] = []
    required_overlap = 0
    top_overlap = 0
    seen_overlap: set[str] = set()

    for profile_signal in profile_signals:
        for offer_signal in [*offer_required, *offer_top]:
            if not _signal_keys_overlap(profile_signal, offer_signal):
                continue
            key = _normalize(profile_signal) or _normalize(offer_signal)
            if key and key not in seen_overlap:
                overlap_labels.append(profile_signal)
                seen_overlap.add(key)
            if offer_signal in offer_required:
                required_overlap += 1
            else:
                top_overlap += 1
            break

    required_overlap = min(required_overlap, len(offer_required))
    top_overlap = min(top_overlap, len(offer_top))
    overlap_count = len(overlap_labels)
    strong_signal_overlap = required_overlap >= 1 or overlap_count >= 2

    return {
        "matched_signals": overlap_labels,
        "overlap_count": overlap_count,
        "required_overlap_count": required_overlap,
        "top_overlap_count": top_overlap,
        "strong_signal_overlap": strong_signal_overlap,
    }


def _role_supported_domains(intelligence: Dict[str, Any] | None) -> set[str]:
    supported: set[str] = set()
    if not isinstance(intelligence, dict):
        return supported
    blocks = [
        str(intelligence.get("dominant_role_block") or "").strip(),
        *[
            str(value).strip()
            for value in list(intelligence.get("secondary_role_blocks") or [])
            if str(value).strip()
        ],
    ]
    for block in blocks:
        supported.update(_BLOCK_TO_DOMAINS.get(block, ()))
    return supported


def _contains_signal_marker(value: str, markers: Sequence[str]) -> bool:
    key = _normalize(value)
    if not key:
        return False
    return any(marker in key for marker in markers)


def _data_domain_score(offer_intelligence: Dict[str, Any] | None) -> float:
    debug = ((offer_intelligence or {}).get("debug") or {}) if isinstance(offer_intelligence, dict) else {}
    domain_scores = debug.get("domain_scores") or []
    for item in domain_scores:
        if _normalize((item or {}).get("domain")) == "data":
            try:
                return float((item or {}).get("score") or 0.0)
            except Exception:
                return 0.0
    return 0.0


def _is_valid_data_software_bridge(
    *,
    profile_intelligence: Dict[str, Any] | None,
    offer_intelligence: Dict[str, Any] | None,
    shared_domains: Sequence[str],
) -> bool:
    profile_block = str((profile_intelligence or {}).get("dominant_role_block") or "").strip()
    offer_block = str((offer_intelligence or {}).get("dominant_role_block") or "").strip()
    if profile_block != "data_analytics" or offer_block != "software_it":
        return False
    if "data" not in {_normalize(domain) for domain in shared_domains}:
        return False

    debug = (offer_intelligence or {}).get("debug") or {}
    title = str((((debug.get("title_probe") or {}).get("raw_title")) or "")).strip()
    title_has_data_anchor = _contains_signal_marker(title, _DATA_SOFTWARE_TITLE_MARKERS)

    top_signals = [
        str(value).strip()
        for value in list((offer_intelligence or {}).get("top_offer_signals") or [])
        if str(value).strip()
    ]
    required_skills = [
        str(value).strip()
        for value in list((offer_intelligence or {}).get("required_skills") or [])
        if str(value).strip()
    ]

    explicit_top = [signal for signal in top_signals if _contains_signal_marker(signal, _DATA_SOFTWARE_SIGNAL_MARKERS)]
    explicit_required = [signal for signal in required_skills if _contains_signal_marker(signal, _DATA_SOFTWARE_SIGNAL_MARKERS)]
    data_domain_score = _data_domain_score(offer_intelligence)

    if title_has_data_anchor and data_domain_score >= 2.5:
        return True
    if data_domain_score >= 3.0 and len(explicit_required) >= 1 and len(set(map(_normalize, [*explicit_top, *explicit_required]))) >= 2:
        return True
    return False


def classify_role_match(
    *,
    profile_intelligence: Dict[str, Any] | None,
    offer_intelligence: Dict[str, Any] | None,
) -> str:
    if not isinstance(profile_intelligence, dict) or not isinstance(offer_intelligence, dict):
        return "unknown"

    profile_block = str(profile_intelligence.get("dominant_role_block") or "").strip()
    offer_block = str(offer_intelligence.get("dominant_role_block") or "").strip()
    if not profile_block or not offer_block:
        return "unknown"
    if profile_block == offer_block:
        return "strong"

    profile_secondary = {
        str(value).strip()
        for value in list(profile_intelligence.get("secondary_role_blocks") or [])
        if str(value).strip()
    }
    offer_secondary = {
        str(value).strip()
        for value in list(offer_intelligence.get("secondary_role_blocks") or [])
        if str(value).strip()
    }
    if offer_block in profile_secondary or profile_block in offer_secondary or (profile_secondary & offer_secondary):
        return "acceptable"
    if offer_block in _role_neighbors(profile_block) or profile_block in _role_neighbors(offer_block):
        return "weak"
    return "invalid"


def is_role_domain_compatible(
    *,
    profile_intelligence: Dict[str, Any] | None,
    offer_intelligence: Dict[str, Any] | None,
) -> bool:
    return bool(
        evaluate_role_domain_gate(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
        ).get("compatible")
    )


def evaluate_role_domain_gate(
    *,
    profile_intelligence: Dict[str, Any] | None,
    offer_intelligence: Dict[str, Any] | None,
) -> Dict[str, Any]:
    role_match = classify_role_match(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    )
    profile_block = str((profile_intelligence or {}).get("dominant_role_block") or "").strip()
    offer_block = str((offer_intelligence or {}).get("dominant_role_block") or "").strip()
    profile_secondary = {
        str(value).strip()
        for value in list((profile_intelligence or {}).get("secondary_role_blocks") or [])
        if str(value).strip()
    }
    offer_secondary = {
        str(value).strip()
        for value in list((offer_intelligence or {}).get("secondary_role_blocks") or [])
        if str(value).strip()
    }

    profile_domain_list = [
        _normalize(value)
        for value in list((profile_intelligence or {}).get("dominant_domains") or [])
        if _normalize(value)
    ]
    offer_domain_list = [
        _normalize(value)
        for value in list((offer_intelligence or {}).get("dominant_domains") or [])
        if _normalize(value)
    ]
    profile_domains = set(profile_domain_list)
    offer_domains = set(offer_domain_list)
    profile_role_supported_domains = _role_supported_domains(profile_intelligence)
    offer_role_supported_domains = _role_supported_domains(offer_intelligence)
    shared_domains = sorted(profile_domains & offer_domains)
    non_generic_shared_domains = [domain for domain in shared_domains if domain not in _GENERIC_SHARED_DOMAINS]
    weak_match_shared_domains = [
        domain
        for domain in non_generic_shared_domains
        if domain not in _WEAK_MATCH_DOMAIN_BLOCKLIST
    ]
    bridge_shared_domains = [
        domain
        for domain in non_generic_shared_domains
        if domain not in _BRIDGE_SHARED_DOMAIN_BLOCKLIST
    ]
    primary_shared_domains = sorted(set(profile_domain_list[:2]) & set(offer_domain_list[:2]))
    secondary_supported_domains = sorted(
        (profile_domains & offer_role_supported_domains)
        | (offer_domains & profile_role_supported_domains)
    )
    meaningful_secondary_supported_domains = [
        domain for domain in secondary_supported_domains if domain not in _GENERIC_SHARED_DOMAINS
    ]
    signal_overlap = _signal_overlap_details(profile_intelligence, offer_intelligence)
    bridge_pair = _is_bridge_role_pair(profile_block, offer_block)
    effective_role_match = role_match
    if role_match == "invalid" and bridge_pair and bridge_shared_domains:
        effective_role_match = "weak"
    compatible = False
    rejection_reason = None
    allow_reason = None

    if role_match == "unknown":
        compatible = True
        allow_reason = "missing_role_intelligence"
    elif role_match == "strong":
        compatible = True
        allow_reason = "strong_role_match"
    elif effective_role_match == "acceptable":
        if non_generic_shared_domains:
            compatible = True
            allow_reason = "acceptable_role_with_shared_domain"
        elif (
            (profile_block and profile_block in offer_secondary)
            or (offer_block and offer_block in profile_secondary)
        ) and meaningful_secondary_supported_domains:
            compatible = True
            allow_reason = "acceptable_role_with_secondary_role_domain_support"
        elif signal_overlap["strong_signal_overlap"]:
            compatible = True
            allow_reason = "acceptable_role_with_signal_overlap"
        elif shared_domains and signal_overlap["overlap_count"] >= 1:
            compatible = True
            allow_reason = "acceptable_role_with_light_domain_signal_overlap"
        else:
            rejection_reason = "acceptable_role_without_domain_or_signal_support"
    elif effective_role_match == "weak":
        if _is_valid_data_software_bridge(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
            shared_domains=shared_domains,
        ):
            compatible = True
            allow_reason = "data_software_bridge_with_explicit_data_support"
        elif bridge_shared_domains and (signal_overlap["overlap_count"] >= 1 or primary_shared_domains):
            compatible = True
            allow_reason = "weak_role_with_bridge_domain"
        elif weak_match_shared_domains and signal_overlap["strong_signal_overlap"]:
            compatible = True
            allow_reason = "weak_role_with_shared_domain_and_signal_overlap"
        elif (
            any(domain not in _WEAK_MATCH_DOMAIN_BLOCKLIST for domain in primary_shared_domains)
            and signal_overlap["required_overlap_count"] >= 1
        ):
            compatible = True
            allow_reason = "weak_role_with_primary_domain_and_required_overlap"
        elif bridge_pair and bridge_shared_domains and signal_overlap["overlap_count"] >= 1:
            compatible = True
            allow_reason = "bridge_role_with_shared_domain"
        else:
            rejection_reason = "weak_role_without_enough_domain_or_signal_support"
    else:
        if bridge_pair and bridge_shared_domains and signal_overlap["required_overlap_count"] >= 1 and signal_overlap["strong_signal_overlap"]:
            compatible = True
            allow_reason = "bridge_role_with_strong_domain_and_required_signal_overlap"
        else:
            rejection_reason = "invalid_role_match"

    was_potentially_valid = bool(
        bridge_shared_domains
        or (
            any(domain not in _BRIDGE_SHARED_DOMAIN_BLOCKLIST for domain in primary_shared_domains)
        )
        or signal_overlap["overlap_count"] >= 1
        or (bridge_pair and bridge_shared_domains)
    )

    return {
        "compatible": compatible,
        "role_match": role_match,
        "domain_overlap": bool(shared_domains),
        "shared_domains": shared_domains,
        "non_generic_shared_domains": non_generic_shared_domains,
        "weak_match_shared_domains": weak_match_shared_domains,
        "bridge_shared_domains": bridge_shared_domains,
        "primary_shared_domains": primary_shared_domains,
        "secondary_supported_domains": secondary_supported_domains,
        "signal_overlap": signal_overlap,
        "bridge_role_pair": bridge_pair,
        "effective_role_match": effective_role_match,
        "rejection_reason": rejection_reason,
        "allow_reason": allow_reason,
        "was_potentially_valid": was_potentially_valid,
    }


def _build_offer_structured_text(
    *,
    title: str,
    missions: Sequence[str],
    fallback_description: str,
) -> str:
    lines: List[str] = []
    if title:
        lines.extend(["summary", title.strip()])
    if missions:
        lines.append("missions")
        for mission in missions[:8]:
            if mission:
                lines.append(f"- {mission.strip()}")
    elif fallback_description:
        lines.extend(["missions", fallback_description.strip()])
    return "\n".join(line for line in lines if line)


def _canonical_skill_records(skill_labels: Sequence[str]) -> List[dict]:
    store = get_canonical_store()
    records: List[dict] = []
    seen: set[str] = set()
    for label in skill_labels:
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        canonical_id = store.alias_to_id.get(key)
        entry = store.id_to_skill.get(canonical_id or "", {})
        records.append(
            {
                "label": label,
                "canonical_id": canonical_id,
                "cluster_name": entry.get("cluster_name") or "",
                "genericity_score": float(entry.get("genericity_score") or 0.0) if entry else 0.0,
                "skill_type": entry.get("skill_type") or "",
            }
        )
    return records


def _compute_domain_scores(
    *,
    title: str,
    offer_cluster: str,
    top_signal_units: Sequence[dict],
    secondary_signal_units: Sequence[dict],
    skill_records: Sequence[dict],
    mission_lines: Sequence[str],
    requirement_lines: Sequence[str],
) -> Dict[str, float]:
    scores: Dict[str, float] = {}

    def add(domain: str, weight: float) -> None:
        if not domain or weight <= 0:
            return
        scores[domain] = round(scores.get(domain, 0.0) + weight, 4)

    for line in [title, *mission_lines[:6], *requirement_lines[:6]]:
        line_key = _normalize(line)
        if line == title:
            if any(marker in line_key for marker in ("financial controller", "controleur financier", "contrôleur financier", "financier", "controller")):
                add("finance", 1.2)
            if any(marker in line_key for marker in ("legal counsel", "counsel", "juriste", "lawyer")):
                add("legal", 1.1)
        for domain_name, markers in _DOMAIN_KEYWORDS.items():
            if any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", line_key) for marker in markers):
                weight = 0.9 if line == title else 0.45
                if domain_name in _GENERIC_DOMAIN_DRIFT:
                    weight *= 0.45 if line == title else 0.3
                add(domain_name, weight)

    for unit in list(top_signal_units or [])[:5]:
        domain = _normalize(unit.get("domain"))
        if domain and domain != "unknown":
            add(domain, 1.6)
        signal_text = _extract_signal_text_from_unit(unit)
        for domain_name, markers in _DOMAIN_KEYWORDS.items():
            if any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", _normalize(signal_text)) for marker in markers):
                weight = 0.35
                if domain_name in _GENERIC_DOMAIN_DRIFT:
                    weight *= 0.45
                add(domain_name, weight)

    for unit in list(secondary_signal_units or [])[:5]:
        domain = _normalize(unit.get("domain"))
        if domain and domain != "unknown":
            add(domain, 0.8)

    for item in list(skill_records or [])[:12]:
        label = str(item.get("label") or "")
        cluster_name = str(item.get("cluster_name") or "")
        if _normalize(label) in _GENERIC_SIGNAL_BLOCKLIST_NORM:
            continue
        for domain_name, markers in _DOMAIN_KEYWORDS.items():
            if any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", _normalize(label)) for marker in markers):
                add(domain_name, 0.4)
        if cluster_name == "DATA_ANALYTICS_AI":
            add("data", 0.45)
        elif cluster_name == "FINANCE_BUSINESS_OPERATIONS":
            add("finance", 0.45)
            add("business", 0.08)
        elif cluster_name == "MARKETING_SALES_GROWTH":
            add("marketing", 0.35)
            add("sales", 0.35)
        elif cluster_name == "SOFTWARE_IT":
            add("software", 0.4)
            add("it", 0.3)

    cluster_key = str(offer_cluster or "").upper()
    if cluster_key == "DATA_IT":
        add("data", 1.0)
        add("software", 0.35)
    elif cluster_key == "FINANCE_LEGAL":
        add("finance", 1.0)
        add("legal", 0.45)
    elif cluster_key == "SUPPLY_OPS":
        add("supply_chain", 1.0)
        add("operations", 0.22)
    elif cluster_key == "MARKETING_SALES":
        add("sales", 0.8)
        add("marketing", 0.8)
        add("communication", 0.35)
    elif cluster_key == "ADMIN_HR":
        add("hr", 1.0)
    elif cluster_key == "ENGINEERING_INDUSTRY":
        add("software", 0.45)
        add("project", 0.3)

    return scores


def _build_offer_summary(
    *,
    dominant_block: str,
    dominant_domains: Sequence[str],
    top_signals: Sequence[str],
) -> str:
    block_phrase = _BLOCK_DISPLAY.get(dominant_block, _BLOCK_DISPLAY["generalist_other"])
    if dominant_block == "generalist_other":
        if top_signals:
            return f"Poste polyvalent avec ancrage {top_signals[0]}."
        return "Poste polyvalent sans bloc metier dominant net."
    anchors = [signal for signal in top_signals if _normalize(signal) not in _GENERIC_SIGNAL_BLOCKLIST_NORM][:2]
    if len(anchors) >= 2:
        return f"Poste orienté {block_phrase} avec ancrage {anchors[0]} et {anchors[1]}."
    if len(anchors) == 1:
        return f"Poste orienté {block_phrase} avec ancrage {anchors[0]}."
    if dominant_domains:
        return f"Poste orienté {block_phrase} avec dominante {dominant_domains[0]}."
    return f"Poste orienté {block_phrase}."


def _derive_role_hypotheses(
    *,
    dominant_block: str,
    secondary_blocks: Sequence[str],
    block_scores: Dict[str, float],
    title: str,
) -> List[dict]:
    hypotheses: List[tuple[str, float]] = []
    seen: set[str] = set()

    normalized_title = _normalize(title)
    for marker, block in _TITLE_BLOCK_HINTS:
        if _normalize(marker) and re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", normalized_title):
            label = _BLOCK_PRIMARY_ROLE.get(block, "Profil polyvalent")
            hypotheses.append((label, 0.88))
            seen.add(_normalize(label))
            break

    label = _BLOCK_PRIMARY_ROLE.get(dominant_block, "Profil polyvalent")
    if _normalize(label) not in seen:
        hypotheses.append((label, round(min(0.92, 0.56 + min(block_scores.get(dominant_block, 0.0), 4.0) * 0.07), 2)))
        seen.add(_normalize(label))

    secondary_label = _BLOCK_SECONDARY_ROLE.get(dominant_block)
    if secondary_label and _normalize(secondary_label) not in seen:
        hypotheses.append((secondary_label, round(min(0.84, 0.44 + min(block_scores.get(dominant_block, 0.0), 4.0) * 0.05), 2)))
        seen.add(_normalize(secondary_label))

    for secondary in list(secondary_blocks or [])[:2]:
        sec_label = _BLOCK_PRIMARY_ROLE.get(secondary)
        if not sec_label or _normalize(sec_label) in seen:
            continue
        hypotheses.append((sec_label, round(min(0.78, 0.36 + min(block_scores.get(secondary, 0.0), 3.0) * 0.07), 2)))
        seen.add(_normalize(sec_label))

    hypotheses.sort(key=lambda item: (-item[1], _normalize(item[0])))
    return [{"label": label, "confidence": confidence} for label, confidence in hypotheses[:_MAX_ROLE_HYPOTHESES]]


def _sentence_has_marker(text: str, markers: Sequence[str]) -> bool:
    normalized = _normalize(text)
    return any(re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", normalized) for marker in markers)


def _select_skill_bucket_candidates(
    *,
    dominant_block: str,
    top_signal_units: Sequence[dict],
    secondary_signal_units: Sequence[dict],
    requirement_skill_candidates: Sequence[str],
    skill_records: Sequence[dict],
    tools_stack: Sequence[str],
    requirement_lines: Sequence[str],
) -> tuple[List[str], List[str]]:
    required_scores: Dict[str, float] = {}
    optional_scores: Dict[str, float] = {}

    def bump(bucket: Dict[str, float], label: str, weight: float) -> None:
        key = _normalize(label)
        if not key or weight <= 0:
            return
        bucket[key] = round(bucket.get(key, 0.0) + weight, 4)

    top_unit_signals = []
    for unit in list(top_signal_units or [])[:5]:
        signal = _extract_signal_text_from_unit(unit)
        if not signal or _is_generic_signal(signal):
            continue
        top_unit_signals.append(signal)
        score = 1.6 + float(unit.get("ranking_score") or 0.0) * 0.25
        bump(required_scores, signal, score)

    for line in requirement_lines:
        if _sentence_has_marker(line, _REQUIRED_MARKERS):
            for candidate in requirement_skill_candidates:
                if _normalize(candidate) in _normalize(line):
                    bump(required_scores, candidate, 2.0)
        if _sentence_has_marker(line, _OPTIONAL_MARKERS):
            for candidate in requirement_skill_candidates:
                if _normalize(candidate) in _normalize(line):
                    bump(optional_scores, candidate, 1.8)

    for candidate in list(requirement_skill_candidates or [])[:10]:
        weight = 1.25 if _score_text_against_block(candidate, dominant_block) > 0 else 0.75
        if _tool_like(candidate) and _normalize(candidate) in _TOOL_OPTIONAL_BLOCKLIST:
            bump(optional_scores, candidate, max(weight, 0.85))
            continue
        bump(required_scores, candidate, weight)

    for item in list(skill_records or [])[:12]:
        label = str(item.get("label") or "")
        if not label or _normalize(label) in _GENERIC_SIGNAL_BLOCKLIST_NORM:
            continue
        if _tool_like(label):
            weight = 0.8 if _score_text_against_block(label, dominant_block) > 0 else 0.5
            if _normalize(label) in _TOOL_OPTIONAL_BLOCKLIST:
                bump(optional_scores, label, weight)
            else:
                bump(required_scores, label, weight)
            continue
        weight = 0.95 if _score_text_against_block(label, dominant_block) > 0 else 0.55
        bump(required_scores, label, weight)

    for label in list(tools_stack or [])[:8]:
        if _normalize(label) in _TOOL_OPTIONAL_BLOCKLIST:
            bump(optional_scores, label, 0.9)

    for unit in list(secondary_signal_units or [])[:3]:
        signal = _extract_signal_text_from_unit(unit)
        if not signal or _is_generic_signal(signal):
            continue
        if _score_text_against_block(signal, dominant_block) > 0.15:
            bump(required_scores, signal, 0.8)
        else:
            bump(optional_scores, signal, 0.55)

    def finalize(bucket: Dict[str, float], *, cap: int, exclude: set[str] | None = None) -> List[str]:
        exclude = exclude or set()
        labels: List[str] = []
        for key, _score in sorted(bucket.items(), key=lambda item: (-item[1], item[0])):
            if key in exclude:
                continue
            if key in {_normalize(item) for item in labels}:
                continue
            labels.append(key)
            if len(labels) >= cap:
                break
        return labels

    key_to_label: Dict[str, str] = {}
    for label in [*top_unit_signals, *requirement_skill_candidates, *[str(i.get("label") or "") for i in skill_records], *tools_stack]:
        key = _normalize(label)
        if key and key not in key_to_label:
            key_to_label[key] = label.strip()

    required_keys = finalize(required_scores, cap=_MAX_REQUIRED)
    optional_keys = finalize(optional_scores, cap=_MAX_OPTIONAL, exclude=set(required_keys))

    return (
        [key_to_label.get(key, key) for key in required_keys],
        [key_to_label.get(key, key) for key in optional_keys],
    )


def _dampen_incompatible_blocks(
    acc: _BlockAccumulator,
    *,
    anchor_block: str | None,
    factor: float,
) -> None:
    if not anchor_block or anchor_block == "generalist_other":
        return
    allowed = {anchor_block, *_role_neighbors(anchor_block)}
    for block in ROLE_BLOCKS:
        if block in allowed:
            continue
        acc.scores[block] = round(acc.scores[block] * factor, 4)


def _select_secondary_roles(
    *,
    sorted_scores: Sequence[tuple[str, float]],
    dominant_role_block: str,
    dominant_score: float,
    title_block: str | None,
    dominant_domain: str | None,
) -> List[str]:
    selected: List[str] = []
    if dominant_role_block == "generalist_other" or dominant_score <= 0:
        return selected

    title_neighbors = _role_neighbors(title_block or "")
    dominant_neighbors = _role_neighbors(dominant_role_block)
    dominant_domain_blocks = set(_DOMAIN_TO_BLOCK.get(dominant_domain or "", {}).keys())

    for block, score in list(sorted_scores[1:5]):
        if block == dominant_role_block or score <= 0:
            continue
        same_title_family = bool(title_block and (block == title_block or block in title_neighbors))
        adjacent_to_dominant = block in dominant_neighbors
        domain_supported = block in dominant_domain_blocks
        if score < max(1.25, dominant_score * 0.56):
            continue
        if not (same_title_family or adjacent_to_dominant or domain_supported):
            continue
        selected.append(block)
        if len(selected) >= 1:
            break
    return selected


def build_offer_intelligence(
    *,
    offer: dict,
    description_structured: dict | None = None,
    description_structured_v1: OfferDescriptionStructuredV1 | dict | None = None,
    canonical_offer: dict | None = None,
) -> Dict[str, Any]:
    cache_payload = {
        "offer": {
            "id": offer.get("id"),
            "title": offer.get("title"),
            "description": offer.get("description") or offer.get("display_description"),
            "skills": list(offer.get("skills") or []),
            "skills_display": list(offer.get("skills_display") or []),
            "offer_cluster": offer.get("offer_cluster"),
        },
        "canonical_offer": canonical_offer,
    }
    cache_key = json.dumps(cache_payload, sort_keys=True, ensure_ascii=False, default=str)
    cached = _INTELLIGENCE_CACHE.get(cache_key)
    if cached is not None:
        return copy.deepcopy(cached)

    title = str(offer.get("title") or "").strip()
    description = str(offer.get("description") or offer.get("display_description") or "").strip()
    skill_labels = _extract_skill_labels(offer.get("skills_display"), offer.get("skills"))

    if canonical_offer is None:
        if description_structured is None:
            description_structured = structure_offer_description(description, esco_skills=skill_labels[:12], lang_hint="fr")
        if description_structured_v1 is None:
            description_structured_v1 = structure_offer_text_v1(description, esco_labels=skill_labels[:12])
        elif isinstance(description_structured_v1, dict):
            description_structured_v1 = OfferDescriptionStructuredV1(**description_structured_v1)
        canonical_offer = build_offer_canonical_representation(
            {
                **offer,
                "description": description,
                "skills": offer.get("skills"),
                "skills_display": offer.get("skills_display"),
                "offer_cluster": offer.get("offer_cluster"),
            }
        )
    else:
        description_structured = canonical_offer.get("description_structured") or description_structured or {}
        description_structured_v1 = canonical_offer.get("description_structured_v1") or description_structured_v1

    if isinstance(description_structured_v1, dict):
        description_structured_v1 = OfferDescriptionStructuredV1(**description_structured_v1)

    title = str(canonical_offer.get("title") or title).strip()
    description = str(canonical_offer.get("description") or description).strip()
    mission_lines = list(canonical_offer.get("mission_lines") or [])[:8]
    requirement_lines = list(canonical_offer.get("requirement_lines") or [])[:6]
    requirement_skill_candidates = list(canonical_offer.get("canonical_enriched_labels") or canonical_offer.get("requirement_skill_candidates") or [])[:12]
    tools_stack = list(canonical_offer.get("tools_stack") or [])
    top_signal_units = list(canonical_offer.get("top_signal_units") or [])[:5]
    secondary_signal_units = list(canonical_offer.get("secondary_signal_units") or [])[:5]

    canonical_skills = list(canonical_offer.get("canonical_skills") or [])
    skill_records = canonical_skills or _canonical_skill_records([*requirement_skill_candidates, *skill_labels])
    canonical_skill_labels = [str(item.get("label") or "") for item in canonical_skills if str(item.get("label") or "").strip()]
    skill_labels = list(canonical_offer.get("skill_labels") or skill_labels)
    if canonical_skill_labels:
        skill_labels = _clean_signal_list([*canonical_skill_labels, *skill_labels])

    offer_cluster = str(canonical_offer.get("offer_cluster") or offer.get("offer_cluster") or "")
    if not offer_cluster:
        offer_cluster, _, _ = detect_offer_cluster(title, description, skill_labels)

    structured_stage = type(
        "OfferStructuredStageView",
        (),
        {
            "enabled": True,
            "structured_units": list(canonical_offer.get("structured_units") or []),
            "stats": dict(canonical_offer.get("structured_extraction_stats") or {}),
        },
    )()

    role_resolution = {
        "raw_title": title,
        "normalized_title": title,
        "primary_role_family": None,
        "secondary_role_families": [],
        "occupation_confidence": 0.0,
        "candidate_occupations": [],
    }
    title_probe = title
    recent_title = ""
    title_block, title_confidence = _infer_offer_title_block(title_probe)
    title_domains = list(_BLOCK_TO_DOMAINS.get(title_block or "", ()))

    acc = _BlockAccumulator()

    for marker, block in _TITLE_BLOCK_HINTS:
        if title_probe and re.search(rf"(?<!\w){re.escape(_normalize(marker))}(?!\w)", _normalize(title_probe)):
            acc.add(block, 2.8, source="title_marker", reason=title_probe)
    if title_block and title_block != "generalist_other":
        acc.add(title_block, 6.6 * max(title_confidence, 0.72), source="title_block", reason=title_probe or title)

    for block, weight in _CLUSTER_TO_BLOCK_WEIGHTS.get(str(offer_cluster or "").upper(), {}).items():
        acc.add(block, weight * 1.0, source="offer_cluster", reason=offer_cluster)

    domain_scores = _compute_domain_scores(
        title=title_probe or title,
        offer_cluster=offer_cluster,
        top_signal_units=top_signal_units,
        secondary_signal_units=secondary_signal_units,
        skill_records=skill_records,
        mission_lines=mission_lines,
        requirement_lines=requirement_lines,
    )
    if title_domains and title_confidence >= 0.72:
        for domain in title_domains:
            domain_scores[domain] = round(domain_scores.get(domain, 0.0) + (3.4 * title_confidence), 4)
    _add_domain_votes(acc, domain_scores)

    for unit in top_signal_units:
        signal_text = _extract_signal_text_from_unit(unit)
        if not signal_text:
            continue
        base_weight = 1.4 + float(unit.get("ranking_score") or unit.get("specificity_score") or 0.0) * 0.65
        _add_text_votes(acc, text=signal_text, source="top_signal_unit", base_weight=base_weight)

    for unit in secondary_signal_units:
        signal_text = _extract_signal_text_from_unit(unit)
        if not signal_text:
            continue
        base_weight = 0.7 + float(unit.get("ranking_score") or unit.get("specificity_score") or 0.0) * 0.3
        _add_text_votes(acc, text=signal_text, source="secondary_signal_unit", base_weight=base_weight)

    for source_name, items, base_weight in (
        ("required_skill_candidate", requirement_skill_candidates, 1.0),
        ("offer_skill", [item.get("label") for item in skill_records], 0.75),
        ("offer_tool", tools_stack, 0.45),
    ):
        for label in list(items or [])[:12]:
            if not label:
                continue
            cluster_name = ""
            genericity_score = None
            if source_name == "offer_skill":
                matched = next((item for item in skill_records if _normalize(item.get("label")) == _normalize(label)), None)
                if matched:
                    cluster_name = str(matched.get("cluster_name") or "")
                    genericity_score = matched.get("genericity_score")
            _add_text_votes(
                acc,
                text=str(label),
                source=source_name,
                base_weight=base_weight,
                cluster_name=cluster_name,
                genericity_score=float(genericity_score) if isinstance(genericity_score, (int, float)) else None,
            )

    all_signal_texts = [
        _extract_signal_text_from_unit(unit)
        for unit in top_signal_units
    ] + mission_lines[:5] + requirement_skill_candidates[:8] + skill_labels[:10]

    finance_anchor_hits = _count_anchor_hits(all_signal_texts, _FINANCE_ANCHORS)
    data_anchor_hits = _count_anchor_hits(all_signal_texts, _DATA_ANCHORS)
    supply_anchor_hits = _count_anchor_hits(all_signal_texts, _SUPPLY_CHAIN_ANCHORS)
    marketing_anchor_hits = _count_anchor_hits(all_signal_texts, _MARKETING_ANCHORS)
    business_anchor_hits = _count_anchor_hits(all_signal_texts, _BUSINESS_ANALYSIS_ANCHORS)
    data_support_hits = _count_anchor_hits(all_signal_texts, _DATA_SUPPORT_SIGNALS)

    canonical_domains = list(canonical_offer.get("canonical_domains") or [])
    dominant_domain = _dominant_domain(domain_scores) or (canonical_domains[0] if canonical_domains else None)
    sorted_domains = sorted(((domain, score) for domain, score in domain_scores.items() if score > 0), key=lambda item: (-item[1], item[0]))
    top_domain_score = sorted_domains[0][1] if sorted_domains else 0.0
    second_domain_score = sorted_domains[1][1] if len(sorted_domains) > 1 else 0.0
    domain_confidence = round(top_domain_score / max(top_domain_score + second_domain_score, 1.0), 4) if top_domain_score > 0 else 0.0

    if title_block and title_block != "generalist_other" and title_confidence >= 0.88:
        _dampen_incompatible_blocks(acc, anchor_block=title_block, factor=0.72)

    if title_block and title_block != "data_analytics" and title_confidence >= 0.84:
        acc.scores[title_block] = round(acc.scores[title_block] + (3.0 * title_confidence), 4)
        if data_support_hits >= 2:
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.66, 4)
        else:
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.76, 4)

    override_block = None
    if dominant_domain and dominant_domain != "data" and domain_confidence >= 0.6:
        candidates = _DOMAIN_TO_BLOCK.get(dominant_domain, {})
        if candidates:
            override_block = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if dominant_domain == "operations" and domain_scores.get("supply_chain", 0.0) >= top_domain_score * 0.55:
                override_block = "supply_chain_ops"
            acc.scores[override_block] = round(acc.scores[override_block] + (2.3 + (top_domain_score * 0.12)), 4)
            acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.68, 4)
            if domain_confidence >= 0.7:
                _dampen_incompatible_blocks(acc, anchor_block=override_block, factor=0.8)

    if finance_anchor_hits >= 2 and acc.scores["finance_ops"] >= acc.scores["data_analytics"] * 0.62:
        acc.scores["finance_ops"] = round(acc.scores["finance_ops"] + (0.9 + (finance_anchor_hits * 0.18)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)
    if supply_anchor_hits >= 2 and acc.scores["supply_chain_ops"] >= acc.scores["data_analytics"] * 0.58:
        acc.scores["supply_chain_ops"] = round(acc.scores["supply_chain_ops"] + (0.8 + (supply_anchor_hits * 0.15)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)
    if marketing_anchor_hits >= 2 and acc.scores["marketing_communication"] >= acc.scores["data_analytics"] * 0.52:
        acc.scores["marketing_communication"] = round(acc.scores["marketing_communication"] + (0.8 + (marketing_anchor_hits * 0.16)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.84, 4)
    if business_anchor_hits >= 2 and acc.scores["business_analysis"] >= acc.scores["data_analytics"] * 0.42:
        acc.scores["business_analysis"] = round(acc.scores["business_analysis"] + (0.9 + (business_anchor_hits * 0.18)), 4)
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.82, 4)
    if data_anchor_hits < 2 and data_support_hits >= 2 and dominant_domain != "data":
        acc.scores["data_analytics"] = round(acc.scores["data_analytics"] * 0.78, 4)

    dominant_domain = _dominant_domain(domain_scores)
    for block in list(acc.scores):
        acc.scores[block] = round(acc.scores[block] * _domain_penalty_for_block(block, dominant_domain), 4)

    sorted_scores = _sorted_block_scores(acc.scores)
    dominant_role_block = sorted_scores[0][0] if sorted_scores and sorted_scores[0][1] > 0 else "generalist_other"
    dominant_score = sorted_scores[0][1] if sorted_scores else 0.0
    secondary_role_blocks = _select_secondary_roles(
        sorted_scores=sorted_scores,
        dominant_role_block=dominant_role_block,
        dominant_score=dominant_score,
        title_block=title_block,
        dominant_domain=dominant_domain,
    )[:_MAX_SECONDARY]

    top_offer_signals = _clean_signal_list(_select_top_profile_signals(
        top_signal_units=top_signal_units,
        preserved_explicit_skills=skill_records,
        profile_summary_skills=[{"label": label} for label in requirement_skill_candidates + skill_labels],
        enriched_signals=[],
        dominant_block=dominant_role_block,
    ))

    required_skills, optional_skills = _select_skill_bucket_candidates(
        dominant_block=dominant_role_block,
        top_signal_units=top_signal_units,
        secondary_signal_units=secondary_signal_units,
        requirement_skill_candidates=requirement_skill_candidates,
        skill_records=skill_records,
        tools_stack=tools_stack,
        requirement_lines=requirement_lines,
    )
    required_skills = _clean_signal_list(required_skills)
    required_norms = {_normalize(item) for item in required_skills}
    optional_skills = [
        item
        for item in _clean_signal_list(optional_skills)
        if not any(_normalize(item) in req or req in _normalize(item) for req in required_norms)
    ]

    dominant_domains = [
        domain
        for domain, score in sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
        if score >= max(1.0, (domain_scores.get(dominant_domain, 0.0) * 0.55 if dominant_domain else 1.0))
    ][:2]
    allowed_domains = set(_BLOCK_TO_DOMAINS.get(dominant_role_block, ()))
    for domain in canonical_domains:
        if not domain or domain in dominant_domains:
            continue
        domain_score = float(domain_scores.get(domain, 0.0))
        if domain in _GENERIC_DOMAIN_DRIFT and domain_score <= 0:
            continue
        if domain not in allowed_domains and domain_score < max(0.95, top_domain_score * 0.42 if top_domain_score else 0.95):
            continue
        if domain in _GENERIC_DOMAIN_DRIFT and domain not in allowed_domains and domain_score < max(1.2, top_domain_score * 0.6 if top_domain_score else 1.2):
            continue
        if domain and domain not in dominant_domains:
            dominant_domains.append(domain)
        if len(dominant_domains) >= 2:
            break

    role_hypotheses = _derive_role_hypotheses(
        dominant_block=dominant_role_block,
        secondary_blocks=secondary_role_blocks,
        block_scores=acc.scores,
        title=title_probe or title,
    )

    offer_summary = _build_offer_summary(
        dominant_block=dominant_role_block,
        dominant_domains=dominant_domains,
        top_signals=top_offer_signals,
    )

    score_total = sum(max(score, 0.0) for _, score in sorted_scores[:4])
    role_block_scores = [
        {
            "role_block": block,
            "score": round(score, 4),
            "share": round((score / score_total), 4) if score_total else 0.0,
        }
        for block, score in sorted_scores[:5]
        if score > 0
    ]

    result = {
        "dominant_role_block": dominant_role_block,
        "secondary_role_blocks": secondary_role_blocks,
        "dominant_domains": dominant_domains,
        "top_offer_signals": top_offer_signals,
        "required_skills": required_skills,
        "optional_skills": optional_skills,
        "role_hypotheses": role_hypotheses,
        "offer_summary": offer_summary,
        "role_block_scores": role_block_scores,
        "debug": {
            "title_probe": {
                "raw_title": role_resolution.get("raw_title"),
                "normalized_title": role_resolution.get("normalized_title"),
                "primary_role_family": role_resolution.get("primary_role_family"),
                "secondary_role_families": role_resolution.get("secondary_role_families") or [],
                "occupation_confidence": float(role_resolution.get("occupation_confidence") or 0.0),
                "candidate_occupations": [],
                "title_block": title_block,
                "title_confidence": round(title_confidence, 4),
            },
            "offer_cluster": offer_cluster,
            "structured_stage_enabled": bool(structured_stage.enabled),
            "structured_unit_count": len(structured_stage.structured_units or []),
            "domain_scores": [
                {"domain": domain, "score": round(score, 4)}
                for domain, score in sorted(domain_scores.items(), key=lambda item: (-item[1], item[0]))
                if score > 0
            ],
            "dominant_domain": dominant_domain,
            "domain_confidence": domain_confidence,
            "override_block": override_block,
            "mission_count": len(mission_lines),
            "requirement_count": len(requirement_lines),
            "mapping_inputs_count": int(len(canonical_offer.get("mapping_inputs") or []) or (structured_stage.stats or {}).get("mapping_inputs_count", 0) or 0),
            "canonical_skill_count": len(canonical_skills),
            "canonical_domain_count": len(canonical_domains),
            "unresolved_count": len(canonical_offer.get("unresolved") or []),
        },
    }
    if len(_INTELLIGENCE_CACHE) >= _INTELLIGENCE_CACHE_CAP:
        oldest_key = next(iter(_INTELLIGENCE_CACHE))
        _INTELLIGENCE_CACHE.pop(oldest_key, None)
    _INTELLIGENCE_CACHE[cache_key] = copy.deepcopy(result)
    return result


def offer_intelligence_to_csv_rows(results: Sequence[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "offer_id",
            "title",
            "expected_role_block",
            "predicted_role_block",
            "dominant_domains",
            "top_offer_signals",
            "required_skills",
            "optional_skills",
            "offer_summary",
        ],
    )
    writer.writeheader()
    for row in results:
        writer.writerow(
            {
                "offer_id": row.get("offer_id"),
                "title": row.get("title"),
                "expected_role_block": row.get("expected_role_block"),
                "predicted_role_block": row.get("predicted_role_block"),
                "dominant_domains": " | ".join(row.get("dominant_domains") or []),
                "top_offer_signals": " | ".join(row.get("top_offer_signals") or []),
                "required_skills": " | ".join(row.get("required_skills") or []),
                "optional_skills": " | ".join(row.get("optional_skills") or []),
                "offer_summary": row.get("offer_summary"),
            }
        )
    return output.getvalue()
