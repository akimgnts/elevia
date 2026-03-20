"""
test_canonical_mapping.py — Sprint 0700 invariance tests for the canonical mapping layer.

Tests (35):

CanonicalStore (8):
  1.  test_store_loads_real_json              — store loads, indexes non-empty
  2.  test_store_label_indexed_as_alias       — skill label resolves as synonym
  3.  test_store_alias_indexed                — explicit alias ("ml") resolves
  4.  test_store_tool_indexed                 — tool entry present, value is list
  5.  test_store_hierarchy_loaded             — 20 relations, no _comment key
  6.  test_store_missing_file_fallback        — absent path → is_loaded() False, no raise
  7.  test_store_empty_json_fallback          — {} JSON → is_loaded() True, empty indexes
  8.  test_store_deterministic_reload         — reset + reload → same alias count

CanonicalMapper (9):
  9.  test_mapper_synonym_match               — "data analysis" → synonym_match, conf=1.0
  10. test_mapper_label_as_synonym            — "machine learning" (label) → synonym_match
  11. test_mapper_tool_match                  — "python" → tool_match, conf=0.8, first canonical_id
  12. test_mapper_unresolved                  — unknown → unresolved, conf=0.0, canonical_id=""
  13. test_mapper_dedup_case_insensitive      — ["Python", "python", "PYTHON"] → 1 mapping
  14. test_mapper_preserves_unresolved        — unresolved entries kept, not dropped
  15. test_mapper_counters_exact              — mixed input → exact matched/unresolved/synonym/tool
  16. test_mapper_deterministic               — same input → identical MappingResult
  17. test_mapper_empty_store_no_exception    — store not loaded → empty MappingResult, no raise

HierarchyExpander (7):
  18. test_expander_1_level_only             — deep_learning → machine_learning added, no grandparent
  19. test_expander_no_expansion_no_parent   — skill with no hierarchy entry → unchanged
  20. test_expander_dedup_parent_in_input    — parent already present → not duplicated
  21. test_expander_input_ids_preserved      — original IDs always in expanded_ids
  22. test_expander_no_transitive_closure    — multiple children, parent added once
  23. test_expander_empty_input              — [] → empty ExpandedResult
  24. test_expander_deterministic            — same input → same output

Profile Integration (7):
  25. test_profile_canonical_fields_present         — response has 3 new fields
  26. test_profile_canonical_fields_types            — correct types (list, int, list)
  27. test_profile_canonical_ids_not_in_skills_uri  — "skill:" prefix absent from skills_uri
  28. test_profile_canonical_skills_count_gte_0     — canonical_skills_count is non-negative int
  29. test_profile_schema_unchanged                 — pre-sprint required fields still present
  30. test_profile_canonical_skills_has_strategy    — each entry in canonical_skills has strategy key
  31. test_profile_fallback_silent                  — response is 200 (canonical layer never breaks request)

Invariants métier (4):
  32. test_invariant_no_silent_drop               — len(mappings) == unique lowercase inputs
  33. test_invariant_strategies_are_exact_enum    — only 3 valid strategy values
  34. test_invariant_scoring_core_frozen          — matching_v1.py has no canonical import
  35. test_invariant_extractors_no_skill_prefix   — extractors.py does not inject "skill:" into skills_uri

Invariants hold:
  - No silent drop of unresolved skills
  - Deterministic: same input → same output
  - Fallback: store absent or broken → empty/safe result, never raises
  - Backward compatibility: ParseFileResponse required fields unchanged
  - Scoring core frozen: canonical IDs never enter skills_uri
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.canonical.canonical_mapper import MappingResult, map_to_canonical
from compass.canonical.canonical_store import (
    CanonicalStore,
    _build_store,
    get_canonical_store,
    reset_canonical_store,
)
from compass.canonical.hierarchy_expander import ExpandedResult, expand_hierarchy


# ── Minimal JSON fixture for isolated unit tests ───────────────────────────────

_MINIMAL_JSON: dict = {
    "ontology": [
        {
            "cluster_name": "DATA_ANALYTICS_AI",
            "skills": [
                {
                    "canonical_skill_id": "skill:machine_learning",
                    "label": "Machine Learning",
                    "skill_type": "technical",
                    "genericity_score": 0.7,
                    "aliases": ["ml", "apprentissage automatique", "predictive modeling"],
                },
                {
                    "canonical_skill_id": "skill:deep_learning",
                    "label": "Deep Learning",
                    "skill_type": "technical",
                    "genericity_score": 0.5,
                    "aliases": ["dl", "neural networks"],
                },
                {
                    "canonical_skill_id": "skill:data_analysis",
                    "label": "Data Analysis",
                    "skill_type": "technical",
                    "genericity_score": 0.8,
                    "aliases": ["data analytics", "eda"],
                },
            ],
        }
    ],
    "normalization_mappings": {
        "synonym_to_canonical": {
            "analyse de données": "skill:data_analysis",
        },
        "tool_to_canonical": {
            "python": ["skill:machine_learning", "skill:data_analysis"],
            "tensorflow": ["skill:machine_learning"],
        },
    },
    "hierarchy": {
        "_comment": "Explicit 1-level parent relations only.",
        "skill:deep_learning": "skill:machine_learning",
    },
}


def _make_store(data: dict = None) -> CanonicalStore:
    """Build an in-memory CanonicalStore from dict (no file I/O)."""
    return _build_store(data if data is not None else _MINIMAL_JSON)


def _empty_store() -> CanonicalStore:
    """Return an unloaded CanonicalStore."""
    return CanonicalStore()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CanonicalStore
# ═══════════════════════════════════════════════════════════════════════════════


def test_store_loads_real_json():
    """Store loads canonical_skills_core.json; all indexes non-empty."""
    store = get_canonical_store()
    assert store.is_loaded(), "Store must report loaded=True after successful JSON load"
    assert len(store.alias_to_id) > 100, f"Expected >100 aliases, got {len(store.alias_to_id)}"
    assert len(store.tool_to_ids) >= 30, f"Expected >=30 tools, got {len(store.tool_to_ids)}"
    assert len(store.id_to_skill) >= 100, f"Expected >=100 skills, got {len(store.id_to_skill)}"
    assert len(store.hierarchy) == 20, f"Expected 20 hierarchy entries, got {len(store.hierarchy)}"


def test_store_v12_non_tech_overlay_aliases_are_available():
    store = get_canonical_store()
    assert store.alias_to_id.get("administration du personnel") == "skill:hr_administration"
    assert store.alias_to_id.get("controle de gestion") == "skill:management_control"
    assert store.alias_to_id.get("traitement des factures") == "skill:accounts_payable"
    assert store.alias_to_id.get("hubspot") == "skill:hubspot"


def test_store_final_exact_tool_and_language_overlays_are_available():
    store = get_canonical_store()
    assert store.alias_to_id.get("anglais") == "skill:english_language"
    assert store.tool_to_ids.get("excel") == ["skill:excel"]
    assert store.tool_to_ids.get("power bi") == ["skill:power_bi"]
    assert store.tool_to_ids.get("salesforce") == ["skill:salesforce"]
    assert store.tool_to_ids.get("sap") == ["skill:sap"]
    assert store.tool_to_ids.get("looker studio") == ["skill:looker_studio"]


def test_store_v13_logistics_procurement_overlay_aliases_are_available():
    store = get_canonical_store()
    assert store.alias_to_id.get("suivi fournisseurs") == "skill:vendor_management"
    assert store.alias_to_id.get("passation de commandes fournisseurs") == "skill:procurement_basics"
    assert store.alias_to_id.get("coordination production") == "skill:operations_management"
    assert store.alias_to_id.get("reporting") == "skill:business_intelligence"
    assert store.alias_to_id.get("coordination avec les prestataires") == "skill:logistics_coordination"


def test_store_label_indexed_as_alias():
    """Skill label ('Machine Learning') must resolve via alias_to_id (label-as-self-alias fix)."""
    store = _make_store()
    assert "machine learning" in store.alias_to_id, (
        "'machine learning' (label lowercased) must be in alias_to_id"
    )
    assert store.alias_to_id["machine learning"] == "skill:machine_learning"


def test_store_alias_indexed():
    """Explicit alias ('ml') must resolve to correct canonical_id."""
    store = _make_store()
    assert store.alias_to_id.get("ml") == "skill:machine_learning", (
        "Explicit alias 'ml' must map to skill:machine_learning"
    )


def test_store_tool_indexed():
    """Tool entry ('python') must be in tool_to_ids, value must be non-empty list."""
    store = _make_store()
    targets = store.tool_to_ids.get("python")
    assert targets is not None, "'python' must be in tool_to_ids"
    assert isinstance(targets, list) and len(targets) > 0
    assert all(isinstance(t, str) for t in targets)


def test_store_hierarchy_loaded():
    """Hierarchy must have exactly 1 entry from minimal fixture; _comment skipped."""
    store = _make_store()
    # Only the one real relation (not _comment)
    assert store.hierarchy == {"skill:deep_learning": "skill:machine_learning"}, (
        "Hierarchy must contain only explicit child→parent pairs (no _comment key)"
    )


def test_store_missing_file_fallback(monkeypatch, tmp_path):
    """If JSON file absent, store is_loaded() == False, no exception raised."""
    absent_path = tmp_path / "nonexistent.json"
    monkeypatch.setenv("ELEVIA_CANONICAL_SKILLS_PATH", str(absent_path))
    reset_canonical_store()
    try:
        store = get_canonical_store()
        assert not store.is_loaded(), "Missing file must produce is_loaded()=False"
        assert store.alias_to_id == {}
        assert store.tool_to_ids == {}
        assert store.id_to_skill == {}
        assert store.hierarchy == {}
    finally:
        reset_canonical_store()
        monkeypatch.delenv("ELEVIA_CANONICAL_SKILLS_PATH", raising=False)


def test_store_empty_json_fallback(monkeypatch, tmp_path):
    """Empty JSON object {} must produce a loaded store with empty indexes (no exception)."""
    json_path = tmp_path / "empty.json"
    json_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ELEVIA_CANONICAL_SKILLS_PATH", str(json_path))
    reset_canonical_store()
    try:
        store = get_canonical_store()
        assert store.is_loaded(), "Empty JSON {} must still set loaded=True"
        assert store.alias_to_id == {}
        assert store.tool_to_ids == {}
        assert store.id_to_skill == {}
        assert store.hierarchy == {}
    finally:
        reset_canonical_store()
        monkeypatch.delenv("ELEVIA_CANONICAL_SKILLS_PATH", raising=False)


def test_store_deterministic_reload(monkeypatch):
    """Reset + reload from same file must produce identical alias count."""
    store1 = get_canonical_store()
    count1 = len(store1.alias_to_id)
    reset_canonical_store()
    store2 = get_canonical_store()
    count2 = len(store2.alias_to_id)
    assert count1 == count2, (
        f"Alias count must be deterministic across reloads: {count1} != {count2}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CanonicalMapper
# ═══════════════════════════════════════════════════════════════════════════════


def test_mapper_synonym_match():
    """Known alias 'data analysis' → strategy=synonym_match, confidence=1.0."""
    store = _make_store()
    result = map_to_canonical(["data analysis"], store=store)
    assert result.matched_count == 1
    assert result.unresolved_count == 0
    assert result.synonym_count == 1
    m = result.mappings[0]
    assert m.strategy == "synonym_match"
    assert m.confidence == 1.0
    assert m.canonical_id == "skill:data_analysis"
    assert m.raw == "data analysis"


def test_mapper_label_as_synonym():
    """Skill label 'machine learning' must resolve via synonym_match (label-as-alias invariant)."""
    store = _make_store()
    result = map_to_canonical(["machine learning"], store=store)
    assert result.matched_count == 1
    m = result.mappings[0]
    assert m.strategy == "synonym_match", (
        "Skill labels must be indexed as self-aliases → synonym_match strategy"
    )
    assert m.canonical_id == "skill:machine_learning"
    assert m.confidence == 1.0


def test_mapper_tool_match():
    """Tool 'python' → strategy=tool_match, conf=0.8, canonical_id = first target."""
    store = _make_store()
    result = map_to_canonical(["python"], store=store)
    assert result.tool_count == 1
    m = result.mappings[0]
    assert m.strategy == "tool_match"
    assert m.confidence == 0.8
    # First target from tool_to_ids["python"]
    first_target = store.tool_to_ids["python"][0]
    assert m.canonical_id == first_target


def test_mapper_mvp_overlay_domain_skills():
    result = map_to_canonical(["audit", "internal control", "compliance", "legal counsel"])
    resolved = {m.raw: m.canonical_id for m in result.mappings}
    assert resolved["audit"] == "skill:audit"
    assert resolved["internal control"] == "skill:internal_control"
    assert resolved["compliance"] == "skill:compliance"
    assert resolved["legal counsel"] == "skill:legal_analysis"


def test_mapper_mvp_overlay_tool_expansions():
    result = map_to_canonical(["databricks", "looker studio", "flask", "opencv", "javascript", "scala"])
    resolved = {m.raw: m.canonical_id for m in result.mappings}
    assert resolved["databricks"] == "skill:data_engineering"
    assert resolved["looker studio"] == "skill:looker_studio"
    assert resolved["flask"] == "skill:backend_development"
    assert resolved["opencv"] == "skill:machine_learning"
    assert resolved["javascript"] == "skill:frontend_development"
    assert resolved["scala"] == "skill:backend_development"


def test_mapper_unresolved():
    """Unknown label → strategy=unresolved, conf=0.0, canonical_id=''."""
    store = _make_store()
    result = map_to_canonical(["lorem ipsum foobar"], store=store)
    assert result.unresolved_count == 1
    assert result.matched_count == 0
    m = result.mappings[0]
    assert m.strategy == "unresolved"
    assert m.confidence == 0.0
    assert m.canonical_id == ""
    assert m.label == ""


def test_mapper_dedup_case_insensitive():
    """['Python', 'python', 'PYTHON'] must produce exactly 1 mapping (case-insensitive dedup)."""
    store = _make_store()
    result = map_to_canonical(["Python", "python", "PYTHON"], store=store)
    assert len(result.mappings) == 1, (
        f"Case-insensitive dedup must yield 1 mapping, got {len(result.mappings)}"
    )


def test_mapper_preserves_unresolved():
    """Unresolved entries must appear in mappings — never silently dropped."""
    store = _make_store()
    labels = ["machine learning", "xyz_unknown_skill_42"]
    result = map_to_canonical(labels, store=store)
    # Both must appear in mappings
    assert len(result.mappings) == 2, (
        "Unresolved entries must be kept in mappings, not dropped"
    )
    strategies = {m.strategy for m in result.mappings}
    assert "unresolved" in strategies
    assert "synonym_match" in strategies


def test_mapper_counters_exact():
    """Mixed input → matched/unresolved/synonym/tool counters must be exact."""
    store = _make_store()
    # synonym: "data analysis", "ml" → 2 synonym
    # tool: "tensorflow" → 1 tool  (but "tensorflow" maps to skill:machine_learning via tool)
    # unresolved: "lorem ipsum" → 1
    labels = ["data analysis", "ml", "tensorflow", "lorem ipsum"]
    result = map_to_canonical(labels, store=store)
    assert result.matched_count == 3     # data analysis + ml + tensorflow
    assert result.unresolved_count == 1  # lorem ipsum
    assert result.synonym_count == 2     # data analysis + ml
    assert result.tool_count == 1        # tensorflow


def test_mapper_deterministic():
    """Same input → identical MappingResult (strategies, confidences, order)."""
    store = _make_store()
    labels = ["machine learning", "python", "deep learning", "eda", "unknown_xyz"]
    r1 = map_to_canonical(labels, store=store)
    r2 = map_to_canonical(labels, store=store)
    assert [(m.raw, m.strategy, m.canonical_id, m.confidence) for m in r1.mappings] == \
           [(m.raw, m.strategy, m.canonical_id, m.confidence) for m in r2.mappings], (
        "map_to_canonical must be deterministic"
    )
    assert r1.matched_count == r2.matched_count
    assert r1.unresolved_count == r2.unresolved_count


def test_mapper_empty_store_no_exception():
    """Unloaded store must return empty MappingResult without raising."""
    store = _empty_store()
    assert not store.is_loaded()
    result = map_to_canonical(["machine learning", "python"], store=store)
    assert isinstance(result, MappingResult)
    assert result.mappings == []
    assert result.matched_count == 0
    assert result.unresolved_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — HierarchyExpander
# ═══════════════════════════════════════════════════════════════════════════════


def test_expander_1_level_only():
    """deep_learning → adds machine_learning (1 level). No grandparent added."""
    store = _make_store()
    # deep_learning → machine_learning (1 level)
    # machine_learning has no parent in minimal fixture → no grandparent possible
    result = expand_hierarchy(["skill:deep_learning"], store=store)
    assert "skill:deep_learning" in result.expanded_ids, "Input ID must be preserved"
    assert "skill:machine_learning" in result.expanded_ids, "Parent must be added"
    assert "skill:machine_learning" in result.added_parents
    assert result.expansion_map == {"skill:deep_learning": "skill:machine_learning"}


def test_expander_1_level_real_hierarchy():
    """Using real store: deep_learning parent is machine_learning, not its grandparent."""
    store = get_canonical_store()
    # machine_learning has no parent in the hierarchy (it IS the parent)
    parent_of_ml = store.hierarchy.get("skill:machine_learning")
    result = expand_hierarchy(["skill:deep_learning"], store=store)
    assert "skill:machine_learning" in result.expanded_ids
    # If machine_learning itself has a parent, it should NOT be in expanded_ids (1 level only)
    if parent_of_ml:
        assert parent_of_ml not in result.expanded_ids, (
            "Grandparent must never be added (1-level invariant)"
        )


def test_expander_no_expansion_no_parent():
    """ID with no hierarchy entry → ExpandedResult unchanged."""
    store = _make_store()
    # skill:data_analysis has no parent in minimal fixture
    result = expand_hierarchy(["skill:data_analysis"], store=store)
    assert result.expanded_ids == ["skill:data_analysis"]
    assert result.added_parents == []
    assert result.expansion_map == {}


def test_expander_dedup_parent_in_input():
    """If parent already in input, it must not be duplicated in expanded_ids."""
    store = _make_store()
    # deep_learning → machine_learning, but machine_learning already in input
    result = expand_hierarchy(["skill:deep_learning", "skill:machine_learning"], store=store)
    assert result.expanded_ids.count("skill:machine_learning") == 1, (
        "Parent already in input must not be duplicated"
    )
    assert result.added_parents == [], "No parent added when already present"


def test_expander_input_ids_preserved():
    """All original input IDs must appear in expanded_ids, never removed."""
    store = _make_store()
    inputs = ["skill:deep_learning", "skill:data_analysis", "skill:unknown_skill"]
    result = expand_hierarchy(inputs, store=store)
    for cid in inputs:
        assert cid in result.expanded_ids, f"Input ID {cid!r} must not be dropped"


def test_expander_no_transitive_closure():
    """Multiple children of same parent → parent added exactly once (no transitive closure)."""
    store = get_canonical_store()
    # deep_learning → machine_learning, nlp → machine_learning, mlops → machine_learning
    children = ["skill:deep_learning", "skill:nlp", "skill:mlops"]
    result = expand_hierarchy(children, store=store)
    assert result.expanded_ids.count("skill:machine_learning") == 1, (
        "machine_learning must appear exactly once even with multiple children"
    )
    assert len(result.added_parents) == 1
    assert result.added_parents[0] == "skill:machine_learning"


def test_expander_empty_input():
    """Empty input → ExpandedResult with all empty fields, no exception."""
    store = _make_store()
    result = expand_hierarchy([], store=store)
    assert isinstance(result, ExpandedResult)
    assert result.expanded_ids == []
    assert result.added_parents == []
    assert result.expansion_map == {}


def test_expander_deterministic():
    """Same input → identical ExpandedResult."""
    store = get_canonical_store()
    inputs = ["skill:deep_learning", "skill:nlp", "skill:containerization"]
    r1 = expand_hierarchy(inputs, store=store)
    r2 = expand_hierarchy(inputs, store=store)
    assert r1.expanded_ids == r2.expanded_ids
    assert r1.added_parents == r2.added_parents
    assert r1.expansion_map == r2.expansion_map


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Profile Integration (TestClient)
# ═══════════════════════════════════════════════════════════════════════════════

# CV text designed to contain known canonical skills for deterministic results
_TECH_CV = (
    "Data Analyst with 3 years experience in machine learning and data analysis. "
    "Daily use of Python, SQL, TensorFlow, Docker. Deep learning models deployed on Kubernetes. "
    "Experience with ETL pipelines and data engineering. Power BI dashboards for stakeholders."
)


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app
    return __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(app)


def _post_txt(client, text: str, filename: str = "cv.txt"):
    from fastapi.testclient import TestClient
    return client.post(
        "/profile/parse-file",
        files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


def test_profile_canonical_fields_present(client):
    """Response must include the 3 new canonical fields added in Sprint 0700."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    assert "canonical_skills" in body, "canonical_skills field missing from response"
    assert "canonical_skills_count" in body, "canonical_skills_count field missing"
    assert "canonical_hierarchy_added" in body, "canonical_hierarchy_added field missing"


