from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.extraction.enriched_concept_builder import build_enriched_concepts


def test_noise_removal_keeps_only_valid_concepts():
    result = build_enriched_concepts(["pas", "cv", "gestion portefeuille", "reporting"])
    concepts = result["concept_signals"]

    assert len(concepts) == 2
    assert all(concept["concept"] not in {"pas", "cv"} for concept in concepts)


def test_deduplication_clusters_reporting_variants():
    result = build_enriched_concepts(["reporting", "reporting mensuel", "weekly reporting"])
    concepts = result["concept_signals"]

    assert len(concepts) == 1
    assert concepts[0]["normalized"] == "reporting"
    assert len(concepts[0]["variants"]) == 3


def test_concept_normalization_unifies_portfolio_management():
    result = build_enriched_concepts(["gestion portefeuille", "portfolio management"])
    concepts = result["concept_signals"]

    assert len(concepts) == 1
    assert concepts[0]["normalized"] == "portfolio management"


def test_domain_detection_maps_supply_chain_concepts():
    result = build_enriched_concepts(["coordination transport", "gestion stocks"])
    concepts = result["concept_signals"]

    assert len(concepts) == 2
    assert all(concept["domain"] == "supply_chain_ops" for concept in concepts)


def test_concept_output_is_structured_and_weighted():
    result = build_enriched_concepts([
        {"normalized": "reporting mensuel", "domain": "finance"},
        {"normalized": "weekly reporting", "domain": "finance"},
    ])
    concept = result["concept_signals"][0]

    assert concept["concept"] == "reporting"
    assert concept["tokens"] == ["reporting"]
    assert concept["weight"] > 0.0
