"""
compass/cv_enricher.py — CV pipeline enrichment with cluster library.

PIPELINE (CV):
  CV → ESCO mapping → Cluster → Lookup cluster library → Inject DOMAIN_SKILLS_ACTIVE
  → Trigger LLM if necessary → Validation déterministe → Update cluster library
  → Scoring (ESCO only, unchanged)

LLM trigger condition:
  cluster identified  AND  (ESCO_skill_count < threshold_cluster  OR  skill_density < DENSITY_THRESHOLD)

Score invariance: NEVER reads or writes score_core.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from typing import Dict, List, Optional, Set

from .cluster_library import ClusterLibraryStore, classify_token, normalize_token, get_library
from .contracts import CVEnrichmentResult

logger = logging.getLogger(__name__)

# ── LLM trigger thresholds ────────────────────────────────────────────────────

# Per-cluster minimum expected ESCO skills before LLM is triggered
_CLUSTER_ESCO_THRESHOLDS: Dict[str, int] = {
    "DATA_IT": 3,
    "FINANCE": 2,
    "SUPPLY_OPS": 2,
    "MARKETING_SALES": 2,
    "PROJECT_MGT": 2,
    "HR": 2,
    "SECURITY": 3,
}
_ESCO_THRESHOLD_DEFAULT = int(os.getenv("ELEVIA_CLUSTER_ESCO_MIN", "3"))
_DENSITY_THRESHOLD = float(os.getenv("ELEVIA_CLUSTER_DENSITY_MIN", "0.02"))


# ── Candidate token extraction ────────────────────────────────────────────────

# Capitalized word or acronym (with optional ++ / # / . suffix)
_CAPITAL_WORD = re.compile(
    r"\b[A-Z][A-Za-z]{1,29}(?:\+\+|#|\.NET|\.js)?\b"
    r"|\b[A-Z]{2,8}(?:\+\+)?\b"
)
# Two consecutive capitalized words (bigrams like "Power BI", "Design Thinking")
_CAPITAL_BIGRAM = re.compile(r"\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b")


def _nfkd_lower(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def extract_candidate_tokens(cv_text: str, esco_skills: List[str]) -> List[str]:
    """
    Extract candidate non-ESCO tokens from CV text.

    Strategy:
    - Capitalized words + acronyms (unigrams)
    - Two-word capitalized bigrams
    - Filter out tokens already covered by ESCO skills

    Returns deduplicated list (order = first occurrence), capped at 100.
    """
    esco_norm = {_nfkd_lower(s) for s in esco_skills if s}

    found: List[str] = []
    seen: Set[str] = set()

    # Unigrams
    for m in _CAPITAL_WORD.finditer(cv_text):
        tok = m.group().strip()
        norm = _nfkd_lower(tok)
        if norm not in seen and norm not in esco_norm and len(norm) >= 2:
            seen.add(norm)
            found.append(tok)

    # Bigrams
    for m in _CAPITAL_BIGRAM.finditer(cv_text):
        tok = m.group().strip()
        norm = _nfkd_lower(tok)
        if norm not in seen and norm not in esco_norm:
            seen.add(norm)
            found.append(tok)

    return found[:100]


def compute_skill_density(cv_text: str, esco_skills: List[str]) -> float:
    """Ratio: matched ESCO skills / total words in CV text."""
    words = cv_text.split()
    if not words:
        return 0.0
    return len(esco_skills) / len(words)


def should_trigger_llm(
    esco_skill_count: int,
    skill_density: float,
    cluster: Optional[str],
) -> bool:
    """
    LLM trigger condition:
      cluster identified  AND  (esco_count < threshold  OR  density < DENSITY_THRESHOLD)
    """
    if not cluster:
        return False
    threshold = _CLUSTER_ESCO_THRESHOLDS.get(cluster, _ESCO_THRESHOLD_DEFAULT)
    return esco_skill_count < threshold or skill_density < _DENSITY_THRESHOLD


# ── Main enrichment entry point ───────────────────────────────────────────────

def enrich_cv(
    cv_text: str,
    cluster: Optional[str],
    esco_skills: List[str],
    *,
    llm_enabled: bool = True,
    library: Optional[ClusterLibraryStore] = None,
) -> CVEnrichmentResult:
    """
    Enrich a CV profile with non-ESCO domain skills from the cluster library.

    Steps:
    1. Extract candidate tokens not already in ESCO skills
    2. Validate + record each in the library (PENDING or ACTIVE)
    3. Fetch ACTIVE skills for this cluster → DOMAIN_SKILLS_ACTIVE
    4. Decide whether to trigger LLM
    5. If LLM: call, validate, record LLM suggestions
    6. Return CVEnrichmentResult

    Args:
        cv_text:      Raw CV text (may be pre-cleaned)
        cluster:      Dominant cluster (e.g. "DATA_IT") or None
        esco_skills:  List of ESCO skill labels matched for this CV
        llm_enabled:  Set False to skip LLM (tests, explicit opt-out)
        library:      Override library store (for testing)

    Score invariance: score_core is NEVER read or written here.
    """
    if not cv_text or not cv_text.strip() or not cluster:
        return CVEnrichmentResult(
            cluster=cluster,
            domain_skills_active=[],
            domain_skills_pending=[],
            new_tokens_added=[],
            llm_triggered=False,
        )

    lib = library or get_library()

    # 1. Extract candidate tokens
    candidates = extract_candidate_tokens(cv_text, esco_skills)

    # 2. Pre-classify then record each candidate in library
    new_tokens: List[str] = []
    pending: List[str] = []
    rejected: List[Dict[str, str]] = []

    for token in candidates:
        decision, reason_code = classify_token(token)
        if decision != "DOMAIN_PENDING":
            rejected.append({
                "token": token,
                "token_norm": normalize_token(token),
                "reason_code": reason_code,
            })
            continue
        status = lib.record_cv_token(cluster, token)
        if status in ("PENDING", "ACTIVE"):
            norm = _nfkd_lower(token)
            new_tokens.append(norm)
        if status == "PENDING":
            pending.append(_nfkd_lower(token))

    # 3. Get ACTIVE skills for cluster
    active_skills = lib.get_active_skills(cluster)

    # 4. LLM trigger decision
    density = compute_skill_density(cv_text, esco_skills)
    llm_suggestions: List[Dict[str, str]] = []
    llm_triggered = False

    if llm_enabled and should_trigger_llm(len(esco_skills), density, cluster):
        try:
            from .llm_enricher import call_llm_for_skills, validate_llm_suggestions  # lazy import
            lib.increment_meta("llm_calls_total")
            raw_suggestions = call_llm_for_skills(
                cv_text=cv_text,
                cluster=cluster,
                esco_skills=esco_skills,
                unmapped_tokens=candidates[:20],
            )
            if raw_suggestions:
                llm_triggered = True
                validated = validate_llm_suggestions(raw_suggestions, cluster, esco_skills)
                for token in validated:
                    status = lib.record_cv_token(cluster, token)
                    if status in ("PENDING", "ACTIVE"):
                        llm_suggestions.append({"token": _nfkd_lower(token), "source": "LLM"})
            else:
                lib.increment_meta("llm_calls_avoided")
        except Exception as exc:
            logger.warning("cv_enricher: LLM call failed: %s", type(exc).__name__)
            lib.increment_meta("llm_calls_avoided")
    else:
        lib.increment_meta("llm_calls_avoided")

    # Refresh active after any LLM recording
    active_skills = lib.get_active_skills(cluster)

    return CVEnrichmentResult(
        cluster=cluster,
        domain_skills_active=active_skills,
        domain_skills_pending=pending[:20],
        new_tokens_added=new_tokens[:20],
        llm_triggered=llm_triggered,
        llm_suggestions=llm_suggestions,
        rejected_tokens=rejected[:50],
    )
