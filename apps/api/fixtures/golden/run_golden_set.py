#!/usr/bin/env python3
"""
run_golden_set.py - Golden Set Validation Script
Sprint 21 - Regression detection via golden set matching

Runs 5 profiles against 20 offers and validates:
- Top 5 results are non-empty
- Scores are descending
- Reasons are present
- No errors occur

Usage:
    python run_golden_set.py [--api-url URL]

Exit codes:
    0 - All assertions passed
    1 - Assertions failed (anomalies detected)
    2 - Script error (API unreachable, etc.)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    print("ERROR: requests library required. Install via: pip install requests")
    sys.exit(2)


# Paths
FIXTURES_DIR = Path(__file__).parent
PROFILES_DIR = FIXTURES_DIR / "profiles"
OFFERS_FILE = FIXTURES_DIR / "offers" / "offers.json"


def load_profiles() -> List[Dict[str, Any]]:
    """Load all profile fixtures."""
    profiles = []
    for profile_file in sorted(PROFILES_DIR.glob("*.json")):
        with open(profile_file) as f:
            profiles.append(json.load(f))
    return profiles


def load_offers() -> List[Dict[str, Any]]:
    """Load offer fixtures."""
    with open(OFFERS_FILE) as f:
        return json.load(f)


def run_match(api_url: str, profile: Dict[str, Any], offers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run a match request against the API."""
    response = requests.post(
        f"{api_url}/v1/match",
        json={"profile": profile, "offers": offers},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def validate_result(profile_id: str, result: Dict[str, Any]) -> List[str]:
    """
    Validate a match result.

    Returns list of anomalies (empty = OK).
    """
    anomalies = []

    # Check results exist
    results = result.get("results", [])
    if not results:
        anomalies.append(f"{profile_id}: No results returned")
        return anomalies

    # Check top 5 have scores
    top5 = results[:5]
    for i, r in enumerate(top5):
        score = r.get("score")
        if score is None:
            anomalies.append(f"{profile_id}: Result {i+1} has no score")

        reasons = r.get("reasons", [])
        if not reasons:
            anomalies.append(f"{profile_id}: Result {i+1} has no reasons")

    # Check scores are descending
    scores = [r.get("score", 0) for r in results]
    for i in range(1, len(scores)):
        if scores[i] > scores[i-1]:
            anomalies.append(f"{profile_id}: Scores not descending at position {i}")
            break

    # Check no error in response
    if "error" in result:
        anomalies.append(f"{profile_id}: Error in response: {result['error']}")

    return anomalies


def main():
    parser = argparse.ArgumentParser(description="Run golden set validation")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    print(f"Golden Set Validation - Sprint 21")
    print(f"API: {args.api_url}")
    print("-" * 50)

    try:
        profiles = load_profiles()
        offers = load_offers()
        print(f"Loaded {len(profiles)} profiles, {len(offers)} offers")
    except Exception as e:
        print(f"ERROR: Failed to load fixtures: {e}")
        sys.exit(2)

    all_anomalies = []
    results_summary = []

    for profile in profiles:
        profile_id = profile.get("profile_id", "unknown")
        print(f"\nTesting profile: {profile_id}")

        try:
            result = run_match(args.api_url, profile, offers)
            anomalies = validate_result(profile_id, result)

            top5_scores = [r.get("score", 0) for r in result.get("results", [])[:5]]
            results_summary.append({
                "profile_id": profile_id,
                "total_results": len(result.get("results", [])),
                "top5_scores": top5_scores,
                "anomalies": anomalies,
            })

            if anomalies:
                print(f"  WARN: {len(anomalies)} anomalies")
                for a in anomalies:
                    print(f"    - {a}")
                all_anomalies.extend(anomalies)
            else:
                print(f"  OK: {len(result.get('results', []))} results, top score: {top5_scores[0] if top5_scores else 'N/A'}")

        except requests.RequestException as e:
            anomaly = f"{profile_id}: API request failed: {e}"
            print(f"  ERROR: {anomaly}")
            all_anomalies.append(anomaly)
            results_summary.append({
                "profile_id": profile_id,
                "error": str(e),
            })

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    for summary in results_summary:
        pid = summary.get("profile_id")
        if "error" in summary:
            print(f"  {pid}: ERROR - {summary['error']}")
        else:
            scores = summary.get("top5_scores", [])
            score_str = ", ".join(str(s) for s in scores) if scores else "N/A"
            status = "WARN" if summary.get("anomalies") else "OK"
            print(f"  {pid}: {status} - Top 5 scores: [{score_str}]")

    print()
    if all_anomalies:
        print(f"RESULT: FAIL - {len(all_anomalies)} anomalies detected")
        sys.exit(1)
    else:
        print("RESULT: PASS - All assertions passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
