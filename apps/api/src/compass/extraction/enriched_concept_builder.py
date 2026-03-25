from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence

from compass.canonical.canonical_store import normalize_canonical_key

from .domain_rules import infer_domain

_STOPWORDS = {
    "avec",
    "dans",
    "pour",
    "des",
    "les",
    "the",
    "and",
    "with",
    "for",
    "pas",
    "mais",
    "sur",
    "via",
    "une",
    "un",
    "du",
    "de",
    "la",
    "le",
}
_GARBAGE_TOKENS = {
    "cv",
    "super",
    "ok",
    "etc",
    "exp",
    "pro",
    "skills",
    "tools",
    "competences",
    "experience",
    "project",
    "projects",
    "profil",
    "profile",
    "soft",
    "simple",
    "simples",
    "toujours",
    "propres",
    "not",
    "only",
    "sometimes",
}
_ALLOWED_SHORT_TOKENS = {"sql", "sap", "erp", "crm", "sirh", "kpi", "rh", "hr", "bi", "tms"}
_MEANINGFUL_SINGLETONS = {
    "reporting",
    "budget",
    "audit",
    "forecasting",
    "onboarding",
    "recrutement",
    "recruitment",
    "prospection",
    "excel",
    "python",
    "sql",
    "sap",
    "sirh",
    "crm",
    "tms",
}
_DOMAIN_OUTPUT_MAP = {
    "supply_chain": "supply_chain_ops",
    "hr": "hr_ops",
    "marketing": "marketing",
    "sales": "sales",
    "finance": "finance",
    "data": "data",
    "unknown": "unknown",
}


def _extract_text(item: Any) -> tuple[str, str]:
    if isinstance(item, str):
        return item, ""
    if isinstance(item, dict):
        text = str(item.get("normalized") or item.get("raw") or item.get("concept") or "")
        return text, str(item.get("domain") or "")
    return "", ""


def _clean_tokens(text: str) -> list[str]:
    tokens = [token for token in normalize_canonical_key(text).split() if token]
    cleaned: list[str] = []
    for token in tokens:
        if token in _STOPWORDS or token in _GARBAGE_TOKENS:
            continue
        if len(token) < 3 and token not in _ALLOWED_SHORT_TOKENS:
            continue
        cleaned.append(token)
    return cleaned


def _normalize_variant(text: str) -> str:
    tokens = _clean_tokens(text)
    return " ".join(tokens).strip()


def _normalize_root(variant: str) -> str:
    key = normalize_canonical_key(variant)
    if not key:
        return ""

    token_set = set(key.split())
    if "reporting" in token_set:
        return "reporting"
    if ("analyse" in token_set and ("donnees" in token_set or "donnee" in token_set)) or key == "data analysis":
        return "data analysis"
    if key == "analyse de donnees":
        return "data analysis"
    if ("portefeuille" in token_set or "portfolio" in token_set) and (
        "gestion" in token_set or "management" in token_set or "manage" in token_set or "clients" in token_set
    ):
        return "portfolio management"
    if ("coordination" in token_set and "transport" in token_set) or key == "transport coordination":
        return "transport coordination"
    if ("gestion" in token_set and ("stocks" in token_set or "stock" in token_set)) or key == "stock management":
        return "stock management"
    if key == "weekly reporting" or key == "monthly reporting":
        return "reporting"
    return key


def _infer_output_domain(variant: str, domain_hint: str, root: str) -> str:
    domain, _, _ = infer_domain(variant, root, domain_hint)
    if domain == "unknown":
        if root == "reporting":
            domain = "business"
        elif root == "portfolio management":
            domain = "sales"
        elif root == "data analysis":
            domain = "data"
        elif root in {"transport coordination", "stock management"}:
            domain = "supply_chain"
    return _DOMAIN_OUTPUT_MAP.get(domain, domain)


def _is_valid_signal(variant: str, domain: str, root: str) -> bool:
    if not variant or not root:
        return False
    tokens = variant.split()
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0] not in _MEANINGFUL_SINGLETONS and domain == "unknown":
        return False
    if domain == "unknown" and len(tokens) < 2 and tokens[0] not in _MEANINGFUL_SINGLETONS:
        return False
    return True


def _cluster_key(root: str, domain: str) -> tuple[str, str]:
    return root, domain or "unknown"


def _best_concept(root: str, variants: Sequence[str]) -> str:
    if root in {
        "reporting",
        "data analysis",
        "portfolio management",
        "transport coordination",
        "stock management",
    }:
        return root
    normalized_variants = [normalize_canonical_key(value) for value in variants if normalize_canonical_key(value)]
    if root in normalized_variants:
        return root
    return sorted(normalized_variants, key=lambda value: (-len(value.split()), -len(value), value))[0]


def _concept_weight(variant_count: int, token_count: int) -> float:
    weight = 0.45 + min(variant_count, 5) * 0.12 + min(token_count, 5) * 0.04
    return round(min(weight, 0.95), 4)


def build_enriched_concepts(enriched_signals: Sequence[Any]) -> Dict[str, List[dict]]:
    clusters: dict[tuple[str, str], list[str]] = defaultdict(list)

    for item in list(enriched_signals or []):
        raw_text, domain_hint = _extract_text(item)
        variant = _normalize_variant(raw_text)
        if not variant:
            continue
        root = _normalize_root(variant)
        domain = _infer_output_domain(variant, domain_hint, root)
        if not _is_valid_signal(variant, domain, root):
            continue
        key = _cluster_key(root, domain)
        if variant not in clusters[key]:
            clusters[key].append(variant)

    concept_signals: list[dict] = []
    for (root, domain), variants in sorted(clusters.items(), key=lambda item: (item[0][1], item[0][0])):
        concept = _best_concept(root, variants)
        tokens = [token for token in normalize_canonical_key(concept).split() if token]
        concept_signals.append(
            {
                "concept": concept,
                "normalized": root,
                "variants": list(variants),
                "tokens": tokens,
                "domain": domain,
                "weight": _concept_weight(len(variants), len(tokens)),
            }
        )

    concept_signals.sort(key=lambda item: (-float(item.get("weight") or 0.0), item.get("domain") or "", item.get("normalized") or ""))
    return {"concept_signals": concept_signals}
