from compass.canonical.canonical_mapper import map_to_canonical
from compass.canonical.canonical_store import reset_canonical_store, get_canonical_store
from compass.extraction.skill_phrase_reducer import reduce_phrase_to_skill_candidates


def _map_single(term: str) -> str:
    reset_canonical_store()
    res = map_to_canonical([term])
    for m in res.mappings:
        if m.raw == term:
            return m.canonical_id
    return ""


def test_synonym_ai_maps_to_machine_learning():
    assert _map_single("ai") == "skill:machine_learning"


def test_tool_power_bi_maps_to_business_intelligence():
    reset_canonical_store()
    store = get_canonical_store()
    assert store.tool_to_ids.get("power bi")[0] == "skill:business_intelligence"


def test_reducer_plus_mapping_ai_driven_scoring_models():
    reset_canonical_store()
    kept, _ = reduce_phrase_to_skill_candidates("ai-driven scoring models")
    res = map_to_canonical(kept)
    assert any(m.canonical_id == "skill:machine_learning" for m in res.mappings)


def test_unknown_token_remains_unresolved():
    reset_canonical_store()
    res = map_to_canonical(["after-sales performance across departments"])
    assert all(m.canonical_id == "" for m in res.mappings)
