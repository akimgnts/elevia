from __future__ import annotations

import json
from pathlib import Path

from api.utils.inbox_catalog import load_catalog_offers
from compass.offer.offer_intelligence import build_offer_intelligence, offer_intelligence_to_csv_rows

_ROOT = Path(__file__).resolve().parents[2]
_OUT_JSON = _ROOT / "data" / "eval" / "offer_intelligence_eval_results.json"
_OUT_CSV = _ROOT / "data" / "eval" / "offer_intelligence_eval_results.csv"

_VALIDATION_CASES = [
    {"offer_id": "BF-AZ-SAMPLE-0001", "expected_role_block": "data_analytics", "label": "data / bi"},
    {"offer_id": "BF-AZ-0001", "expected_role_block": "finance_ops", "label": "finance / controlling"},
    {"offer_id": "BF-AZ-0004", "expected_role_block": "sales_business_dev", "label": "sales / business development"},
    {"offer_id": "BF-AZ-0005", "expected_role_block": "supply_chain_ops", "label": "supply chain / logistics"},
    {"offer_id": "BF-AZ-0010", "expected_role_block": "hr_ops", "label": "hr"},
    {"offer_id": "BF-AZ-0012", "expected_role_block": "marketing_communication", "label": "communication"},
    {"offer_id": "BF-AZ-0016", "expected_role_block": "marketing_communication", "label": "marketing"},
    {"offer_id": "BF-AZ-0008", "expected_role_block": "legal_compliance", "label": "legal / compliance"},
]


def main() -> None:
    offers = load_catalog_offers()
    by_id = {str(offer.get("id") or ""): offer for offer in offers}

    review_rows = []
    correct = 0
    for case in _VALIDATION_CASES:
        offer = by_id.get(case["offer_id"])
        if not offer:
            continue
        intelligence = build_offer_intelligence(offer=offer)
        predicted = intelligence.get("dominant_role_block")
        if predicted == case["expected_role_block"]:
            correct += 1
        review_rows.append(
            {
                "offer_id": case["offer_id"],
                "label": case["label"],
                "title": offer.get("title"),
                "expected_role_block": case["expected_role_block"],
                "predicted_role_block": predicted,
                "dominant_domains": intelligence.get("dominant_domains") or [],
                "top_offer_signals": intelligence.get("top_offer_signals") or [],
                "required_skills": intelligence.get("required_skills") or [],
                "optional_skills": intelligence.get("optional_skills") or [],
                "offer_summary": intelligence.get("offer_summary"),
            }
        )

    results = {
        "catalog_offer_count": len(offers),
        "validation_case_count": len(review_rows),
        "strict_accuracy": round((correct / len(review_rows)), 4) if review_rows else 0.0,
        "cases": review_rows,
    }

    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    _OUT_CSV.write_text(offer_intelligence_to_csv_rows(review_rows), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
