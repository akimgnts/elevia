import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path("scripts/audit_weighted_core_coverage.py").resolve()
    spec = importlib.util.spec_from_file_location("audit_weighted_core_coverage", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_is_excluded_candidate_label_filters_generic_terms():
    mod = _load_script_module()

    assert mod.is_excluded_candidate_label("anglais") is True
    assert mod.is_excluded_candidate_label("operations") is True
    assert mod.is_excluded_candidate_label("recrutement") is False


def test_extract_candidate_entries_keeps_secondary_non_core_and_excludes_generic():
    mod = _load_script_module()

    offer = {
        "id": "BF-1",
        "title": "Talent Acquisition Specialist",
        "offer_cluster": "ADMIN_HR",
        "skills_display": [
            {"uri": "uri:recrutement", "label": "recrutement"},
            {"uri": "uri:anglais", "label": "anglais"},
        ],
    }
    match_debug = {
        "skills": {
            "matched_secondary": ["recrutement", "anglais"],
            "matched_context": [],
        }
    }

    class _Resolved:
        def __init__(self, canonical_id, importance_level):
            self.canonical_id = canonical_id
            self.importance_level = importance_level

    def resolver(label, offer_cluster):
        if label == "recrutement":
            return _Resolved(None, None)
        return _Resolved("skill:english", "SECONDARY")

    candidates, excluded = mod.extract_candidate_entries(
        cv_file="CV - Nawel KADI 2026.pdf",
        domain_tag="hr",
        offer=offer,
        match_debug=match_debug,
        resolver=resolver,
    )

    assert candidates == [
        {
            "domain_tag": "hr",
            "label": "recrutement",
            "uri": "uri:recrutement",
            "bucket": "matched_secondary",
            "resolved": False,
            "canonical_id": None,
            "importance_level": None,
            "cv": "CV - Nawel KADI 2026.pdf",
            "offer_id": "BF-1",
            "offer_title": "Talent Acquisition Specialist",
        }
    ]
    assert excluded == [{"domain_tag": "hr", "label": "anglais", "bucket": "matched_secondary"}]


def test_aggregate_candidates_groups_by_domain_and_label():
    mod = _load_script_module()

    aggregated = mod.aggregate_candidates(
        [
            {
                "domain_tag": "hr",
                "label": "recrutement",
                "uri": "uri:recrutement",
                "bucket": "matched_secondary",
                "resolved": False,
                "canonical_id": None,
                "importance_level": None,
                "cv": "CV A",
                "offer_id": "BF-1",
                "offer_title": "Offer A",
            },
            {
                "domain_tag": "hr",
                "label": "recrutement",
                "uri": "uri:recrutement",
                "bucket": "matched_context",
                "resolved": False,
                "canonical_id": None,
                "importance_level": None,
                "cv": "CV B",
                "offer_id": "BF-2",
                "offer_title": "Offer B",
            },
        ]
    )

    assert list(aggregated) == ["hr"]
    assert aggregated["hr"][0]["label"] == "recrutement"
    assert aggregated["hr"][0]["frequency"] == 2
    assert aggregated["hr"][0]["bucket_counts"] == {"matched_context": 1, "matched_secondary": 1}
    assert aggregated["hr"][0]["examples"] == [
        {"cv": "CV A", "offer_id": "BF-1", "offer_title": "Offer A"},
        {"cv": "CV B", "offer_id": "BF-2", "offer_title": "Offer B"},
    ]


def test_build_json_report_has_expected_shape():
    mod = _load_script_module()

    report = mod.build_json_report(
        cv_count=5,
        offers_analyzed=12,
        domains={
            "hr": [
                {
                    "label": "recrutement",
                    "uri": "uri:recrutement",
                    "frequency": 2,
                    "resolved": False,
                    "canonical_id": None,
                    "importance_level": None,
                    "bucket_counts": {"matched_secondary": 2},
                    "examples": [{"cv": "CV A", "offer_id": "BF-1", "offer_title": "Offer A"}],
                }
            ]
        },
        excluded_notes=["anglais"],
    )

    assert report["summary"] == {
        "cv_count": 5,
        "offers_analyzed": 12,
        "candidate_count": 1,
    }
    assert report["domains"]["hr"][0]["label"] == "recrutement"
    assert report["excluded_notes"] == ["anglais"]
