import json
from pathlib import Path

from integrations.onet.repository import OnetRepository

from compass.roles.occupation_resolver import OccupationResolver
from compass.roles.role_family_map import infer_role_family_from_title
from compass.roles.role_resolver import RoleResolver
from compass.roles.title_normalization import canonicalize_title_tokens, title_family_markers


def _load_case(case_id: str) -> dict:
    path = Path("apps/api/data/eval/role_resolver_eval_cases.jsonl")
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("id") == case_id:
            return row
    raise AssertionError(f"missing case {case_id}")


def test_title_normalization_canonicalizes_multi_token_role_phrases():
    assert canonicalize_title_tokens("Business Intelligence Analyst") == ["business_intelligence", "analyst"]
    assert canonicalize_title_tokens("Data Scientist") == ["data_science", "analytics"]
    assert canonicalize_title_tokens("Supply Chain Coordinator") == ["supply_chain", "operations", "coordinator"]


def test_title_role_family_precedence_prefers_data_analytics_and_sales_over_generic_engineering():
    assert infer_role_family_from_title("data engineer") == "data_analytics"
    assert infer_role_family_from_title("business developer") == "sales"
    assert title_family_markers("Business Developer / Chargé de développement commercial")["family"] == "sales"


def test_benchmark_false_cases_now_resolve_to_expected_role_families():
    repo = OnetRepository(Path("apps/api/data/db/onet.db"))
    resolver = RoleResolver(occupation_resolver=OccupationResolver(repo=repo))

    fr_case = _load_case("PROFILE-FR-01")
    bi_case = _load_case("PROFILE-BI-03")

    fr_result = resolver.resolve(raw_title=fr_case["raw_title"], canonical_skills=fr_case["canonical_skills"])
    bi_result = resolver.resolve(raw_title=bi_case["raw_title"], canonical_skills=bi_case["canonical_skills"])

    assert fr_result["primary_role_family"] == "data_analytics"
    assert bi_result["primary_role_family"] == "sales"
