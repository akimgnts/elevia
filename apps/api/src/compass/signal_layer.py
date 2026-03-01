"""
compass/signal_layer.py — Deterministic signal layer for offer scoring.

Pure functions (except registry loaders).
No IO in core functions. No randomness. No LLM calls.
No changes to scoring formula — post-layer only.

IDF note: when URI scoring is active (ELEVIA_SCORE_USE_URIS=1, default),
IDF keys are lowercase ESCO URIs. When label scoring, keys are normalized labels.
Generic ratio falls back to count ratio when IDF keys don't match skill keys (documented).
"""
from __future__ import annotations

import json
import os
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .contracts import (
    ExplainPayloadV1,
    ExplainPayloadV1Compact,
    SkillRef,
    ToolNote,
)
from .context_engine import compute_cluster_level

_EPS = 1e-9
_REGISTRY_DIR = Path(__file__).parent / "registry"
_VERTICALS_DIR = Path(__file__).parent.parent / "verticals"


# ── Text normalization ────────────────────────────────────────────────────────

def normalize_text(s: str) -> str:
    """Lower, strip, NFKD de-accent. Matches existing canonicalization utilities."""
    if not s:
        return ""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_only.lower().strip()


# ── Registry loaders (module-level cache via lru_cache) ───────────────────────

@lru_cache(maxsize=1)
def load_generic_set(path: Optional[str] = None) -> Set[str]:
    """Load generic skills registry. Returns set of normalized labels."""
    p = Path(path) if path else _REGISTRY_DIR / "generic_skills.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return frozenset(normalize_text(item["label"]) for item in data.get("items", []))


