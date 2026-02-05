"""
Validate VIE fixture catalog score distribution.

Usage:
  python3 scripts/test_vie_fixture_catalog.py
"""

import json
import statistics
import sys
from pathlib import Path

API_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

from matching.matching_v1 import MatchingEngine
from matching.extractors import extract_profile

PROFILE_PATH = API_ROOT / "fixtures" / "profiles" / "akim_guentas_matching.json"
FIXTURES_PATH = API_ROOT / "fixtures" / "offers" / "vie_catalog.json"


def main() -> int:
    if not PROFILE_PATH.exists():
        print(f"Missing profile fixture: {PROFILE_PATH}")
        return 1
    if not FIXTURES_PATH.exists():
        print(f"Missing VIE fixtures: {FIXTURES_PATH}")
        return 1

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    offers = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

    if not isinstance(offers, list) or not offers:
        print("No offers found in VIE fixtures.")
        return 1

    extracted = extract_profile(profile)
    engine = MatchingEngine(offers)

    scores = [engine.score_offer(extracted, offer).score for offer in offers]
    scores_sorted = sorted(scores)
    min_score = scores_sorted[0]
    max_score = scores_sorted[-1]
    median_score = statistics.median(scores_sorted)

    print(f"Offers: {len(scores)}")
    print(f"Scores (min/median/max): {min_score} / {median_score} / {max_score}")

    ok = True
    if min_score >= 40:
        print("FAIL: min score should be < 40")
        ok = False
    if not (50 <= median_score <= 70):
        print("FAIL: median score should be ~50-70")
        ok = False
    if max_score <= 80:
        print("FAIL: max score should be > 80")
        ok = False

    if ok:
        print("OK: score distribution looks healthy")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
