#!/usr/bin/env python3
"""Comprehensive validation of French explanation layer integration."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "apps/api/src"))

from api.routes.inbox import get_inbox
from api.schemas.inbox import InboxRequest


GOLDEN_PROFILES = [
    "profile_02_developer",
    "profile_01_data_analyst",
    "profile_04_finance",
    "profile_05_commercial",
    "akim_guentas",
]

SCORE_RANGES = {
    80: "Excellent match",
    60: "Bon match",
    40: "Match moyen",
    20: "Match faible",
    0: "Peu pertinent",
}

def load_profile(name: str) -> dict:
    """Load profile fixture."""
    fixtures = Path(__file__).parent.parent / "apps/api/fixtures/profiles"
    path = fixtures / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profile {name} not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_score_label(score: int, label: str) -> bool:
    """Check fit_label matches score range."""
    if score >= 80:
        return label == "Excellent match"
    elif score >= 60:
        return label == "Bon match"
    elif score >= 40:
        return label == "Match moyen"
    elif score >= 20:
        return label == "Match faible"
    else:
        return label == "Peu pertinent"


def validate_explanation(item, profile_name: str) -> dict:
    """Validate single explanation item."""
    result = {
        "title": item.title,
        "score": item.score,
        "checks": {},
        "errors": [],
        "example": None,
    }

    if not item.explanation:
        result["errors"].append("No explanation field")
        return result

    exp = item.explanation

    # Check fit_label
    if validate_score_label(item.score, exp.fit_label):
        result["checks"]["fit_label_correct"] = True
    else:
        result["checks"]["fit_label_correct"] = False
        result["errors"].append(
            f"fit_label '{exp.fit_label}' doesn't match score {item.score}"
        )

    # Check summary_reason is French and non-empty
    if exp.summary_reason:
        has_french = any(
            w in exp.summary_reason.lower()
            for w in ["vous", "avez", "compétences", "sur", "match"]
        )
        result["checks"]["summary_is_french"] = has_french
        if not has_french:
            result["errors"].append("summary_reason doesn't look French")
    else:
        result["errors"].append("summary_reason is empty")

    # Check strengths
    if item.matched_skills and not exp.strengths:
        result["errors"].append(f"Has {len(item.matched_skills)} matched skills but no strengths")
    result["checks"]["strengths_populated"] = len(exp.strengths) > 0
    result["checks"]["strengths_count"] = len(exp.strengths)

    # Check gaps
    if item.missing_skills and not exp.gaps:
        result["errors"].append(f"Has {len(item.missing_skills)} missing skills but no gaps")
    result["checks"]["gaps_populated"] = len(exp.gaps) > 0
    result["checks"]["gaps_count"] = len(exp.gaps)

    # Check next_actions
    result["checks"]["next_actions_populated"] = len(exp.next_actions) > 0
    result["checks"]["next_actions_count"] = len(exp.next_actions)

    # Verify technical explain is preserved
    if not item.explain:
        result["errors"].append("Technical explain block is missing!")
    else:
        result["checks"]["explain_preserved"] = True
        result["checks"]["explain_matched"] = len(item.explain.matched_core)
        result["checks"]["explain_missing"] = len(item.explain.missing_core)

    # No empty/useless fields
    if exp.blockers is None:
        result["errors"].append("blockers field is None (should be list)")
    if not isinstance(exp.strengths, list):
        result["errors"].append("strengths is not a list")
    if not isinstance(exp.gaps, list):
        result["errors"].append("gaps is not a list")
    if not isinstance(exp.next_actions, list):
        result["errors"].append("next_actions is not a list")

    result["checks"]["valid_types"] = len(result["errors"]) == 0

    # Store example for display
    result["example"] = {
        "fit_label": exp.fit_label,
        "summary_reason": exp.summary_reason[:80] + "..." if len(exp.summary_reason) > 80 else exp.summary_reason,
        "strengths": exp.strengths[:2],
        "gaps": exp.gaps[:2],
        "next_actions": exp.next_actions[:1],
    }

    return result


def test_profile(profile_name: str) -> dict:
    """Test single profile."""
    print(f"\n{'='*80}")
    print(f"Profile: {profile_name}")
    print(f"{'='*80}")

    try:
        profile = load_profile(profile_name)
        profile_id = profile.get("id") or profile.get("profile_id") or profile_name

        # Call inbox with explain=true
        req = InboxRequest(
            profile_id=profile_id,
            profile=profile,
            min_score=10,
            limit=3,
            explain=True,
        )

        response = get_inbox(req)
        print(f"Items returned: {len(response.items)}")

        if not response.items:
            return {
                "profile": profile_name,
                "status": "FAIL",
                "reason": "No items returned",
                "items": [],
            }

        # Validate top 3 items
        validated = []
        for i, item in enumerate(response.items[:3]):
            val = validate_explanation(item, profile_name)
            validated.append(val)
            print(f"\n[{i+1}] {val['title']} (score={val['score']})")
            if val["errors"]:
                print(f"    ERRORS: {val['errors']}")
            else:
                print(f"    ✓ All checks passed")
            if val["example"]:
                ex = val["example"]
                print(f"    Fit: {ex['fit_label']}")
                print(f"    Summary: {ex['summary_reason']}")
                if ex["strengths"]:
                    print(f"    Strengths: {', '.join(ex['strengths'][:2])}")
                if ex["gaps"]:
                    print(f"    Gaps: {', '.join(ex['gaps'][:2])}")

        # Overall status
        all_passed = all(len(v["errors"]) == 0 for v in validated)
        status = "PASS" if all_passed else "FAIL"

        error_count = sum(len(v["errors"]) for v in validated)
        error_details = []
        for v in validated:
            if v["errors"]:
                error_details.append(f"{v['title']}: {v['errors']}")

        return {
            "profile": profile_name,
            "status": status,
            "items": validated,
            "error_count": error_count,
            "error_details": error_details,
        }

    except Exception as e:
        import traceback
        print(f"EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()
        return {
            "profile": profile_name,
            "status": "ERROR",
            "reason": str(e),
            "items": [],
        }


def main():
    """Run validation on all profiles."""
    print("\n" + "="*80)
    print("FRENCH EXPLANATION LAYER VALIDATION")
    print("="*80)
    print(f"Testing {len(GOLDEN_PROFILES)} golden profiles")

    results = []
    for profile_name in GOLDEN_PROFILES:
        result = test_profile(profile_name)
        results.append(result)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    pass_count = sum(1 for r in results if r["status"] == "PASS")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    error_count = sum(1 for r in results if r["status"] == "ERROR")

    for result in results:
        status = result["status"]
        profile = result["profile"]
        if result["status"] == "PASS":
            print(f"✓ {status:6} | {profile:30}")
        elif result["status"] == "FAIL":
            item_errors = result.get("error_count", 0)
            print(f"✗ {status:6} | {profile:30} | {item_errors} errors")
            for err in result.get("error_details", [])[:2]:
                print(f"         {err}")
        else:
            print(f"✗ {status:6} | {profile:30} | {result.get('reason', '?')}")

    print(f"\n{'='*80}")
    print(f"Results: {pass_count} PASS, {fail_count} FAIL, {error_count} ERROR")
    print(f"{'='*80}")

    # Show example from first passing profile
    for result in results:
        if result["status"] == "PASS" and result["items"]:
            first_item = result["items"][0]
            print(f"\nExample (from {result['profile']}):")
            print(f"  Title: {first_item['title']}")
            print(f"  Score: {first_item['score']}")
            if first_item["example"]:
                ex = first_item["example"]
                print(f"  Fit label: {ex['fit_label']}")
                print(f"  Summary: {ex['summary_reason']}")
                print(f"  Strengths: {ex['strengths']}")
                print(f"  Gaps: {ex['gaps']}")
                print(f"  Next action: {ex['next_actions']}")
            break

    return 0 if (fail_count == 0 and error_count == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
