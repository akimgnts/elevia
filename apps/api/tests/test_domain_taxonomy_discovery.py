import json

from api.utils.domain_taxonomy_discovery import (
    classify_with_closed_taxonomy,
    consolidate_discovered_domains,
    filter_unprocessed_offers,
    load_checkpoint,
    normalize_discovery_item,
    run_classification_with_checkpoint,
    run_discovery_with_checkpoint,
    save_checkpoint,
    stratified_offer_sample,
)


def test_stratified_offer_sample_prefers_domain_coverage_before_overfilling():
    offers = [
        {"external_id": "1", "current_domain": "data", "country": "fr"},
        {"external_id": "2", "current_domain": "data", "country": "de"},
        {"external_id": "3", "current_domain": "finance", "country": "fr"},
        {"external_id": "4", "current_domain": "hr", "country": "es"},
        {"external_id": "5", "current_domain": "sales", "country": "us"},
    ]

    sample = stratified_offer_sample(offers, sample_size=4)
    ids = {item["external_id"] for item in sample}

    assert len(sample) == 4
    assert {"1", "3", "4", "5"} <= ids or {"2", "3", "4", "5"} <= ids


def test_normalize_discovery_item_enforces_required_shape():
    item = normalize_discovery_item(
        "BF-1",
        {
            "domain_proposed": "Digital Marketing",
            "subdomain": "SEO",
            "confidence": 0.82,
            "evidence": ["seo", "content"],
        },
    )

    assert item == {
        "offer_id": "BF-1",
        "domain_proposed": "digital marketing",
        "subdomain": "seo",
        "confidence": 0.82,
        "evidence": ["seo", "content"],
    }


def test_consolidate_discovered_domains_merges_synonyms_into_closed_list():
    discoveries = [
        {"offer_id": "1", "domain_proposed": "digital marketing", "subdomain": "seo", "confidence": 0.8, "evidence": ["seo"]},
        {"offer_id": "2", "domain_proposed": "marketing", "subdomain": "content", "confidence": 0.8, "evidence": ["content"]},
        {"offer_id": "3", "domain_proposed": "communication", "subdomain": "brand", "confidence": 0.8, "evidence": ["communication"]},
        {"offer_id": "4", "domain_proposed": "data science", "subdomain": "ml", "confidence": 0.8, "evidence": ["machine learning"]},
        {"offer_id": "5", "domain_proposed": "data analyst", "subdomain": "bi", "confidence": 0.8, "evidence": ["analytics"]},
    ]

    result = consolidate_discovered_domains(discoveries)

    assert "marketing_communication" in result["closed_domain_list_v1"]
    assert "data" in result["closed_domain_list_v1"]
    assert result["raw_to_closed"]["digital marketing"] == "marketing_communication"
    assert result["raw_to_closed"]["communication"] == "marketing_communication"
    assert result["raw_to_closed"]["data science"] == "data"
    assert result["raw_to_closed"]["data analyst"] == "data"


def test_classify_with_closed_taxonomy_flags_uncertain_items():
    closed_list = ["data", "finance", "marketing_communication"]

    good = classify_with_closed_taxonomy(
        {"offer_id": "1", "domain_proposed": "data science", "subdomain": "ml", "confidence": 0.84, "evidence": ["machine learning"]},
        raw_to_closed={"data science": "data"},
        closed_domain_list=closed_list,
    )
    weak = classify_with_closed_taxonomy(
        {"offer_id": "2", "domain_proposed": "innovation", "subdomain": "strategy", "confidence": 0.31, "evidence": ["innovation"]},
        raw_to_closed={},
        closed_domain_list=closed_list,
    )

    assert good["domain_tag"] == "data"
    assert good["needs_ai_review"] is False
    assert weak["domain_tag"] == "other"
    assert weak["needs_ai_review"] is True


def _stub_discover_factory():
    calls: list[list[str]] = []

    def discover(batch):
        ids = [str(item.get("external_id") or "") for item in batch]
        calls.append(list(ids))
        return [
            {
                "offer_id": ext,
                "domain_proposed": "marketing",
                "subdomain": "content",
                "confidence": 0.9,
                "evidence": ["content"],
            }
            for ext in ids
        ]

    return discover, calls


def _stub_classify_factory():
    calls: list[list[str]] = []

    def classify(batch, *, closed_domain_list):
        ids = [str(item.get("external_id") or "") for item in batch]
        calls.append(list(ids))
        return [
            {
                "offer_id": ext,
                "domain_tag": closed_domain_list[0] if closed_domain_list else "other",
                "confidence": 0.7,
                "evidence": ["x"],
                "needs_ai_review": False,
            }
            for ext in ids
        ]

    return classify, calls


def test_filter_unprocessed_offers_skips_known_ids():
    offers = [{"external_id": "a"}, {"external_id": "b"}, {"external_id": "c"}]
    remaining = filter_unprocessed_offers(offers, ["a", "c"])
    assert [item["external_id"] for item in remaining] == ["b"]


