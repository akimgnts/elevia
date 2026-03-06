"""
cluster_signal_policy.py — Deterministic cluster-aware token filtering.

Used by:
- Analyze recovery pre-filter (candidates_for_ai)
- Offer domain token symmetry filter (pre-domain URI application)

No scoring core access. Deterministic only.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from compass.cluster_library import normalize_token as _lib_normalize_token

# ── Normalization ─────────────────────────────────────────────────────────────

_NON_WORD_SEP = re.compile(r"[\/_|]+")
_DASHES = re.compile(r"[\-–—]+")
_WS = re.compile(r"\s+")
_HANDLE_RE = re.compile(r"^[a-z0-9_\-]{1,8}$")
_NUMBER_ONLY = re.compile(r"^\d+([.,]\d+)?$")


def normalize_token(token: str) -> str:
    if token is None:
        return ""
    s = str(token).strip()
    if not s:
        return ""
    s = _NON_WORD_SEP.sub(" ", s)
    s = _DASHES.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return _lib_normalize_token(s)


# ── Cluster allow/block lists ─────────────────────────────────────────────────

_ALLOWLIST_BY_CLUSTER: Dict[str, set] = {
    "DATA_IT": {
        "machine learning",
        "deep learning",
        "data science",
        "data engineering",
        "data analysis",
        "data visualization",
        "data mining",
        "time series",
        "forecasting",
        "business intelligence",
        "power bi",
        "powerbi",
        "tableau",
        "dashboard",
        "dashboards",
        "etl",
        "sql",
        "python",
        "spark",
        "airflow",
        "kafka",
        "ml",
        "ai",
        "bi",
        "r",
    },
    "MARKETING_SALES": {
        "crm",
        "email marketing",
        "marketing automation",
        "seo",
        "sem",
        "google analytics",
        "campaign management",
        "lead generation",
        "salesforce",
    },
    "FINANCE_LEGAL": {
        "financial modeling",
        "risk management",
        "audit",
        "ifrs",
        "gaap",
        "excel",
        "vba",
        "valuation",
        "m&a",
        "lbo",
        "dcf",
    },
}

_BLOCKLIST_BY_CLUSTER: Dict[str, set] = {
    "DATA_IT": {
        "microsoft office",
        "word",
        "powerpoint",
        "outlook",
    },
    "MARKETING_SALES": {
        "microsoft office",
        "word",
        "powerpoint",
    },
    "FINANCE_LEGAL": {
        "powerpoint",
    },
}

_GENERIC_BLOCKLIST = {
    "business",
    "strategy",
    "management",
    "project",
    "projects",
    "team",
    "experience",
    "skills",
    "skill",
    "knowledge",
    "analysis",
    "reporting",
    "documentation",
    "communication",
    "leadership",
    "autonomie",
    "autonome",
    "rigueur",
    "anglais",
    "english",
    "francais",
    "french",
    "espagnol",
    "spanish",
    "allemand",
    "german",
    "italien",
    "italian",
    "arabe",
    "arabic",
    "paris",
    "london",
    "berlin",
    "madrid",
    "barcelona",
    "lyon",
    "marseille",
    "lille",
    "nice",
}

_GLOBAL_ALLOWLIST = {
    "bi",
    "ml",
    "ai",
    "sql",
    "r",
}


def _allowlist_for(cluster: Optional[str]) -> set:
    allow = set(_GLOBAL_ALLOWLIST)
    if cluster:
        allow.update(_ALLOWLIST_BY_CLUSTER.get(cluster, set()))
    return allow


def _blocklist_for(cluster: Optional[str]) -> set:
    if not cluster:
        return set()
    return set(_BLOCKLIST_BY_CLUSTER.get(cluster, set()))


def _is_generic(norm: str) -> bool:
    return norm in _GENERIC_BLOCKLIST


def _is_handle_or_number(norm: str, original: str) -> bool:
    if _NUMBER_ONLY.match(norm):
        return True
    # handle check uses original to avoid false positives on "SQL"
    stripped = original.strip()
    if _HANDLE_RE.match(stripped):
        if any(ch.isdigit() or ch in {"_", "-"} for ch in stripped):
            return True
    return False


def build_candidates_for_ai(
    cluster: Optional[str],
    ignored_tokens: List[str],
    noise_tokens: List[str],
    validated_esco_labels: List[str],
    *,
    max_candidates: int = 60,
) -> Dict[str, object]:
    """
    Deterministic pre-filter for AI recovery candidates.

    Returns:
      {
        "candidates": [token_norm],
        "dropped": [{"token": token_norm, "reason": reason}],
        "stats": {
          "raw_count": int,
          "candidate_count": int,
          "dropped_count": int,
          "noise_ratio": float,
          "tech_density": float,
          "dropped_by_reason": {reason: count}
        }
      }
    """
    cluster_key = (cluster or "").strip().upper() or None
    allow = _allowlist_for(cluster_key)
    block = _blocklist_for(cluster_key)

    validated_norm = {
        normalize_token(label)
        for label in (validated_esco_labels or [])
        if label
    }

    combined: List[str] = list(ignored_tokens or []) + list(noise_tokens or [])
    raw_count = len(combined)

    candidates: List[str] = []
    dropped: List[Dict[str, str]] = []
    dropped_by_reason: Dict[str, int] = {}
    seen = set()

    for tok in combined:
        if tok is None:
            continue
        original = str(tok)
        norm = normalize_token(original)
        if not norm:
            reason = "empty"
            dropped.append({"token": "", "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if norm in seen:
            continue
        seen.add(norm)

        if norm in validated_norm:
            reason = "already_validated"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if norm in block:
            reason = "blocklist"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if norm in allow:
            candidates.append(norm)
            if len(candidates) >= max_candidates:
                break
            continue

        if _is_handle_or_number(norm, original):
            reason = "handle_or_number"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if len(norm) < 3:
            reason = "too_short"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if _is_generic(norm):
            reason = "generic"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        candidates.append(norm)
        if len(candidates) >= max_candidates:
            break

    candidate_count = len(candidates)
    dropped_count = len(dropped)
    noise_ratio = dropped_count / max(1, raw_count)
    tech_density = candidate_count / max(1, raw_count)

    return {
        "candidates": candidates,
        "dropped": dropped,
        "stats": {
            "raw_count": raw_count,
            "candidate_count": candidate_count,
            "dropped_count": dropped_count,
            "noise_ratio": noise_ratio,
            "tech_density": tech_density,
            "dropped_by_reason": dropped_by_reason,
        },
    }


def filter_offer_domain_tokens(
    cluster: Optional[str],
    tokens: List[str],
) -> Dict[str, object]:
    """
    Deterministic filter for offer domain tokens.

    Returns:
      {"kept": [token_norm], "dropped": [...], "stats": {...}}
    """
    cluster_key = (cluster or "").strip().upper() or None
    allow = _allowlist_for(cluster_key)
    block = _blocklist_for(cluster_key)

    kept: List[str] = []
    dropped: List[Dict[str, str]] = []
    dropped_by_reason: Dict[str, int] = {}
    seen = set()

    for tok in tokens or []:
        if tok is None:
            continue
        original = str(tok)
        norm = normalize_token(original)
        if not norm:
            reason = "empty"
            dropped.append({"token": "", "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue
        if norm in seen:
            continue
        seen.add(norm)

        if norm in block:
            reason = "blocklist"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if norm in allow:
            kept.append(norm)
            continue

        if _is_handle_or_number(norm, original):
            reason = "handle_or_number"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if len(norm) < 3:
            reason = "too_short"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        if _is_generic(norm):
            reason = "generic"
            dropped.append({"token": norm, "reason": reason})
            dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            continue

        kept.append(norm)

    raw_count = len(tokens or [])
    kept_count = len(kept)
    dropped_count = len(dropped)

    return {
        "kept": kept,
        "dropped": dropped,
        "stats": {
            "raw_count": raw_count,
            "kept_count": kept_count,
            "dropped_count": dropped_count,
            "dropped_by_reason": dropped_by_reason,
        },
    }
