from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.extraction.semantic_guards import apply_semantic_guards


def test_semantic_guard_drops_ai_without_ml_context():
    result = apply_semantic_guards(
        cv_text="J ai travaille sur l integration et le suivi RH",
        mapping_inputs=["ai", "Excel", "administration du personnel"],
        preserved_labels=["Excel", "HR Administration"],
    )

    assert result.mapping_inputs == ["Excel", "administration du personnel"]
    assert result.dropped[0]["drop_reason"] == "dropped:semantic_guard:machine learning"


def test_semantic_guard_keeps_ml_when_context_is_explicit():
    result = apply_semantic_guards(
        cv_text="Python machine learning dataset training",
        mapping_inputs=["machine learning", "Python"],
        preserved_labels=["Python", "Machine Learning"],
    )

    assert result.mapping_inputs == ["machine learning", "Python"]
    assert result.dropped == []


def test_semantic_guard_drops_data_abstraction_on_logistics_profile_without_data_context():
    result = apply_semantic_guards(
        cv_text="Supply chain approvisionnement fournisseurs stocks livraisons sap",
        mapping_inputs=["Data Analysis", "ERP Usage", "SAP"],
        preserved_labels=["Data Analysis", "Supply Chain Management", "Procurement", "SAP"],
        preserved_items=[
            {"label": "Data Analysis", "candidate_type": "domain"},
            {"label": "Supply Chain Management", "candidate_type": "domain"},
            {"label": "SAP", "candidate_type": "platform"},
        ],
    )

    assert [item["label"] for item in result.preserved_items] == ["Supply Chain Management", "SAP"]
    assert any(item["drop_reason"] == "dropped:semantic_guard:logistics_without_data_context" for item in result.dropped)
