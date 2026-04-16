"""
career_intelligence_agent.py — Post-validation career decision engine.

Sits AFTER:
  CVUnderstandingAgent → ProfileStructuringAgent → ProfileEnrichmentAgent → Wizard

Responsibilities:
  - Summarise what the user is strongest at
  - Identify which offer clusters match them best
  - Surface the gaps worth fixing
  - Generate concrete, ranked recommended actions

Rules (hard):
  - NO LLM calls
  - NO mutation of career_profile
  - NO writes to DB
  - NO impact on matching core / scoring
  - Fully deterministic — same input → same output
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from copy import deepcopy
from typing import Any


# ---------------------------------------------------------------------------
# Tuneable thresholds (deterministic, no ML)
# ---------------------------------------------------------------------------

HIGH_DEMAND_THRESHOLD = 5       # min offers in a cluster to be "high demand"
MEDIUM_DEMAND_THRESHOLD = 2
HIGH_MATCH_THRESHOLD = 0.60     # avg match score to flag cluster as strong fit
GAP_CRITICAL_FREQUENCY = 3      # skill appears in ≥N offers but absent from profile
GAP_OPTIONAL_FREQUENCY = 1
MAX_ACTIONS = 8
MAX_TARGET_COMPANIES = 10
MAX_CLUSTERS = 8


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _canon(text)) if len(t) >= 3}


def _extract_profile_skills(career_profile: dict[str, Any]) -> list[str]:
    """Collect every skill label visible in the validated profile."""
    skills: list[str] = []
    for exp in career_profile.get("experiences") or []:
        for link in exp.get("skill_links") or []:
            label = str((link.get("skill") or {}).get("label") or "").strip()
            if label:
                skills.append(label)
        for item in exp.get("canonical_skills_used") or []:
            label = str((item.get("label") if isinstance(item, dict) else item) or "").strip()
            if label:
                skills.append(label)
        for item in exp.get("tools") or []:
            label = str((item.get("label") if isinstance(item, dict) else item) or "").strip()
            if label:
                skills.append(label)
    for item in career_profile.get("selected_skills") or []:
        label = str((item.get("label") if isinstance(item, dict) else item) or "").strip()
        if label:
            skills.append(label)
    return skills


def _extract_offer_skills(offer: dict[str, Any]) -> list[str]:
    """Extract required skill labels from a single offer dict."""
    skills: list[str] = []
    for key in ("required_skills", "skills", "canonical_skills", "tags"):
        raw = offer.get(key) or []
        if isinstance(raw, list):
            for item in raw:
                label = str((item.get("label") if isinstance(item, dict) else item) or "").strip()
                if label:
                    skills.append(label)
    return skills


def _match_score(profile_skill_keys: set[str], offer_skills: list[str]) -> float:
    """Jaccard-style overlap between profile skills and offer required skills."""
    if not offer_skills:
        return 0.0
    offer_keys = {_canon(s) for s in offer_skills}
    overlap = len(profile_skill_keys & offer_keys)
    return round(overlap / len(offer_keys), 4)


def _dominant_domain(career_profile: dict[str, Any]) -> str:
    """
    Infer dominant domain from base_title, experiences titles, and structuring
    report domain signals — purely via keyword mapping.
    """
    DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "software_it": ["développeur", "developer", "software", "backend", "frontend", "fullstack", "devops", "data engineer", "cloud"],
        "data_analytics": ["data", "analyst", "analytics", "bi", "sql", "power bi", "tableau", "reporting"],
        "finance": ["finance", "comptable", "contrôle de gestion", "audit", "trésorerie", "gestion financière"],
        "marketing": ["marketing", "communication", "brand", "social media", "content", "digital"],
        "hr_people": ["rh", "ressources humaines", "talent", "recrutement", "formation"],
        "supply_chain": ["supply chain", "logistique", "achat", "procurement", "operations"],
        "consulting": ["consultant", "conseil", "stratégie", "transformation"],
        "sales": ["commercial", "vente", "sales", "account", "business development"],
    }

    blob = " ".join(filter(None, [
        career_profile.get("base_title") or "",
        career_profile.get("target_title") or "",
        *[str(exp.get("title") or "") for exp in (career_profile.get("experiences") or [])],
    ])).lower()

    scores: Counter[str] = Counter()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in blob:
                scores[domain] += 1

    if not scores:
        return "general"
    return scores.most_common(1)[0][0]


def _cluster_key(offer: dict[str, Any]) -> str:
    """
    Lightweight cluster assignment using offer title keyword heuristics.
    Returns a stable, lowercase slug.
    """
    title = _canon(offer.get("title") or offer.get("job_title") or "")

    CLUSTER_MAP: list[tuple[list[str], str]] = [
        (["data engineer", "data engineering", "ingénieur données"], "data_engineering"),
        (["data analyst", "analyst data", "analyste données", "analyste data", "business analyst"], "data_analytics"),
        (["data scientist", "machine learning", "ml engineer", "ia", "ai engineer"], "data_science_ml"),
        (["backend", "back-end", "back end", "java", "python developer", "node"], "backend_dev"),
        (["frontend", "front-end", "front end", "react", "angular", "vue", "ui developer"], "frontend_dev"),
        (["fullstack", "full-stack", "full stack"], "fullstack_dev"),
        (["devops", "cloud", "infrastructure", "sre", "platform engineer"], "devops_cloud"),
        (["finance", "comptab", "contrôle de gestion", "audit", "trésor"], "finance_control"),
        (["marketing", "brand", "digital", "communication", "content"], "marketing_comms"),
        (["supply chain", "logistique", "procurement", "achats"], "supply_chain"),
        (["commercial", "sales", "account manager", "business development"], "sales_bizdev"),
        (["consultant", "conseil", "stratégie"], "consulting_strategy"),
        (["rh", "talent", "recrutement", "hr manager", "people"], "hr_people"),
        (["chef de projet", "project manager", "programme manager", "scrum"], "project_management"),
    ]

    for keywords, cluster in CLUSTER_MAP:
        for kw in keywords:
            if kw in title:
                return cluster

    return "other"


# ---------------------------------------------------------------------------
# Routing decision layer
# ---------------------------------------------------------------------------

def _decide_next_agents(
    opportunity_clusters: list[dict[str, Any]],
    blocking_gaps: list[str],
    target_companies: list[dict[str, Any]],
) -> list[str]:
    """
    Route to downstream agents based on career intelligence signals.

    Rules (in priority order):
    1. Blocking gaps present → skill remediation needed before applying
    2. Strong match + high demand → ready to apply
    3. Many qualifying companies → opportunity hunting is worth it
    4. Fallback → always route somewhere
    """
    agents: list[str] = []

    # Blocking skill gaps must be addressed before mass applications
    if blocking_gaps:
        agents.append("skill_gap_remediation_agent")

    # Strong match in a high-demand cluster → go apply
    has_strong_cluster = any(
        c["match_score_avg"] >= HIGH_MATCH_THRESHOLD and c["demand_level"] == "high"
        for c in opportunity_clusters
    )
    if has_strong_cluster:
        agents.append("application_strategy_agent")

    # Many companies hiring for this profile → targeted hunting
    if len(target_companies) >= 3:
        agents.append("opportunity_hunter_agent")

    # Always route forward — minimum: application strategy
    if not agents:
        agents.append("application_strategy_agent")

    return agents


# ---------------------------------------------------------------------------
# Public agent
# ---------------------------------------------------------------------------

class CareerIntelligenceAgent:
    def __init__(self) -> None:
        self.name = "career_intelligence_agent"
        self.version = "v1"

    def run(self, state: dict) -> dict:
        """
        Input state:
        {
            "career_profile": {...},
            "structuring_report": {...},
            "enrichment_report": {...},
            "offers": [...],
        }

        Output state (merged — all input keys preserved):
        {
            **input_state,
            "career_intelligence_report": {...},
            "next_recommended_agents": [...],
        }
        """
        career_profile = deepcopy(state.get("career_profile") or {})
        structuring_report = state.get("structuring_report") or {}
        enrichment_report = state.get("enrichment_report") or {}
        offers = list(state.get("offers") or [])

        # ── 1. Extract profile signals ──────────────────────────────────────
        profile_skills = _extract_profile_skills(career_profile)
        skill_freq: Counter[str] = Counter(_canon(s) for s in profile_skills if s)
        profile_skill_keys = set(skill_freq.keys())

        dominant_domain = _dominant_domain(career_profile)
        sorted_skills = [label for label, _ in skill_freq.most_common()]
        core_strengths = sorted_skills[:5]
        secondary_strengths = sorted_skills[5:10]

        # ── 2. Score each offer ─────────────────────────────────────────────
        scored_offers: list[dict[str, Any]] = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            offer_skills = _extract_offer_skills(offer)
            score = _match_score(profile_skill_keys, offer_skills)
            scored_offers.append({
                "offer": offer,
                "score": score,
                "cluster": _cluster_key(offer),
                "offer_skills": offer_skills,
            })

        # ── 3. Build clusters ───────────────────────────────────────────────
        cluster_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in scored_offers:
            cluster_buckets[item["cluster"]].append(item)

        opportunity_clusters: list[dict[str, Any]] = []
        for cluster_name, items in cluster_buckets.items():
            count = len(items)
            avg_score = round(sum(i["score"] for i in items) / count, 4) if count else 0.0
            demand_level = (
                "high" if count >= HIGH_DEMAND_THRESHOLD
                else "medium" if count >= MEDIUM_DEMAND_THRESHOLD
                else "low"
            )
            countries: list[str] = sorted({
                str(i["offer"].get("country") or i["offer"].get("location") or "").strip()
                for i in items
                if (i["offer"].get("country") or i["offer"].get("location") or "").strip()
            })
            companies: list[str] = sorted({
                str(i["offer"].get("company") or i["offer"].get("employer") or "").strip()
                for i in items
                if (i["offer"].get("company") or i["offer"].get("employer") or "").strip()
            })[:5]
            opportunity_clusters.append({
                "cluster": cluster_name,
                "match_score_avg": avg_score,
                "demand_level": demand_level,
                "offer_count": count,
                "countries": countries[:10],
                "example_companies": companies,
            })

        opportunity_clusters.sort(key=lambda c: (-c["match_score_avg"], -c["offer_count"]))
        opportunity_clusters = opportunity_clusters[:MAX_CLUSTERS]

        # ── 4. Market fit aggregates ────────────────────────────────────────
        country_freq: Counter[str] = Counter()
        role_freq: Counter[str] = Counter()
        sector_freq: Counter[str] = Counter()

        for item in scored_offers:
            if item["score"] < 0.1:
                continue
            offer = item["offer"]
            country = str(offer.get("country") or offer.get("location") or "").strip()
            if country:
                country_freq[country] += 1
            role = str(offer.get("title") or offer.get("job_title") or "").strip()
            if role:
                role_freq[_canon(role)] += 1
            sector = str(offer.get("sector") or offer.get("industry") or "").strip()
            if sector:
                sector_freq[_canon(sector)] += 1

        top_countries = [c for c, _ in country_freq.most_common(5)]
        top_roles = [r for r, _ in role_freq.most_common(5)]
        top_sectors = [s for s, _ in sector_freq.most_common(5)]

        # ── 5. Gap analysis ─────────────────────────────────────────────────
        offer_skill_freq: Counter[str] = Counter()
        for item in scored_offers:
            for skill in item["offer_skills"]:
                offer_skill_freq[_canon(skill)] += 1

        critical_missing: list[str] = []
        nice_to_have: list[str] = []
        for skill_key, freq in offer_skill_freq.most_common(30):
            if skill_key in profile_skill_keys:
                continue
            if freq >= GAP_CRITICAL_FREQUENCY:
                critical_missing.append(skill_key)
            elif freq >= GAP_OPTIONAL_FREQUENCY:
                nice_to_have.append(skill_key)

        # Blocking gaps = critical skills absent AND appear in high-demand clusters
        high_demand_cluster_skills: set[str] = set()
        for item in scored_offers:
            if item["cluster"] in {
                c["cluster"] for c in opportunity_clusters if c["demand_level"] == "high"
            }:
                for s in item["offer_skills"]:
                    high_demand_cluster_skills.add(_canon(s))

        blocking_gaps = [
            s for s in critical_missing
            if s in high_demand_cluster_skills
        ]

        # ── 6. Recommended actions ──────────────────────────────────────────
        recommended_actions: list[dict[str, Any]] = []

        # Training actions from critical gaps
        for skill in blocking_gaps[:3]:
            recommended_actions.append({
                "type": "skill_improvement",
                "action": f"Apprendre ou renforcer : {skill}",
                "impact": "high",
            })

        for skill in critical_missing[:3]:
            if skill in blocking_gaps:
                continue
            recommended_actions.append({
                "type": "skill_improvement",
                "action": f"Développer la compétence : {skill}",
                "impact": "medium",
            })

        # Application focus from best-matching clusters
        for cluster in opportunity_clusters[:2]:
            if cluster["match_score_avg"] >= HIGH_MATCH_THRESHOLD:
                cluster_label = cluster["cluster"].replace("_", " ")
                country_hint = f" en {cluster['countries'][0]}" if cluster["countries"] else ""
                recommended_actions.append({
                    "type": "application_target",
                    "action": f"Cibler les offres {cluster_label}{country_hint}",
                    "impact": "high",
                })

        # Company targeting
        for cluster in opportunity_clusters[:3]:
            for company in cluster["example_companies"][:2]:
                recommended_actions.append({
                    "type": "application_target",
                    "action": f"Postuler chez {company} (cluster : {cluster['cluster']})",
                    "impact": "medium",
                })

        recommended_actions = recommended_actions[:MAX_ACTIONS]

        # ── 7. Target companies ─────────────────────────────────────────────
        company_freq: Counter[str] = Counter()
        company_best_score: dict[str, float] = {}
        for item in scored_offers:
            company = str(item["offer"].get("company") or item["offer"].get("employer") or "").strip()
            if not company:
                continue
            company_freq[company] += 1
            company_best_score[company] = max(company_best_score.get(company, 0.0), item["score"])

        target_companies: list[dict[str, Any]] = []
        for company, freq in company_freq.most_common(MAX_TARGET_COMPANIES):
            score = company_best_score.get(company, 0.0)
            if freq >= 2 and score >= 0.3:
                reason = "forte fréquence d'offres + correspondance compétences"
            elif score >= HIGH_MATCH_THRESHOLD:
                reason = "correspondance compétences élevée"
            elif freq >= 3:
                reason = "recruteur fréquent sur ce marché"
            else:
                continue
            target_companies.append({
                "company": company,
                "offer_count": freq,
                "best_match_score": score,
                "reason": reason,
            })

        # ── 8. Decision layer — next agents ────────────────────────
        next_agents = _decide_next_agents(
            opportunity_clusters=opportunity_clusters,
            blocking_gaps=blocking_gaps[:5],
            target_companies=target_companies,
        )

        # ── 9. Assemble output state (merge, not replace) ───────────
        output_state = dict(state)
        output_state["career_intelligence_report"] = {
            "profile_summary": {
                "dominant_domain": dominant_domain,
                "core_strengths": core_strengths,
                "secondary_strengths": secondary_strengths,
            },
            "market_fit": {
                "top_countries": top_countries,
                "top_roles": top_roles,
                "top_sectors": top_sectors,
            },
            "opportunity_clusters": opportunity_clusters,
            "gap_analysis": {
                "critical_missing_skills": critical_missing[:10],
                "nice_to_have_skills": nice_to_have[:10],
                "blocking_gaps": blocking_gaps[:5],
            },
            "recommended_actions": recommended_actions,
            "target_companies": target_companies,
            "stats": {
                "offers_analyzed": len(offers),
                "scored_offers": len(scored_offers),
                "matching_clusters": len(opportunity_clusters),
                "profile_skills_count": len(profile_skill_keys),
                "critical_gaps_count": len(critical_missing),
            },
        }
        output_state["next_recommended_agents"] = next_agents
        return output_state
