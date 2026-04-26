"""Domain affinity soft signal — pure enrichment, no scoring impact.

Single source of truth shared between the runtime inbox route and the
offline audit script (`scripts/run_domain_aware_matching_audit.py`).

Frozen invariants (see DECISIONS.md):
- This module is read-only at request time: no DB writes, no AI calls.
- `domain_affinity` is *display-only*; never used to filter, re-rank, or
  modify scores in matching_v1.
- DB taxonomy is the 11-tag set in `offer_domain_enrichment.domain_tag`.
"""
from __future__ import annotations

from typing import Iterable, Optional


# ── Strong signals (curated per domain, canonical IDs) ───────────────────────
# A CV must contain at least one strong signal to be assigned a domain;
# otherwise it is routed to "other" (low confidence).
STRONG_SIGNALS: dict[str, frozenset[str]] = {
    "data": frozenset({
        "skill:data_analysis", "skill:business_intelligence", "skill:machine_learning",
        "skill:data_mining", "skill:sql", "skill:data_visualization",
        "skill:statistical_programming", "skill:data_pipeline", "skill:data_science",
        "skill:data_engineering", "skill:big_data", "skill:etl",
        "skill:time_series_analysis", "skill:predictive_analytics", "skill:data_modeling",
    }),
    "finance": frozenset({
        "skill:accounting", "skill:financial_analysis", "skill:budgeting",
        "skill:financial_reporting", "skill:audit", "skill:controlling",
        "skill:tax", "skill:treasury", "skill:financial_modeling",
        "skill:cost_accounting", "skill:management_accounting",
    }),
    "hr": frozenset({
        "skill:recruitment", "skill:talent_acquisition", "skill:human_resources_management",
        "skill:onboarding", "skill:talent_management", "skill:performance_management",
        "skill:learning_and_development", "skill:compensation_and_benefits",
        "skill:employee_relations",
    }),
    "marketing": frozenset({
        "skill:digital_marketing", "skill:seo", "skill:content_marketing",
        "skill:social_media", "skill:campaign_management", "skill:brand_management",
        "skill:market_analysis", "skill:public_relations", "skill:product_marketing",
    }),
    "sales": frozenset({
        "skill:b2b_sales", "skill:lead_generation", "skill:account_management",
        "skill:business_development", "skill:negotiation", "skill:sales_pitch",
        "skill:customer_relationship_management",
    }),
    "supply": frozenset({
        "skill:supply_chain_management", "skill:procurement", "skill:logistics",
        "skill:inventory_management", "skill:warehouse_management", "skill:demand_planning",
        "skill:supplier_management",
    }),
    "engineering": frozenset({
        "skill:software_development", "skill:cloud_architecture", "skill:devops",
        "skill:agile", "skill:mechanical_engineering", "skill:electrical_engineering",
        "skill:industrial_engineering", "skill:process_engineering",
        "skill:quality_engineering", "skill:systems_engineering",
    }),
    "operations": frozenset({
        "skill:operations_management", "skill:lean_management", "skill:six_sigma",
        "skill:continuous_improvement",
    }),
    "legal": frozenset({
        "skill:legal_analysis", "skill:contract_management", "skill:legal_research",
        "skill:regulatory_affairs",
    }),
    "admin": frozenset({
        "skill:office_administration", "skill:administrative_support",
        "skill:executive_assistance",
    }),
}


# ── Adjacency matrix (3-level affinity classification, undirected) ───────────
# Pairs of domain tags that are considered "adjacent" (close career mobility).
# Anything else → "distant". Same domain → "aligned". Unknown/other → "neutral".
ADJACENCY: frozenset[frozenset[str]] = frozenset({
    frozenset({"data", "finance"}),
    frozenset({"data", "engineering"}),
    frozenset({"data", "marketing"}),
    frozenset({"data", "operations"}),
    frozenset({"finance", "operations"}),
    frozenset({"finance", "legal"}),
    frozenset({"sales", "marketing"}),
    frozenset({"sales", "operations"}),
    frozenset({"engineering", "supply"}),
    frozenset({"engineering", "operations"}),
    frozenset({"hr", "operations"}),
    frozenset({"hr", "admin"}),
    frozenset({"legal", "operations"}),
    frozenset({"admin", "operations"}),
})


_AFFINITY_VERSION = "v1_3_level_aligned_adjacent_distant"
_INFERENCE_VERSION = "v1_strong_only"


def infer_cv_domain(canonical_ids: Iterable[str]) -> str:
    """Infer the dominant CV domain from a list of canonical skill IDs.

    Uses STRONG_SIGNALS only (no DB lookup at request time). A profile
    needs at least one strong signal to be assigned a domain; otherwise
    returns "other".
    """
    score: dict[str, int] = {}
    for skill in canonical_ids:
        if not isinstance(skill, str):
            continue
        for domain, members in STRONG_SIGNALS.items():
            if skill in members:
                score[domain] = score.get(domain, 0) + 1
    if not score:
        return "other"
    return max(score.items(), key=lambda kv: (kv[1], kv[0]))[0]


def domain_affinity(cv_domain: str, offer_domain: Optional[str]) -> str:
    """Classify the CV↔offer domain pair into aligned / adjacent / distant / neutral."""
    if not offer_domain or offer_domain in ("unknown", "other"):
        return "neutral"
    if not cv_domain or cv_domain in ("unknown", "other"):
        return "neutral"
    if cv_domain == offer_domain:
        return "aligned"
    if frozenset({cv_domain, offer_domain}) in ADJACENCY:
        return "adjacent"
    return "distant"


def affinity_score(label: Optional[str]) -> Optional[int]:
    """Return a numeric score for the affinity label (aligned=2, adjacent=1, distant=0)."""
    if label == "aligned":
        return 2
    if label == "adjacent":
        return 1
    if label == "distant":
        return 0
    return None


def fetch_offer_domain_tags(
    connection,
    external_ids: Iterable[str],
    *,
    source: str = "business_france",
) -> dict[str, str]:
    """Bulk SELECT (external_id → domain_tag) from offer_domain_enrichment.

    Read-only. Returns an empty dict for ids not found in the enrichment table.
    Caller owns the connection lifecycle.
    """
    ids = [str(x) for x in external_ids if x]
    if not ids:
        return {}
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT external_id, domain_tag
              FROM offer_domain_enrichment
             WHERE source = %s
               AND external_id = ANY(%s)
            """,
            (source, ids),
        )
        return {str(row[0]): str(row[1]) for row in cur.fetchall() if row[1]}
