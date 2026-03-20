from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parent.parent / "src" / "compass" / "pipeline"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_orchestrator_delegates_response_and_dev_builders():
    source = _read("profile_parse_pipeline.py")
    assert "build_parse_file_response_payload_from_artifacts" in source
    assert "build_analyze_dev_payload" in source
    assert "run_profile_cache_hooks" in source
    assert "store_profile_summary" not in source
    assert "build_profile_summary" not in source
    assert "analyze_dev =" not in source
    assert "response_payload: Dict" not in source


def test_extracted_modules_own_their_responsibilities():
    response_builder = _read("response_builder.py")
    dev_builder = _read("dev_payload_builder.py")
    cache_hooks = _read("cache_hooks.py")

    assert "canonical_skills_count" in response_builder
    assert "matching_input_trace" in response_builder
    assert "signal_loss_audit" in dev_builder
    assert "tight_split_trace" in dev_builder
    assert "store_profile_summary" in cache_hooks
    assert "cache_profile_text" in cache_hooks