def test_run_discovery_with_checkpoint_creates_checkpoint_after_each_batch(tmp_path):
    offers = [{"external_id": str(i), "title": f"t{i}", "description": ""} for i in range(1, 6)]
    discover, calls = _stub_discover_factory()
    checkpoint = tmp_path / "discovery.json"
    progress_events: list[dict] = []

    results = run_discovery_with_checkpoint(
        offers,
        batch_size=2,
        checkpoint_path=checkpoint,
        resume=False,
        discover_fn=discover,
        progress_fn=progress_events.append,
    )

    assert checkpoint.exists()
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["processed_ids"] == ["1", "2", "3", "4", "5"]
    assert payload["batch_count"] == 3
    assert payload["phase"] == "discovery"
    assert len(payload["results"]) == 5
    assert [item["offer_id"] for item in results] == ["1", "2", "3", "4", "5"]
    assert calls == [["1", "2"], ["3", "4"], ["5"]]
    batch_events = [event for event in progress_events if event.get("event") == "batch"]
    assert [event["batch"] for event in batch_events] == [1, 2, 3]
    assert progress_events[-1]["event"] == "done"


def test_run_discovery_with_checkpoint_resume_skips_already_processed(tmp_path):
    offers = [{"external_id": str(i), "title": f"t{i}", "description": ""} for i in range(1, 6)]
    checkpoint = tmp_path / "discovery.json"

    save_checkpoint(
        checkpoint,
        processed_ids=["1", "2"],
        results=[
            {
                "offer_id": "1",
                "domain_proposed": "marketing",
                "subdomain": "content",
                "confidence": 0.9,
                "evidence": ["content"],
            },
            {
                "offer_id": "2",
                "domain_proposed": "marketing",
                "subdomain": "content",
                "confidence": 0.9,
                "evidence": ["content"],
            },
        ],
        batch_count=1,
        phase="discovery",
    )

    discover, calls = _stub_discover_factory()
    results = run_discovery_with_checkpoint(
        offers,
        batch_size=2,
        checkpoint_path=checkpoint,
        resume=True,
        discover_fn=discover,
    )

    assert calls == [["3", "4"], ["5"]]
    assert [item["offer_id"] for item in results] == ["1", "2", "3", "4", "5"]
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["processed_ids"] == ["1", "2", "3", "4", "5"]
    assert payload["batch_count"] == 3


def test_run_discovery_resumed_in_two_halves_matches_single_run(tmp_path):
    offers = [{"external_id": str(i), "title": f"t{i}", "description": ""} for i in range(1, 7)]

    discover_full, _ = _stub_discover_factory()
    full_checkpoint = tmp_path / "full.json"
    full_results = run_discovery_with_checkpoint(
        offers,
        batch_size=2,
        checkpoint_path=full_checkpoint,
        resume=False,
        discover_fn=discover_full,
    )

    discover_split, split_calls = _stub_discover_factory()
    split_checkpoint = tmp_path / "split.json"
    first_half_results = run_discovery_with_checkpoint(
        offers[:4],
        batch_size=2,
        checkpoint_path=split_checkpoint,
        resume=False,
        discover_fn=discover_split,
    )
    assert len(first_half_results) == 4

    resumed_results = run_discovery_with_checkpoint(
        offers,
        batch_size=2,
        checkpoint_path=split_checkpoint,
        resume=True,
        discover_fn=discover_split,
    )

    assert resumed_results == full_results
    full_payload = json.loads(full_checkpoint.read_text(encoding="utf-8"))
    split_payload = json.loads(split_checkpoint.read_text(encoding="utf-8"))
    assert full_payload["processed_ids"] == split_payload["processed_ids"]
    assert full_payload["results"] == split_payload["results"]
    assert split_calls == [["1", "2"], ["3", "4"], ["5", "6"]]


def test_run_classification_with_checkpoint_resume_skips_processed(tmp_path):
    offers = [{"external_id": str(i), "title": f"t{i}", "description": ""} for i in range(1, 5)]
    checkpoint = tmp_path / "classification.json"
    save_checkpoint(
        checkpoint,
        processed_ids=["1"],
        results=[
            {
                "offer_id": "1",
                "domain_tag": "data",
                "confidence": 0.7,
                "evidence": ["x"],
                "needs_ai_review": False,
            }
        ],
        batch_count=1,
        phase="classification",
    )

    classify, calls = _stub_classify_factory()
    results = run_classification_with_checkpoint(
        offers,
        closed_domain_list=["data", "other"],
        batch_size=2,
        checkpoint_path=checkpoint,
        resume=True,
        classify_fn=classify,
    )

    assert calls == [["2", "3"], ["4"]]
    assert [item["offer_id"] for item in results] == ["1", "2", "3", "4"]
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["processed_ids"] == ["1", "2", "3", "4"]


def test_load_checkpoint_returns_empty_when_missing(tmp_path):
    state = load_checkpoint(tmp_path / "missing.json")
    assert state == {"processed_ids": [], "results": [], "batch_count": 0}