@lru_cache(maxsize=1)
def load_tool_registry(path: Optional[str] = None) -> Dict:
    """Load tool ambiguity registry."""
    p = Path(path) if path else _REGISTRY_DIR / "tool_ambiguity_registry.json"
    return json.loads(p.read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def load_vertical_config(vertical: str = "elevia") -> Dict:
    """Load vertical config JSON."""
    p = _VERTICALS_DIR / vertical / "config.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def get_signal_cfg(vertical: str = "elevia") -> Dict:
    """Return signal_layer config dict for the vertical."""
    return load_vertical_config(vertical).get("signal_layer", {})


def _debug_signal_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_SIGNAL", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


# ── Core metric functions ─────────────────────────────────────────────────────

def compute_coverage_ratio(
    matched_offer_uris: Set[str],
    offer_uris: Set[str],
) -> float:
    """
    Fraction of offer skills matched.
    coverage_ratio = |matched ∩ offer| / |offer|
    """
    if not offer_uris:
        return 0.0
    return round(len(matched_offer_uris & offer_uris) / len(offer_uris), 4)


def compute_rare_signal(
    matched_offer_uris: Set[str],
    offer_uris: Set[str],
    idf_map: Dict[str, float],
) -> Tuple[float, str]:
    """
    IDF-weighted rare signal ratio.

    rare_signal = sum_idf(matched_offer_uris ∩ offer_uris) / max(ε, sum_idf(offer_uris))

    Levels (configurable via vertical config):
      < 0.30 → LOW
      < 0.55 → MED
      else   → HIGH
    """
    intersection = matched_offer_uris & offer_uris
    sum_matched = sum(idf_map.get(u, 1.0) for u in intersection)
    sum_offer = sum(idf_map.get(u, 1.0) for u in offer_uris)
    ratio = sum_matched / max(_EPS, sum_offer)
    ratio = round(ratio, 4)

    cfg = get_signal_cfg()
    thresholds = cfg.get("rare_signal_thresholds", {})
    low_t = float(thresholds.get("low", 0.30))
    med_t = float(thresholds.get("med", 0.55))

    if ratio < low_t:
        level = "LOW"
    elif ratio < med_t:
        level = "MED"
    else:
        level = "HIGH"

    return ratio, level


def compute_generic_ratio(
    matched_skill_keys: List[str],
    idf_map: Dict[str, float],
    generic_set: Set[str],
) -> float:
    """
    Fraction of matched skill IDF-weight that is generic.

    generic_ratio = sum_idf(generic_matched) / max(ε, sum_idf(matched_all))

    Fallback: count ratio when IDF values aren't available for the given keys
    (e.g. when keys are labels but IDF was built from URIs). The fallback is
    documented and does not affect scoring.
    """
    if not matched_skill_keys:
        return 0.0

    generic_matched = [k for k in matched_skill_keys if normalize_text(k) in generic_set]

    # Prefer IDF-weighted
    idf_all = [idf_map.get(k, None) for k in matched_skill_keys]
    has_idf = any(v is not None for v in idf_all)

    if has_idf:
        sum_generic = sum(idf_map.get(k, 1.0) for k in generic_matched)
        sum_all = sum(idf_map.get(k, 1.0) for k in matched_skill_keys)
        if sum_all < _EPS:
            return 0.0
        return round(sum_generic / sum_all, 4)
    else:
        # Fallback: count ratio (IDF keys don't match — likely URI vs label mismatch)
        return round(len(generic_matched) / max(1, len(matched_skill_keys)), 4)


def analyze_tools(
    offer_text: str,
    offer_skill_labels: List[str],
    offer_cluster_level: str,
    tool_registry: Dict,
    max_hits: int = 5,
) -> List[ToolNote]:
    """
    Detect ambiguous tools from the registry in offer text and skill labels.

    For each detected tool:
    - If max sense hits >= min_context_hits → SPECIFIED with dominant sense
    - Else → UNSPECIFIED

    Returns stable-sorted list by tool_key.
    """
    offer_norm = normalize_text(offer_text or "")
    skill_norms = {normalize_text(s) for s in offer_skill_labels if s}

    notes: List[ToolNote] = []

    for tool_def in tool_registry.get("tools", []):
        tool_key = tool_def["tool_key"]
        aliases = [normalize_text(a) for a in tool_def.get("aliases", []) if a]
        min_hits = int(tool_def.get("min_context_hits", 1))

        # Check presence: alias in text or in skill labels
        found = any(
            (a and (a in offer_norm or a in skill_norms))
            for a in aliases
        )
        if not found:
            continue

        # Count sense hits
        senses = tool_def.get("senses", [])
        best_sense: Optional[str] = None
        best_hits: List[str] = []
        best_count = 0

        for sense_def in senses:
            sense = sense_def.get("sense", "")
            disambiguators = [normalize_text(d) for d in sense_def.get("disambiguators", []) if d]
            hit_tokens = [d for d in disambiguators if d and d in offer_norm]
            count = len(hit_tokens)
            if count > best_count:
                best_count = count
                best_sense = sense
                best_hits = hit_tokens[:max_hits]

        if best_count >= min_hits:
            notes.append(ToolNote(
                tool_key=tool_key,
                status="SPECIFIED",
                sense=best_sense,
                hits=best_hits[:max_hits],
            ))
        else:
            notes.append(ToolNote(
                tool_key=tool_key,
                status="UNSPECIFIED",
                sense=None,
                hits=[],
            ))

    # Stable sort by tool_key
    notes.sort(key=lambda n: n.tool_key)
    return notes


def compute_confidence(
    score_core: float,
    rare_signal_level: str,
    cluster_level: str,
    generic_ratio: float,
    tool_notes: List[ToolNote],
    cfg: Dict,
) -> Tuple[str, List[str]]:
    """
    Compute confidence level and incoherence reasons.

    Incoherence reasons (sorted, stable):
      GENERIC_DOMINANCE      — generic_ratio > cfg.generic_cap_ratio
      TOOL_UNSPECIFIED:<key> — any tool with UNSPECIFIED status
      LOW_RARE_SIGNAL        — rare_signal_level == "LOW"
      CLUSTER_OUT            — cluster_level == "OUT"

    Confidence baseline:
      base = min(rare_signal_conf, cluster_conf)
      if any reasons → cap at "MED"
      if rare_signal_level == "LOW" → force "LOW"
    """
    generic_cap = float(cfg.get("generic_cap_ratio", 0.15))

    reasons: List[str] = []
    if generic_ratio > generic_cap:
        reasons.append("GENERIC_DOMINANCE")
    for note in tool_notes:
        if note.status == "UNSPECIFIED":
            reasons.append(f"TOOL_UNSPECIFIED:{note.tool_key}")
    if rare_signal_level == "LOW":
        reasons.append("LOW_RARE_SIGNAL")
    if cluster_level == "OUT":
        reasons.append("CLUSTER_OUT")

    reasons = sorted(set(reasons))

    # Map to numeric confidence values
    signal_val = {"LOW": 0, "MED": 1, "HIGH": 2}.get(rare_signal_level, 1)
    cluster_val = {"STRICT": 2, "NEIGHBOR": 1, "OUT": 0}.get(cluster_level, 1)
    base_val = min(signal_val, cluster_val)
    confidence = {0: "LOW", 1: "MED", 2: "HIGH"}[base_val]

    # Cap and force rules
    if reasons and confidence == "HIGH":
        confidence = "MED"
    if rare_signal_level == "LOW":
        confidence = "LOW"

    return confidence, reasons


# ── Main builder ──────────────────────────────────────────────────────────────

def build_explain_payload_v1(
    score_core: float,
    matched_skills: List[SkillRef],
    offer_skills: List[SkillRef],
    offer_text: str,
    domain_bucket: str,
    idf_map: Dict[str, float],
    cfg: Dict,
    generic_set: Optional[Set[str]] = None,
    tool_registry: Optional[Dict] = None,
) -> ExplainPayloadV1:
    """
    Build the full ExplainPayloadV1 from already-available scoring outputs.

    Does NOT recompute score_core — reads it as given.
    Ordering: by (-idf, label) — deterministic, no randomness.
    """
    generic_set = generic_set if generic_set is not None else load_generic_set()
    tool_registry = tool_registry if tool_registry is not None else load_tool_registry()
    debug_signal = _debug_signal_enabled()

    # Derive key sets (URI preferred, fallback to normalized label)
    def _key(s: SkillRef) -> str:
        return (s.uri or "").strip() or normalize_text(s.label)

    matched_keys = [_key(s) for s in matched_skills]
    offer_keys = [_key(s) for s in offer_skills]

    matched_uri_set: Set[str] = {k for k in matched_keys if k.startswith("http")}
    offer_uri_set: Set[str] = {k for k in offer_keys if k.startswith("http")}

    # Fallback to normalized labels if no URIs available
    if not offer_uri_set:
        matched_uri_set = set(matched_keys)
        offer_uri_set = set(offer_keys)

    # Metrics
    coverage_ratio = compute_coverage_ratio(matched_uri_set, offer_uri_set)
    rare_signal, rare_signal_level = compute_rare_signal(matched_uri_set, offer_uri_set, idf_map)

    # Generic ratio: use normalized labels (fallback to count if IDF doesn't cover labels)
    matched_label_keys = [normalize_text(s.label) for s in matched_skills]
    generic_ratio = compute_generic_ratio(matched_label_keys, idf_map, generic_set)

    # Cluster level
    cluster_level = compute_cluster_level(domain_bucket)

    # Tool analysis
    offer_skill_labels = [s.label for s in offer_skills]
    tool_notes = analyze_tools(
        offer_text=offer_text,
        offer_skill_labels=offer_skill_labels,
        offer_cluster_level=cluster_level,
        tool_registry=tool_registry,
        max_hits=int(cfg.get("max_tool_hits", 5)),
    )

    # Confidence
    confidence, incoherence_reasons = compute_confidence(
        score_core=score_core,
        rare_signal_level=rare_signal_level,
        cluster_level=cluster_level,
        generic_ratio=generic_ratio,
        tool_notes=tool_notes,
        cfg=cfg,
    )

    # Stable ordering: (-idf_value, label)
    def _sort_key(s: SkillRef) -> tuple:
        k = _key(s)
        return (-idf_map.get(k, 1.0), s.label)

    matched_sorted = sorted(matched_skills, key=_sort_key)

    # Missing = offer skills not in matched set
    matched_set = set(matched_keys)
    missing_offer = [s for s in offer_skills if _key(s) not in matched_set]
    missing_sorted = sorted(missing_offer, key=_sort_key)

    max_items = int(cfg.get("max_list_items_ui", 8))

    debug_trace = None
    if debug_signal:
        debug_trace = {
            "generic_ratio": generic_ratio,
            "rare_signal": rare_signal,
            "tool_notes": [t.model_dump() for t in tool_notes],
        }

    return ExplainPayloadV1(
        score_core=round(score_core, 4),
        confidence=confidence,
        incoherence_reasons=incoherence_reasons,
        matched_skills=matched_sorted[:max_items],
        missing_offer_skills=missing_sorted[:max_items],
        coverage_ratio=coverage_ratio,
        rare_signal=rare_signal,
        rare_signal_level=rare_signal_level,
        generic_ratio=generic_ratio,
        cluster_level=cluster_level,
        tool_notes=tool_notes,
        debug_trace=debug_trace,
    )


def build_explain_compact(payload: ExplainPayloadV1, full_offer_skill_count: int) -> ExplainPayloadV1Compact:
    """Derive compact version from full payload."""
    return ExplainPayloadV1Compact(
        score_core=payload.score_core,
        confidence=payload.confidence,
        cluster_level=payload.cluster_level,
        rare_signal_level=payload.rare_signal_level,
        incoherence_reasons=payload.incoherence_reasons[:2],
        matched_count=len(payload.matched_skills),
        missing_count=len(payload.missing_offer_skills),
    )
