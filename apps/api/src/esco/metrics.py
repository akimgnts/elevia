"""
metrics.py - ESCO Coverage Metrics
Sprint 24 - Phase 1

Internal metrics for measuring skill coverage.
No external API exposure.
"""

import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Set

from .loader import ESCO_VERSION

logger = logging.getLogger(__name__)


def esco_coverage(
    profile_esco_ids: Set[str],
    offer_esco_ids: Set[str],
) -> Dict[str, Any]:
    """
    Calculate ESCO skill coverage between profile and offer.

    Args:
        profile_esco_ids: Set of ESCO URIs from candidate profile
        offer_esco_ids: Set of ESCO URIs required by offer

    Returns:
        {
            "coverage": float (0..1),
            "matched": int,
            "offer_total": int,
            "missing_ids": list[str]
        }

    Examples:
        >>> esco_coverage({"A", "B", "C"}, {"A", "B", "D"})
        {"coverage": 0.67, "matched": 2, "offer_total": 3, "missing_ids": ["D"]}
    """
    if not offer_esco_ids:
        return {
            "coverage": 1.0,
            "matched": 0,
            "offer_total": 0,
            "missing_ids": [],
        }

    matched = profile_esco_ids & offer_esco_ids
    missing = offer_esco_ids - profile_esco_ids

    coverage = len(matched) / len(offer_esco_ids) if offer_esco_ids else 1.0

    return {
        "coverage": round(coverage, 4),
        "matched": len(matched),
        "offer_total": len(offer_esco_ids),
        "missing_ids": sorted(list(missing)),
    }


def detailed_coverage(
    profile_esco_ids: Set[str],
    offer_esco_ids: Set[str],
    profile_labels: Optional[Dict[str, str]] = None,
    offer_labels: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Calculate detailed ESCO skill coverage with labels.

    Args:
        profile_esco_ids: Set of ESCO URIs from candidate profile
        offer_esco_ids: Set of ESCO URIs required by offer
        profile_labels: Optional mapping of URI -> label for profile skills
        offer_labels: Optional mapping of URI -> label for offer skills

    Returns:
        Extended coverage dict with labeled skills
    """
    base = esco_coverage(profile_esco_ids, offer_esco_ids)

    matched_ids = profile_esco_ids & offer_esco_ids
    excess_ids = profile_esco_ids - offer_esco_ids

    # Add labeled sections if labels provided
    if profile_labels or offer_labels:
        profile_labels = profile_labels or {}
        offer_labels = offer_labels or {}

        base["matched_skills"] = [
            {"id": uri, "label": offer_labels.get(uri, profile_labels.get(uri, uri))}
            for uri in sorted(matched_ids)
        ]
        base["missing_skills"] = [
            {"id": uri, "label": offer_labels.get(uri, uri)}
            for uri in base["missing_ids"]
        ]
        base["excess_skills"] = [
            {"id": uri, "label": profile_labels.get(uri, uri)}
            for uri in sorted(excess_ids)
        ]

    return base


def log_mapping_run(
    mapped_count: int,
    unmapped_count: int,
    duration_ms: int,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log ESCO mapping run event.

    Args:
        mapped_count: Number of successfully mapped skills
        unmapped_count: Number of unmapped skills
        duration_ms: Mapping duration in milliseconds
        extra: Additional fields to include
    """
    log_entry = {
        "event": "esco_mapping_run",
        "esco_version": ESCO_VERSION,
        "mapped_count": mapped_count,
        "unmapped_count": unmapped_count,
        "duration_ms": duration_ms,
    }

    if extra:
        log_entry.update(extra)

    # Log as JSON to stdout
    print(json.dumps(log_entry), file=sys.stdout, flush=True)


class MappingTimer:
    """
    Context manager for timing mapping operations.

    Usage:
        with MappingTimer() as timer:
            result = map_skills(skills, store)
        log_mapping_run(len(result["mapped"]), len(result["unmapped"]), timer.duration_ms)
    """

    def __init__(self):
        self.start_time: float = 0
        self.end_time: float = 0
        self.duration_ms: int = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
        return False


def aggregate_coverage_stats(coverages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate multiple coverage results.

    Args:
        coverages: List of coverage dicts from esco_coverage()

    Returns:
        {
            "mean_coverage": float,
            "min_coverage": float,
            "max_coverage": float,
            "total_matched": int,
            "total_offer_skills": int,
            "sample_size": int
        }
    """
    if not coverages:
        return {
            "mean_coverage": 0.0,
            "min_coverage": 0.0,
            "max_coverage": 0.0,
            "total_matched": 0,
            "total_offer_skills": 0,
            "sample_size": 0,
        }

    coverage_values = [c["coverage"] for c in coverages]
    total_matched = sum(c["matched"] for c in coverages)
    total_offer = sum(c["offer_total"] for c in coverages)

    return {
        "mean_coverage": round(sum(coverage_values) / len(coverage_values), 4),
        "min_coverage": round(min(coverage_values), 4),
        "max_coverage": round(max(coverage_values), 4),
        "total_matched": total_matched,
        "total_offer_skills": total_offer,
        "sample_size": len(coverages),
    }
