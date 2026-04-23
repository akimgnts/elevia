import importlib.util
import sys
from pathlib import Path


def _load_runner_module():
    module_path = Path(__file__).resolve().parents[3] / "scripts" / "run_cv_panel_backend.py"
    spec = importlib.util.spec_from_file_location("run_cv_panel_backend", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summarize_parse_and_build_inbox_payload_use_real_contract():
    runner = _load_runner_module()
    parse_json = {
        "canonical_skills": [{"label": "Data Analysis"}, {"label": "SQL"}],
        "validated_items": [{"label": "analyse de données"}, {"label": "sql"}],
        "skills_uri": ["uri:data-analysis", "uri:sql"],
        "profile": {
            "id": "profile-123",
            "skills": ["analyse de données", "sql"],
            "skills_uri": ["uri:data-analysis", "uri:sql"],
            "career_profile": {
                "experiences": [{"title": "Data Analyst"}],
                "selected_skills": [{"label": "Power BI"}],
            },
        },
    }

    summary = runner.summarize_parse(parse_json)
    payload = runner.build_inbox_payload(parse_json, default_profile_id="fallback-id")

    assert summary["canonical_skills_count"] == 2
    assert summary["validated_items_count"] == 2
    assert summary["skills_uri_count"] == 2
    assert summary["experiences_count"] == 1
    assert payload == {
        "profile_id": "profile-123",
        "profile": parse_json["profile"],
        "min_score": 0,
        "limit": 24,
        "explain": True,
    }


def test_extract_offer_metrics_reads_explain_items_and_counts():
    runner = _load_runner_module()
    inbox_items = [
        {
            "offer_id": "BF-1",
            "title": "Offer 1",
            "score": 51,
            "explain": {
                "matched_core": [{"label": "SQL"}],
                "missing_core": [{"label": "Python"}],
                "matched_full": [{"label": "SQL"}, {"label": "Excel"}],
                "missing_full": [{"label": "Python"}],
            },
        }
    ]

    offers = runner.extract_offer_metrics(inbox_items, top_k=3)

    assert len(offers) == 1
    offer = offers[0]
    assert offer.offer_id == "BF-1"
    assert offer.rank == 1
    assert offer.matched_core_count == 1
    assert offer.missing_core_count == 1
    assert offer.matched_full_count == 2
    assert offer.missing_full_count == 1
    assert offer.matched_core == ["SQL"]
    assert offer.missing_core == ["Python"]
