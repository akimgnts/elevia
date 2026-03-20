from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.object_normalizer import normalize_object_phrase


def test_object_normalizer_trims_long_narrative_tail():
    normalized = normalize_object_phrase(
        "priorites livraison securiser departs tenir",
        action="management",
        domain="supply_chain",
    )
    assert normalized == "priorites livraison"


def test_object_normalizer_removes_tool_tail_from_data_like_object():
    normalized = normalize_object_phrase(
        "donnees erp mise forme power",
        action="extraction",
        domain="data",
        tools=["ERP Usage", "Power BI"],
    )
    assert normalized == "donnees erp"
