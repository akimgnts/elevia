#!/usr/bin/env python3
"""Validate French explanations in /inbox endpoint with 5 golden profiles."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps/api/src"))

from api.routes.inbox import get_inbox
from api.schemas.inbox import InboxRequest


def load_profile(name: str) -> dict:
    """Load profile fixture by name."""
    fixtures_dir = Path(__file__).parent.parent / "apps/api/fixtures/profiles"
    profile_path = fixtures_dir / f"{name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def test_profile(profile_name: str) -> dict:
    """Test /inbox with a profile, checking for French explanations."""
    print(f"\n{'='*70}")
    print(f"Testing: {profile_name}")
    print(f"{'='*70}")

    profile = load_profile(profile_name)
    profile_id = profile.get("id") or profile.get("profile_id") or profile_name

    # Call /inbox with explain=True
    req = InboxRequest(
        profile_id=profile_id,
        profile=profile,
        min_score=10,
        limit=5,  # Only get top 5 for quick validation
        explain=True,
    )

    try:
        response = get_inbox(req)
        print(f"Profile: {profile_id}")
        print(f"Items returned: {len(response.items)}")

        if not response.items:
            print("WARNING: No items returned!")
            return {"profile": profile_name, "status": "NO_ITEMS", "count": 0}

        # Check first item for explanation
        item = response.items[0]
        print(f"\nFirst item: {item.title}")
        print(f"Score: {item.score}")

        if not item.explanation:
            print("WARNING: No explanation field!")
            return {"profile": profile_name, "status": "NO_EXPLANATION", "count": len(response.items)}

        exp = item.explanation
        print(f"\nExplanation (French):")
        print(f"  Fit label: {exp.fit_label}")
        print(f"  Summary: {exp.summary_reason[:100]}...")
        print(f"  Strengths ({len(exp.strengths)}): {exp.strengths[:2]}")
        print(f"  Gaps ({len(exp.gaps)}): {exp.gaps[:2]}")
        print(f"  Blockers ({len(exp.blockers)}): {exp.blockers[:1]}")
        print(f"  Next actions ({len(exp.next_actions)}): {exp.next_actions[:1]}")

        # Verify French text (sample checks)
        french_indicators = [
            ("Excellent match", exp.fit_label),
            ("Bon match", exp.fit_label),
            ("Match moyen", exp.fit_label),
            ("Match faible", exp.fit_label),
            ("Peu pertinent", exp.fit_label),
            ("compétences", exp.summary_reason.lower()),
            ("sur", exp.summary_reason.lower()),
        ]

        has_french = any(
            indicator in value.lower()
            for indicator, value in french_indicators
            if value
        )

        if not has_french:
            print("\nWARNING: No French text detected!")
            return {"profile": profile_name, "status": "NO_FRENCH", "count": len(response.items)}

        print("\n✓ French explanation detected!")

        # Verify field structure
        if not all([exp.fit_label, exp.summary_reason]):
            print("WARNING: Missing required fields!")
            return {"profile": profile_name, "status": "MISSING_FIELDS", "count": len(response.items)}

        return {"profile": profile_name, "status": "OK", "count": len(response.items), "fit_label": exp.fit_label}

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return {"profile": profile_name, "status": "ERROR", "error": str(e)}


if __name__ == "__main__":
    # Test 5 golden profiles
    profiles = [
        "profile_02_developer",
        "profile_01_data_analyst",
        "profile_04_finance",
        "profile_05_commercial",
        "akim_guentas",
    ]

    results = []
    for profile_name in profiles:
        try:
            result = test_profile(profile_name)
            results.append(result)
        except Exception as e:
            results.append({"profile": profile_name, "status": "ERROR", "error": str(e)})

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for r in results:
        status = r.get("status", "?")
        profile = r.get("profile", "?")
        count = r.get("count", 0)
        fit = r.get("fit_label", "")
        print(f"{status:15} | {profile:30} | {count:3} items | {fit}")

    # Overall result
    ok_count = sum(1 for r in results if r.get("status") == "OK")
    print(f"\nPassed: {ok_count}/{len(results)}")

    sys.exit(0 if ok_count == len(results) else 1)
