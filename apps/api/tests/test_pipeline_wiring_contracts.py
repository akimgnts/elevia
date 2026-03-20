from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parent.parent / "src"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_parse_file_uses_baseline_parser_and_compass_enricher():
    source = _read(ROOT / "api/routes/profile_file.py")
    assert "build_parse_file_response_payload" in source, (
        "parse-file must delegate orchestration to the modular parsing pipeline"
    )
    pipeline = _read(ROOT / "compass/pipeline/profile_parse_pipeline.py")
    assert "run_cv_pipeline" in pipeline, "pipeline must use compass.canonical_pipeline.run_cv_pipeline"
    assert "run_enrichment_stage" in pipeline, "pipeline must use explicit enrichment stage"
    assert "run_canonical_mapping_stage" in pipeline, "pipeline must use explicit canonical mapping stage"


def test_parse_baseline_uses_baseline_parser_and_compass_enricher():
    source = _read(ROOT / "api/routes/profile_baseline.py")
    assert "build_parse_baseline_response_payload" in source, (
        "parse-baseline must delegate orchestration to the modular parsing pipeline"
    )
    pipeline = _read(ROOT / "compass/pipeline/profile_parse_pipeline.py")
    assert "build_parse_baseline_response_payload" in pipeline


def test_inbox_uses_catalog_and_matching_engine():
    source = _read(ROOT / "api/routes/inbox.py")
    assert "load_catalog_offers" in source, "inbox must load offers via inbox_catalog"
    assert "MatchingEngine" in source, "inbox must use matching_v1.MatchingEngine"
    assert "extract_profile" in source, "inbox must use matching.extractors.extract_profile"


def test_matching_route_uses_matching_engine():
    source = _read(ROOT / "api/routes/matching.py")
    assert "MatchingEngine" in source, "/v1/match must use MatchingEngine"
    assert "extract_profile" in source, "/v1/match must use extract_profile"


def test_offer_catalog_uses_compass_structurers():
    source = _read(ROOT / "api/routes/offers.py")
    assert "structure_offer_text_v1" in source, "offers/catalog must use Compass text structurer"
    assert "build_explain_payload_v1" in source, "offers/catalog must build Compass explain payload"


def test_inbox_catalog_injects_domain_uris():
    source = _read(ROOT / "api/utils/inbox_catalog.py")
    assert "normalize_offers_to_uris" in source, "inbox_catalog must use canonical offer normalization"
    canon = _read(ROOT / "compass/offer_canonicalization.py")
    assert "build_domain_uris_for_text" in canon, "canonical offer normalization must build DOMAIN URIs"
