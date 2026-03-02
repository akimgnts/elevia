"""
compass/offer_enricher.py — Offer pipeline enrichment + Market Radar.

PIPELINE (Offres):
  Offre → Extraction déterministe → ESCO mapping → Cluster
  → Détection termes non-ESCO fréquents → Validation déterministe
  → Update cluster library → Generate market_radar_report.json

No LLM triggered from offer pipeline (only from CV pipeline).
Score invariance: NEVER reads or writes score_core.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from .cluster_library import ClusterLibraryStore, get_library
from .contracts import ClusterLibraryMetrics, MarketRadarReport
from .cv_enricher import extract_candidate_tokens   # reuse same extraction logic

logger = logging.getLogger(__name__)


class OfferEnrichmentResult:
    """Lightweight result from processing one offer."""
    __slots__ = ("new_tokens_recorded", "newly_activated", "cluster")

    def __init__(
        self,
        cluster: Optional[str],
        new_tokens_recorded: List[str],
        newly_activated: List[str],
    ) -> None:
        self.cluster = cluster
        self.new_tokens_recorded = new_tokens_recorded
        self.newly_activated = newly_activated


def enrich_offer(
    offer_text: str,
    cluster: Optional[str],
    esco_skills: List[str],
    *,
    library: Optional[ClusterLibraryStore] = None,
) -> OfferEnrichmentResult:
    """
    Process an offer for Market Radar: extract non-ESCO tokens, record in library.

    No LLM. Purely deterministic.

    Args:
        offer_text:   Raw offer description
        cluster:      Offer cluster (e.g. "DATA_IT") or None
        esco_skills:  ESCO skill labels matched to this offer
        library:      Override library store (for testing)

    Score invariance: score_core is NEVER read or written here.
    """
    if not offer_text or not offer_text.strip() or not cluster:
        return OfferEnrichmentResult(cluster=cluster, new_tokens_recorded=[], newly_activated=[])

    lib = library or get_library()

    candidates = extract_candidate_tokens(offer_text, esco_skills)

    recorded: List[str] = []
    activated: List[str] = []

    for token in candidates:
        status = lib.record_offer_token(cluster, token)
        if status in ("PENDING", "ACTIVE"):
            recorded.append(token)
        if status == "ACTIVE":
            activated.append(token)

    return OfferEnrichmentResult(
        cluster=cluster,
        new_tokens_recorded=recorded,
        newly_activated=activated,
    )


def generate_market_radar(
    *,
    top_n: int = 10,
    library: Optional[ClusterLibraryStore] = None,
    save: bool = True,
) -> MarketRadarReport:
    """
    Generate the Market Radar report from current library state.

    Args:
        top_n:   Number of top emerging skills per cluster
        library: Override library store (for testing)
        save:    If True, also write to data/reports/market_radar_report.json

    Returns:
        MarketRadarReport
    """
    lib = library or get_library()
    report = lib.generate_market_radar(top_n=top_n)
    if save:
        lib.save_reports()
    return report


def generate_library_metrics(
    *,
    library: Optional[ClusterLibraryStore] = None,
    save: bool = True,
) -> ClusterLibraryMetrics:
    """
    Generate cluster library metrics.

    Args:
        library: Override library store (for testing)
        save:    If True, also write to data/reports/cluster_library_metrics.json

    Returns:
        ClusterLibraryMetrics
    """
    lib = library or get_library()
    metrics = lib.get_metrics()
    if save:
        lib.save_reports()
    return metrics
