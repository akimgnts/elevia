"""
Smoke runtime matching with the same catalog loader as /inbox.

Usage:
  ELEVIA_INBOX_USE_VIE_FIXTURES=1 ELEVIA_DEBUG_MATCHING=1 \
    python3 scripts/smoke_runtime_matching.py
"""

import logging
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.inbox_catalog import load_catalog_offers
from matching.extractors import extract_profile
from matching.matching_v1 import MatchingEngine

PROFILE_PATH = API_ROOT / "fixtures" / "profiles" / "akim_guentas_matching.json"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not PROFILE_PATH.exists():
        print(f"Missing profile fixture: {PROFILE_PATH}")
        return 1

    profile = PROFILE_PATH.read_text(encoding="utf-8")
    profile_data = __import__("json").loads(profile)

    offers = load_catalog_offers()
    if not offers:
        print("No offers loaded from catalog.")
        return 1

    extracted = extract_profile(profile_data)
    if extracted.matching_skills_count <= 3 and extracted.capabilities_count == 3:
        print("WARNING: profil réduit (matching_skills <= 3, capabilities=3)")
    engine = MatchingEngine(offers)

    sample = [offer for offer in offers if offer.get("is_vie") is True][:5]
    if len(sample) < 5:
        sample = offers[:5]

    print(f"Loaded offers: {len(offers)} | Sampled: {len(sample)}")
    print("Debug breakdown (5 offers):")

    for offer in sample:
        engine.score_offer(extracted, offer)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
