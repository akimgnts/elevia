"""
Tests for CareerIntelligenceAgent.

TDD contract:
  - deterministic output (same input → same output)
  - correct clustering behaviour
  - correct gap detection
  - no mutation of input career_profile
  - output shape is frontend-consumable
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.intelligence import CareerIntelligenceAgent


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_career_profile(
    *,
    title: str = "Data Analyst",
    skills: list[str] | None = None,
    tools: list[str] | None = None,
) -> dict:
    skills = skills or ["SQL", "Python", "Power BI"]
    tools = tools or ["Excel", "Tableau"]
    return {
        "schema_version": "v2",
        "base_title": title,
        "experiences": [
            {
                "title": title,
                "company": "Acme Corp",
                "skill_links": [
                    {
                        "skill": {"label": s, "uri": None},
                        "tools": [{"label": t} for t in tools],
                        "context": "reporting budgétaire",
                        "autonomy_level": "autonomous",
                    }
                    for s in skills
                ],
                "canonical_skills_used": [{"label": s, "uri": None} for s in skills],
                "tools": tools,
            }
        ],
        "selected_skills": [{"label": s, "uri": None} for s in skills],
    }


def _make_offer(
    title: str,
    company: str,
    country: str,
    skills: list[str],
    sector: str = "",
) -> dict:
    return {
        "title": title,
        "company": company,
        "country": country,
        "sector": sector,
        "required_skills": [{"label": s} for s in skills],
    }


ANALYTICS_OFFERS = [
    _make_offer("Data Analyst", "Capgemini", "Germany", ["SQL", "Python", "Power BI"]),
    _make_offer("Data Analyst", "Sopra Steria", "Spain", ["SQL", "Tableau", "Excel"]),
    _make_offer("Business Analyst", "Thales", "France", ["SQL", "Excel", "Jira"]),
    _make_offer("Business Analyst", "Airbus", "Germany", ["SQL", "Power BI", "SAP"]),
    _make_offer("Business Analyst", "BNP Paribas", "France", ["SQL", "Python", "Tableau"]),
    _make_offer("Data Analyst", "Alten", "Spain", ["SQL", "Python", "Looker"]),
    _make_offer("Backend Developer", "Criteo", "France", ["Python", "Docker", "Kubernetes"]),
    _make_offer("Backend Developer", "Deezer", "France", ["Python", "Redis", "Kafka"]),
]


# ---------------------------------------------------------------------------
# 1. Output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_returns_career_intelligence_report_key(self) -> None:
        agent = CareerIntelligenceAgent()
        result = agent.run({"career_profile": _make_career_profile(), "offers": []})
        assert "career_intelligence_report" in result

    def test_report_has_all_top_level_sections(self) -> None:
        agent = CareerIntelligenceAgent()
        report = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]
        for key in ("profile_summary", "market_fit", "opportunity_clusters", "gap_analysis", "recommended_actions", "target_companies", "stats"):
            assert key in report, f"missing section: {key}"

    def test_profile_summary_has_required_fields(self) -> None:
        agent = CareerIntelligenceAgent()
        summary = agent.run({"career_profile": _make_career_profile(), "offers": []})[
            "career_intelligence_report"
        ]["profile_summary"]
        assert "dominant_domain" in summary
        assert "core_strengths" in summary
        assert "secondary_strengths" in summary
        assert isinstance(summary["core_strengths"], list)

    def test_gap_analysis_has_required_fields(self) -> None:
        agent = CareerIntelligenceAgent()
        gap = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["gap_analysis"]
        assert "critical_missing_skills" in gap
        assert "nice_to_have_skills" in gap
        assert "blocking_gaps" in gap

    def test_stats_has_offers_analyzed(self) -> None:
        agent = CareerIntelligenceAgent()
        stats = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["stats"]
        assert stats["offers_analyzed"] == len(ANALYTICS_OFFERS)


# ---------------------------------------------------------------------------
# 2. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_produces_same_output(self) -> None:
        agent = CareerIntelligenceAgent()
        payload = {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        r1 = agent.run(deepcopy(payload))
        r2 = agent.run(deepcopy(payload))
        assert r1 == r2

    def test_independent_agent_instances_produce_same_output(self) -> None:
        payload = {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        r1 = CareerIntelligenceAgent().run(deepcopy(payload))
        r2 = CareerIntelligenceAgent().run(deepcopy(payload))
        assert r1 == r2

    def test_empty_offers_is_deterministic(self) -> None:
        agent = CareerIntelligenceAgent()
        payload = {"career_profile": _make_career_profile(), "offers": []}
        r1 = agent.run(deepcopy(payload))
        r2 = agent.run(deepcopy(payload))
        assert r1 == r2


# ---------------------------------------------------------------------------
# 3. No mutation of input
# ---------------------------------------------------------------------------

class TestNoMutation:
    def test_career_profile_is_not_mutated(self) -> None:
        agent = CareerIntelligenceAgent()
        profile = _make_career_profile()
        original = deepcopy(profile)
        agent.run({"career_profile": profile, "offers": ANALYTICS_OFFERS})
        assert profile == original

    def test_offers_list_is_not_mutated(self) -> None:
        agent = CareerIntelligenceAgent()
        offers = deepcopy(ANALYTICS_OFFERS)
        original = deepcopy(offers)
        agent.run({"career_profile": _make_career_profile(), "offers": offers})
        assert offers == original

    def test_payload_dict_is_not_mutated(self) -> None:
        agent = CareerIntelligenceAgent()
        payload = {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        original_keys = set(payload.keys())
        agent.run(payload)
        assert set(payload.keys()) == original_keys


# ---------------------------------------------------------------------------
# 4. Clustering behaviour
# ---------------------------------------------------------------------------

class TestClustering:
    def test_analytics_offers_produce_data_analytics_cluster(self) -> None:
        agent = CareerIntelligenceAgent()
        clusters = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["opportunity_clusters"]
        cluster_names = [c["cluster"] for c in clusters]
        assert "data_analytics" in cluster_names

    def test_cluster_has_required_fields(self) -> None:
        agent = CareerIntelligenceAgent()
        clusters = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["opportunity_clusters"]
        assert len(clusters) > 0
        for cluster in clusters:
            for field in ("cluster", "match_score_avg", "demand_level", "offer_count", "countries", "example_companies"):
                assert field in cluster, f"cluster missing field: {field}"

    def test_demand_level_is_high_for_large_cluster(self) -> None:
        # 6 analytics offers → should be high demand
        agent = CareerIntelligenceAgent()
        clusters = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["opportunity_clusters"]
        analytics_clusters = [c for c in clusters if c["cluster"] == "data_analytics"]
        assert analytics_clusters, "data_analytics cluster expected"
        assert analytics_clusters[0]["demand_level"] == "high"

    def test_cluster_match_score_is_between_0_and_1(self) -> None:
        agent = CareerIntelligenceAgent()
        clusters = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["opportunity_clusters"]
        for cluster in clusters:
            assert 0.0 <= cluster["match_score_avg"] <= 1.0, (
                f"bad score in cluster {cluster['cluster']}: {cluster['match_score_avg']}"
            )

    def test_clusters_sorted_by_match_score_desc(self) -> None:
        agent = CareerIntelligenceAgent()
        clusters = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["opportunity_clusters"]
        scores = [c["match_score_avg"] for c in clusters]
        assert scores == sorted(scores, reverse=True)

    def test_empty_offers_produces_empty_clusters(self) -> None:
        agent = CareerIntelligenceAgent()
        clusters = agent.run({"career_profile": _make_career_profile(), "offers": []})[
            "career_intelligence_report"
        ]["opportunity_clusters"]
        assert clusters == []

    def test_cluster_countries_come_from_offer_data(self) -> None:
        agent = CareerIntelligenceAgent()
        clusters = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["opportunity_clusters"]
        analytics_clusters = [c for c in clusters if c["cluster"] == "data_analytics"]
        assert analytics_clusters
        countries = analytics_clusters[0]["countries"]
        # Germany and Spain are present in analytics offers
        assert any(c in ("Germany", "Spain", "France") for c in countries)


# ---------------------------------------------------------------------------
# 5. Gap detection
# ---------------------------------------------------------------------------

class TestGapDetection:
    def test_skills_in_offers_but_not_profile_are_critical_gaps(self) -> None:
        profile = _make_career_profile(skills=["SQL"])  # Python and Power BI absent
        offers = [
            _make_offer("Data Analyst", "Co A", "Germany", ["SQL", "Python", "Power BI"]),
            _make_offer("Data Analyst", "Co B", "France", ["SQL", "Python", "Tableau"]),
            _make_offer("Data Analyst", "Co C", "Spain", ["SQL", "Python", "Excel"]),
        ]
        agent = CareerIntelligenceAgent()
        gap = agent.run({"career_profile": profile, "offers": offers})[
            "career_intelligence_report"
        ]["gap_analysis"]
        # python appears 3 times → critical
        assert "python" in gap["critical_missing_skills"]

    def test_skills_already_in_profile_are_not_in_gaps(self) -> None:
        profile = _make_career_profile(skills=["SQL", "Python", "Power BI"])
        offers = [_make_offer("Data Analyst", "Co", "Germany", ["SQL", "Python", "Power BI"])]
        agent = CareerIntelligenceAgent()
        gap = agent.run({"career_profile": profile, "offers": offers})[
            "career_intelligence_report"
        ]["gap_analysis"]
        for skill in ("sql", "python", "power bi"):
            assert skill not in gap["critical_missing_skills"]
            assert skill not in gap["nice_to_have_skills"]

    def test_blocking_gaps_are_subset_of_critical_missing(self) -> None:
        agent = CareerIntelligenceAgent()
        gap = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["gap_analysis"]
        critical_set = set(gap["critical_missing_skills"])
        for g in gap["blocking_gaps"]:
            assert g in critical_set, f"blocking gap '{g}' not in critical_missing"

    def test_no_gaps_when_profile_matches_all_offer_skills(self) -> None:
        skills = ["SQL", "Python", "Power BI", "Excel", "Tableau"]
        profile = _make_career_profile(skills=skills)
        offers = [_make_offer("Data Analyst", "Co", "Germany", skills)]
        agent = CareerIntelligenceAgent()
        gap = agent.run({"career_profile": profile, "offers": offers})[
            "career_intelligence_report"
        ]["gap_analysis"]
        assert gap["critical_missing_skills"] == []
        assert gap["blocking_gaps"] == []

    def test_empty_offers_produces_empty_gaps(self) -> None:
        agent = CareerIntelligenceAgent()
        gap = agent.run({"career_profile": _make_career_profile(), "offers": []})[
            "career_intelligence_report"
        ]["gap_analysis"]
        assert gap["critical_missing_skills"] == []
        assert gap["nice_to_have_skills"] == []
        assert gap["blocking_gaps"] == []


# ---------------------------------------------------------------------------
# 6. Profile summary
# ---------------------------------------------------------------------------

class TestProfileSummary:
    def test_dominant_domain_data_analytics_detected(self) -> None:
        profile = _make_career_profile(title="Data Analyst")
        agent = CareerIntelligenceAgent()
        summary = agent.run({"career_profile": profile, "offers": []})[
            "career_intelligence_report"
        ]["profile_summary"]
        assert summary["dominant_domain"] == "data_analytics"

    def test_core_strengths_reflect_profile_skills(self) -> None:
        skills = ["SQL", "Python", "Power BI"]
        profile = _make_career_profile(skills=skills)
        agent = CareerIntelligenceAgent()
        summary = agent.run({"career_profile": profile, "offers": []})[
            "career_intelligence_report"
        ]["profile_summary"]
        core_keys = {s.lower() for s in summary["core_strengths"]}
        for s in skills:
            assert s.lower() in core_keys, f"expected '{s}' in core_strengths"

    def test_empty_profile_returns_general_domain(self) -> None:
        agent = CareerIntelligenceAgent()
        summary = agent.run({"career_profile": {}, "offers": []})[
            "career_intelligence_report"
        ]["profile_summary"]
        assert summary["dominant_domain"] == "general"

    def test_core_strengths_list_length_bounded(self) -> None:
        agent = CareerIntelligenceAgent()
        summary = agent.run({"career_profile": _make_career_profile(), "offers": []})[
            "career_intelligence_report"
        ]["profile_summary"]
        assert len(summary["core_strengths"]) <= 5


# ---------------------------------------------------------------------------
# 7. Recommended actions
# ---------------------------------------------------------------------------

class TestRecommendedActions:
    def test_actions_have_type_action_impact_fields(self) -> None:
        agent = CareerIntelligenceAgent()
        actions = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["recommended_actions"]
        for action in actions:
            assert "type" in action
            assert "action" in action
            assert "impact" in action
            assert action["impact"] in ("high", "medium", "low")

    def test_action_count_bounded(self) -> None:
        agent = CareerIntelligenceAgent()
        actions = agent.run({"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS})[
            "career_intelligence_report"
        ]["recommended_actions"]
        assert len(actions) <= 8

    def test_empty_offers_produces_no_actions(self) -> None:
        agent = CareerIntelligenceAgent()
        actions = agent.run({"career_profile": _make_career_profile(), "offers": []})[
            "career_intelligence_report"
        ]["recommended_actions"]
        assert actions == []


# ---------------------------------------------------------------------------
# 8. Robustness — minimal / degenerate inputs
# ---------------------------------------------------------------------------

class TestRobustness:
    def test_handles_none_payload(self) -> None:
        agent = CareerIntelligenceAgent()
        result = agent.run({})
        assert "career_intelligence_report" in result

    def test_handles_offers_with_missing_fields(self) -> None:
        offers = [{"title": "Analyst"}, {"company": "SomeCorpo"}, {}]
        agent = CareerIntelligenceAgent()
        result = agent.run({"career_profile": _make_career_profile(), "offers": offers})
        assert "career_intelligence_report" in result

    def test_handles_career_profile_without_experiences(self) -> None:
        agent = CareerIntelligenceAgent()
        result = agent.run({"career_profile": {"schema_version": "v2", "experiences": []}, "offers": ANALYTICS_OFFERS})
        assert "career_intelligence_report" in result

    def test_handles_offers_without_required_skills(self) -> None:
        offers = [{"title": "Data Analyst", "company": "Co", "country": "Germany"}]
        agent = CareerIntelligenceAgent()
        result = agent.run({"career_profile": _make_career_profile(), "offers": offers})
        assert "career_intelligence_report" in result

    def test_non_dict_offers_are_skipped_gracefully(self) -> None:
        offers: list = ["not a dict", None, 42, _make_offer("Data Analyst", "Co", "Germany", ["SQL"])]
        agent = CareerIntelligenceAgent()
        result = agent.run({"career_profile": _make_career_profile(), "offers": offers})
        assert "career_intelligence_report" in result

    def test_stats_scored_offers_excludes_non_dicts(self) -> None:
        offers: list = ["bad", _make_offer("Data Analyst", "Co", "Germany", ["SQL"])]
        agent = CareerIntelligenceAgent()
        stats = agent.run({"career_profile": _make_career_profile(), "offers": offers})[
            "career_intelligence_report"
        ]["stats"]
        assert stats["scored_offers"] == 1


# ---------------------------------------------------------------------------
# 9. Agent contract — identity
# ---------------------------------------------------------------------------

class TestAgentContract:
    def test_agent_has_name_attribute(self) -> None:
        agent = CareerIntelligenceAgent()
        assert agent.name == "career_intelligence_agent"

    def test_agent_has_version_attribute(self) -> None:
        agent = CareerIntelligenceAgent()
        assert agent.version == "v1"

    def test_output_preserves_input_career_profile(self) -> None:
        """State merge: career_profile must be forwarded in output."""
        profile = _make_career_profile()
        state = {"career_profile": profile, "offers": ANALYTICS_OFFERS}
        result = CareerIntelligenceAgent().run(state)
        assert result["career_profile"] == profile

    def test_output_preserves_extra_state_keys(self) -> None:
        """State merge: unknown upstream keys must pass through unchanged."""
        state = {
            "career_profile": _make_career_profile(),
            "offers": ANALYTICS_OFFERS,
            "structuring_report": {"foo": "bar"},
            "enrichment_report": {"baz": 42},
        }
        result = CareerIntelligenceAgent().run(state)
        assert result["structuring_report"] == {"foo": "bar"}
        assert result["enrichment_report"] == {"baz": 42}


# ---------------------------------------------------------------------------
# 10. next_recommended_agents — routing decision layer
# ---------------------------------------------------------------------------

class TestNextAgents:
    def test_output_contains_next_recommended_agents_key(self) -> None:
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        )
        assert "next_recommended_agents" in result

    def test_next_agents_is_non_empty_list(self) -> None:
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        )
        agents = result["next_recommended_agents"]
        assert isinstance(agents, list)
        assert len(agents) >= 1

    def test_next_agents_values_are_strings(self) -> None:
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        )
        for item in result["next_recommended_agents"]:
            assert isinstance(item, str)

    def test_empty_offers_routes_to_application_strategy(self) -> None:
        """No signals → default to application_strategy_agent."""
        result = CareerIntelligenceAgent().run(
            {"career_profile": _make_career_profile(), "offers": []}
        )
        assert "application_strategy_agent" in result["next_recommended_agents"]

    def test_blocking_gaps_route_to_skill_gap_remediation(self) -> None:
        """Python missing from profile but required in 6 high-demand offers → blocking gap."""
        profile = _make_career_profile(skills=["SQL"])
        offers = [
            _make_offer("Data Analyst", f"Co {i}", "France", ["SQL", "Python"])
            for i in range(6)  # 6 offers → HIGH demand (≥5 threshold)
        ]
        result = CareerIntelligenceAgent().run({"career_profile": profile, "offers": offers})
        assert "skill_gap_remediation_agent" in result["next_recommended_agents"]

    def test_high_match_high_demand_routes_to_application_strategy(self) -> None:
        """Profile matches ≥60% and cluster has ≥5 offers → high demand → application_strategy."""
        profile = _make_career_profile(skills=["SQL", "Python", "Power BI"])
        offers = [
            _make_offer("Data Analyst", f"Co {i}", "France", ["SQL", "Python", "Power BI"])
            for i in range(6)  # 6 offers → HIGH demand
        ]
        result = CareerIntelligenceAgent().run({"career_profile": profile, "offers": offers})
        assert "application_strategy_agent" in result["next_recommended_agents"]

    def test_many_target_companies_routes_to_opportunity_hunter(self) -> None:
        """≥3 qualifying target companies → opportunity_hunter_agent."""
        profile = _make_career_profile(skills=["SQL", "Python", "Power BI"])
        # 4 companies, each appearing twice, each matching well → ≥3 qualify
        offers = []
        for company in ["Capgemini", "Sopra", "Thales", "Atos"]:
            for _ in range(2):
                offers.append(
                    _make_offer("Data Analyst", company, "France", ["SQL", "Python", "Power BI"])
                )
        result = CareerIntelligenceAgent().run({"career_profile": profile, "offers": offers})
        assert "opportunity_hunter_agent" in result["next_recommended_agents"]

    def test_routing_is_deterministic(self) -> None:
        from copy import deepcopy
        payload = {"career_profile": _make_career_profile(), "offers": ANALYTICS_OFFERS}
        r1 = CareerIntelligenceAgent().run(deepcopy(payload))
        r2 = CareerIntelligenceAgent().run(deepcopy(payload))
        assert r1["next_recommended_agents"] == r2["next_recommended_agents"]
