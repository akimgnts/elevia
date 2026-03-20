from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.generic_skill_filter import filter_generic_mapping_inputs, filter_generic_structured_units


def test_generic_filter_removes_standalone_generic_skills_without_context():
    kept, removed = filter_generic_mapping_inputs(
        ["communication", "sql", "gestion de projet"],
        structured_units=[],
    )
    assert "sql" in kept
    assert "communication" not in kept
    assert removed


def test_generic_filter_keeps_contextual_unit_with_object():
    units, removed = filter_generic_structured_units(
        [
            {"raw_text": "communication interne", "object": "communication interne", "domain": "marketing"},
            {"raw_text": "communication", "object": "communication", "domain": ""},
        ]
    )
    assert len(units) == 1
    assert units[0]["raw_text"] == "communication interne"
    assert removed