def test_profile_canonical_fields_types(client):
    """canonical_skills: list, canonical_skills_count: int, canonical_hierarchy_added: list."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["canonical_skills"], list)
    assert isinstance(body["canonical_skills_count"], int)
    assert body["canonical_skills_count"] >= 0
    assert isinstance(body["canonical_hierarchy_added"], list)


def test_profile_canonical_ids_not_in_skills_uri(client):
    """Canonical IDs (skill:xxx prefix) must never appear in profile.skills_uri."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    profile = resp.json().get("profile", {})
    skills_uri = profile.get("skills_uri") or []
    for uri in skills_uri:
        assert not str(uri).startswith("skill:"), (
            f"Canonical ID leaked into skills_uri: {uri!r}"
        )


def test_profile_canonical_skills_count_gte_0(client):
    """canonical_skills_count must be ≥ 0 and consistent with canonical_skills list."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    resolved = sum(
        1 for m in body["canonical_skills"] if m.get("canonical_id")
    )
    assert body["canonical_skills_count"] == resolved, (
        f"canonical_skills_count={body['canonical_skills_count']} must equal "
        f"resolved entries in canonical_skills={resolved}"
    )


def test_profile_schema_unchanged(client):
    """All required pre-Sprint-0700 fields must still be present in response."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    pre_sprint_required = {
        "source", "mode", "ai_available", "ai_added_count", "filename",
        "content_type", "extracted_text_length", "canonical_count",
        "skills_raw", "skills_canonical", "profile", "warnings",
        "raw_tokens", "filtered_tokens", "validated_labels",
    }
    missing = pre_sprint_required - body.keys()
    assert not missing, f"Pre-sprint required fields missing: {missing}"


