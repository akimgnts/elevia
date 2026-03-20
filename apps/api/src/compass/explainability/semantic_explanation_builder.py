"""Deterministic semantic explainability built from profile vs offer intelligence."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence
import re
import unicodedata


_ROLE_DISPLAY = {
    "data_analytics": "analyse de donnees",
    "business_analysis": "analyse metier",
    "finance_ops": "finance operationnelle",
    "legal_compliance": "conformite / juridique",
    "sales_business_dev": "developpement commercial",
    "marketing_communication": "marketing / communication",
    "hr_ops": "rh operationnelles",
    "supply_chain_ops": "supply chain / operations",
    "project_ops": "coordination de projets",
    "software_it": "software / it",
    "generalist_other": "profil polyvalent",
}

_DOMAIN_DISPLAY = {
    "data": "data",
    "finance": "finance",
    "sales": "commercial",
    "marketing": "marketing",
    "communication": "communication",
    "hr": "rh",
    "supply_chain": "supply chain",
    "operations": "operations",
    "business": "metier",
    "project": "projet",
    "software": "software",
    "it": "it",
    "legal": "juridique",
    "generalist": "polyvalent",
}

_ROLE_ADJACENCY = {
    "data_analytics": {"business_analysis", "finance_ops"},
    "business_analysis": {"data_analytics", "finance_ops", "project_ops", "supply_chain_ops", "sales_business_dev"},
    "finance_ops": {"business_analysis", "legal_compliance", "data_analytics"},
    "legal_compliance": {"finance_ops"},
    "sales_business_dev": {"marketing_communication", "business_analysis"},
    "marketing_communication": {"sales_business_dev", "business_analysis"},
    "hr_ops": {"project_ops"},
    "supply_chain_ops": {"project_ops", "business_analysis"},
    "project_ops": {"business_analysis", "supply_chain_ops", "hr_ops"},
    "software_it": {"data_analytics"},
    "generalist_other": set(),
}

_GENERIC_SIGNAL_KEYS = {
    "communication",
    "collaboration",
    "leadership",
    "problem solving",
    "organisation",
    "teamwork",
    "excel",
}

_MAX_MATCHED = 5
_MAX_MISSING = 5


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _clean_list(values: Sequence[Any], limit: int) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for raw in values:
        label = str(raw or "").strip()
        key = _normalize(label)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(label)
        if len(result) >= limit:
            break
    return result


def _domain_label(domain: str) -> str:
    return _DOMAIN_DISPLAY.get(domain, domain.replace("_", " "))


def _role_label(role_block: str) -> str:
    return _ROLE_DISPLAY.get(role_block, role_block.replace("_", " "))


def _join_labels(values: Sequence[str]) -> str:
    items = [item for item in values if item]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} et {items[1]}"
    return f"{', '.join(items[:-1])} et {items[-1]}"


def _alignment_level(profile_role: str, offer_role: str, shared_domains: Sequence[str]) -> str:
    if profile_role and offer_role and profile_role == offer_role:
        return "high"
    if profile_role and offer_role and offer_role in _ROLE_ADJACENCY.get(profile_role, set()):
        return "medium"
    if shared_domains:
        return "medium"
    return "low"


def _token_set(value: str) -> set[str]:
    return {token for token in _normalize(value).split() if token}


def _signals_match(left: str, right: str) -> bool:
    left_key = _normalize(left)
    right_key = _normalize(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    if left_key in right_key or right_key in left_key:
        return True
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = left_tokens & right_tokens
    if len(overlap) >= min(len(left_tokens), len(right_tokens)):
        return True
    return len(overlap) >= 2


def _collect_matched_signals(profile_signals: Sequence[str], offer_signals: Sequence[str]) -> List[str]:
    matched: List[str] = []
    seen: set[str] = set()
    for offer_signal in offer_signals:
        offer_key = _normalize(offer_signal)
        if not offer_key or offer_key in _GENERIC_SIGNAL_KEYS:
            continue
        if any(_signals_match(profile_signal, offer_signal) for profile_signal in profile_signals):
            if offer_key in seen:
                continue
            seen.add(offer_key)
            matched.append(offer_signal)
            if len(matched) >= _MAX_MATCHED:
                break
    return matched


def _collect_missing_signals(
    matched_signals: Sequence[str],
    offer_core_signals: Sequence[str],
    explanation: Optional[Dict[str, Any]],
) -> List[str]:
    matched_keys = {_normalize(item) for item in matched_signals}
    missing: List[str] = []
    seen: set[str] = set()
    for signal in offer_core_signals:
        key = _normalize(signal)
        if not key or key in matched_keys or key in seen or key in _GENERIC_SIGNAL_KEYS:
            continue
        seen.add(key)
        missing.append(signal)
        if len(missing) >= _MAX_MISSING:
            break
    for signal in list((explanation or {}).get("blockers") or []) + list((explanation or {}).get("gaps") or []):
        key = _normalize(signal)
        if not key or key in matched_keys or key in seen:
            continue
        seen.add(key)
        missing.append(str(signal))
        if len(missing) >= _MAX_MISSING:
            break
    return missing


def _build_summary(
    *,
    alignment: str,
    profile_role: str,
    offer_role: str,
    shared_domains: Sequence[str],
    matched_signals: Sequence[str],
    missing_signals: Sequence[str],
) -> str:
    profile_label = _role_label(profile_role)
    offer_label = _role_label(offer_role)
    shared_domain_labels = [_domain_label(domain) for domain in shared_domains[:2]]
    matched_label = _join_labels(list(matched_signals)[:2])
    missing_label = _join_labels(list(missing_signals)[:2])

    if alignment == "high":
        anchor = _join_labels(shared_domain_labels) or offer_label
        if matched_label and missing_label:
            return (
                f"Ton profil et ce poste sont alignes sur {anchor}, avec un socle commun en {matched_label}, "
                f"mais il manque encore {missing_label}."
            )
        if matched_label:
            return f"Ton profil et ce poste sont alignes sur {anchor}, avec un socle commun en {matched_label}."
        return f"Ton profil et ce poste parlent le meme metier autour de {anchor}."

    if alignment == "medium":
        anchor = _join_labels(shared_domain_labels) or matched_label or offer_label
        if missing_label:
            return f"Ton profil recoupe ce poste sur {anchor}, mais le poste reste plus oriente {offer_label} avec un manque sur {missing_label}."
        return f"Ton profil recoupe ce poste sur {anchor}, meme si le poste reste plus oriente {offer_label}."

    if matched_label:
        return f"Le poste est surtout oriente {offer_label}, alors que ton profil penche davantage vers {profile_label}, avec seulement un recouvrement partiel sur {matched_label}."
    return f"Le poste est surtout oriente {offer_label}, alors que ton profil penche davantage vers {profile_label}."


def build_semantic_explainability(
    *,
    profile_intelligence: Optional[Dict[str, Any]],
    offer_intelligence: Optional[Dict[str, Any]],
    explanation: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(profile_intelligence, dict) or not isinstance(offer_intelligence, dict):
        return None

    profile_role = str(profile_intelligence.get("dominant_role_block") or "")
    offer_role = str(offer_intelligence.get("dominant_role_block") or "")
    if not profile_role or not offer_role:
        return None

    profile_domains = _clean_list(list(profile_intelligence.get("dominant_domains") or []), 3)
    offer_domains = _clean_list(list(offer_intelligence.get("dominant_domains") or []), 3)
    profile_domain_keys = [_normalize(item) for item in profile_domains]
    offer_domain_keys = [_normalize(item) for item in offer_domains]

    shared_domains = [
        offer_domains[idx]
        for idx, key in enumerate(offer_domain_keys)
        if key and key in set(profile_domain_keys)
    ][:3]
    profile_only_domains = [
        profile_domains[idx]
        for idx, key in enumerate(profile_domain_keys)
        if key and key not in set(offer_domain_keys)
    ][:3]
    offer_only_domains = [
        offer_domains[idx]
        for idx, key in enumerate(offer_domain_keys)
        if key and key not in set(profile_domain_keys)
    ][:3]

    alignment = _alignment_level(profile_role, offer_role, shared_domains)

    profile_signals = _clean_list(list(profile_intelligence.get("top_profile_signals") or []), 7)
    offer_signal_source = list(offer_intelligence.get("top_offer_signals") or []) + list(offer_intelligence.get("required_skills") or [])
    offer_signals = _clean_list(offer_signal_source, 7)

    matched_signals = _collect_matched_signals(profile_signals, offer_signals)
    if not matched_signals:
        matched_signals = _clean_list(list((explanation or {}).get("strengths") or []), _MAX_MATCHED)
    missing_signals = _collect_missing_signals(
        matched_signals,
        _clean_list(list(offer_intelligence.get("required_skills") or []) or offer_signals, 7),
        explanation,
    )

    return {
        "role_alignment": {
            "profile_role": profile_role,
            "offer_role": offer_role,
            "alignment": alignment,
        },
        "domain_alignment": {
            "shared_domains": shared_domains,
            "profile_only_domains": profile_only_domains,
            "offer_only_domains": offer_only_domains,
        },
        "signal_alignment": {
            "matched_signals": matched_signals[:_MAX_MATCHED],
            "missing_core_signals": missing_signals[:_MAX_MISSING],
        },
        "alignment_summary": _build_summary(
            alignment=alignment,
            profile_role=profile_role,
            offer_role=offer_role,
            shared_domains=shared_domains,
            matched_signals=matched_signals,
            missing_signals=missing_signals,
        ),
    }
