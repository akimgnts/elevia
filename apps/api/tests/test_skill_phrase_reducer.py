import pytest

from compass.canonical.canonical_store import get_canonical_store, reset_canonical_store, normalize_canonical_key
from compass.extraction.skill_phrase_reducer import reduce_phrase_to_skill_candidates


def _has_canonical_hit(candidate: str) -> bool:
    store = get_canonical_store()
    key = normalize_canonical_key(candidate)
    return key in store.alias_to_id or key in store.tool_to_ids


@pytest.fixture(autouse=True)
def _reset_store():
    reset_canonical_store()
    yield
    reset_canonical_store()


def test_reducer_api_rest_power_bi():
    kept, _trace = reduce_phrase_to_skill_candidates("API REST JSON Power BI")
    assert "api rest" in kept
    assert "power bi" in kept


def test_reducer_ai_driven_scoring_models():
    kept, _trace = reduce_phrase_to_skill_candidates("AI-driven scoring models")
    assert "ai" in kept


def test_reducer_ingestion_pipeline():
    kept, _trace = reduce_phrase_to_skill_candidates("multi-source ingestion pipelines")
    assert "data pipeline" in kept


def test_reducer_keeps_only_canonical_hits():
    kept, _trace = reduce_phrase_to_skill_candidates("communication and decision-making")
    assert all(_has_canonical_hit(k) for k in kept)