def test_profile_canonical_skills_has_strategy(client):
    """Each entry in canonical_skills must have 'strategy' key with valid value."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    canonical_skills = resp.json()["canonical_skills"]
    valid_strategies = {"synonym_match", "tool_match", "unresolved"}
    for entry in canonical_skills:
        assert "strategy" in entry, f"Missing 'strategy' in canonical_skills entry: {entry}"
        assert entry["strategy"] in valid_strategies, (
            f"Invalid strategy {entry['strategy']!r} in {entry}"
        )


def test_profile_fallback_silent(client):
    """Minimal CV must return 200 even if canonical layer produces no matches."""
    minimal_cv = "Je suis ingénieur avec de l'expérience dans les projets complexes."
    resp = _post_txt(client, minimal_cv)
    assert resp.status_code == 200, (
        f"Canonical layer failure must not break request: status={resp.status_code}"
    )
    body = resp.json()
    # Canonical fields must be present even if empty
    assert "canonical_skills" in body
    assert "canonical_skills_count" in body
    assert "canonical_hierarchy_added" in body


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Invariants métier
# ═══════════════════════════════════════════════════════════════════════════════


def test_invariant_no_silent_drop():
    """len(mappings) must equal number of unique lowercase inputs — no silent drop."""
    store = _make_store()
    # 4 distinct (after lowercase dedup)
    labels = ["Machine Learning", "python", "lorem ipsum", "Data Analysis"]
    result = map_to_canonical(labels, store=store)
    assert len(result.mappings) == 4, (
        f"No input may be silently dropped: expected 4 mappings, got {len(result.mappings)}"
    )
    # Total accounting: matched + unresolved == total mappings
    assert result.matched_count + result.unresolved_count == len(result.mappings)


def test_invariant_strategies_are_exact_enum():
    """All strategies must be exactly one of the 3 defined values — no probabilistic variants."""
    store = _make_store()
    labels = ["machine learning", "python", "tensorflow", "unknown_xyz_999", "ml"]
    result = map_to_canonical(labels, store=store)
    valid = {"synonym_match", "tool_match", "unresolved"}
    for m in result.mappings:
        assert m.strategy in valid, (
            f"Strategy {m.strategy!r} is not in allowed set {valid}"
        )
        assert m.confidence in {1.0, 0.8, 0.0}, (
            f"Confidence {m.confidence} must be exactly 1.0, 0.8, or 0.0"
        )


def test_invariant_scoring_core_frozen():
    """matching_v1.py may only use the read-only weighted_store freeze exception."""
    matching_src = (API_SRC / "matching" / "matching_v1.py").read_text(encoding="utf-8")
    assert 'MATCHING_BOUNDARY_STATE = "STATE_B_EXPLICIT_WEIGHTED_STORE"' in matching_src, (
        "matching_v1.py must declare the explicit architecture boundary state"
    )
    assert "from compass.canonical.weighted_store import (" in matching_src, (
        "matching_v1.py freeze contract must explicitly document the weighted_store exception"
    )
    assert "canonical_mapper" not in matching_src
    assert "canonical_store" not in matching_src
    assert "hierarchy_expander" not in matching_src
    assert "master_store" not in matching_src


def test_invariant_extractors_no_skill_prefix():
    """extractors.py must not inject skill: prefix URIs from canonical into skills_uri."""
    extractors_src = (API_SRC / "matching" / "extractors.py").read_text(encoding="utf-8")
    # The canonical layer must never populate skills_uri with "skill:" prefixed IDs
    # Verify extractors doesn't import canonical mapper
    assert "canonical_mapper" not in extractors_src, (
        "extractors.py must not import canonical_mapper (canonical IDs must not enter skills_uri)"
    )
    assert "canonical_store" not in extractors_src
