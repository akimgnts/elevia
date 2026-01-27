#!/usr/bin/env python3
"""
backtest_esco.py - ESCO Silent Backtest Runner
Sprint 24 - Phase 2

Runs ESCO mapping on golden set profiles × offers and outputs coverage metrics.
"""

import argparse
import csv
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from esco.loader import get_esco_store
from esco.mapper import map_skills
from esco.metrics import esco_coverage


# Default paths relative to apps/api/
DEFAULT_PROFILES_DIR = Path(__file__).parent.parent / "fixtures" / "golden" / "profiles"
DEFAULT_OFFERS_FILE = Path(__file__).parent.parent / "fixtures" / "golden" / "offers" / "offers.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data"


def _utc_now() -> str:
    """Return ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def obs_log(
    event: str,
    *,
    run_id: str,
    profiles: int = 0,
    offers: int = 0,
    rows_written: int = 0,
    duration_ms: int = 0,
    status: str = "success",
    error_code: Optional[str] = None,
) -> None:
    """Emit structured JSON log to stdout."""
    log_entry = {
        "timestamp": _utc_now(),
        "event": event,
        "run_id": run_id,
        "profiles": profiles,
        "offers": offers,
        "rows_written": rows_written,
        "duration_ms": duration_ms,
        "status": status,
    }
    if error_code:
        log_entry["error_code"] = error_code
    print(json.dumps(log_entry), flush=True)


def load_profiles(profiles_dir: Path) -> List[Dict[str, Any]]:
    """Load all profile JSON files from directory."""
    profiles = []
    if not profiles_dir.exists():
        return profiles

    for json_file in sorted(profiles_dir.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            profile = json.load(f)
            # Ensure profile_id exists
            if "profile_id" not in profile:
                profile["profile_id"] = json_file.stem
            profiles.append(profile)

    return profiles


def load_offers(offers_file: Path) -> List[Dict[str, Any]]:
    """Load offers from JSON file."""
    if not offers_file.exists():
        return []

    with open(offers_file, "r", encoding="utf-8") as f:
        offers = json.load(f)

    # Handle both list and dict formats
    if isinstance(offers, dict) and "offers" in offers:
        offers = offers["offers"]

    return offers


def extract_profile_skills(profile: Dict[str, Any]) -> List[str]:
    """Extract raw skills from profile."""
    skills = []

    # Try different possible skill fields
    if "skills" in profile:
        skills.extend(profile["skills"])
    if "capabilities" in profile:
        for cap in profile.get("capabilities", []):
            if isinstance(cap, dict) and "name" in cap:
                skills.append(cap["name"])
            elif isinstance(cap, str):
                skills.append(cap)
    if "detected_tools" in profile:
        skills.extend(profile["detected_tools"])
    if "unmapped_skills" in profile:
        for us in profile.get("unmapped_skills", []):
            if isinstance(us, dict) and "raw_text" in us:
                skills.append(us["raw_text"])
            elif isinstance(us, str):
                skills.append(us)

    return list(set(skills))  # Deduplicate


def extract_offer_skills(offer: Dict[str, Any]) -> List[str]:
    """Extract raw skills from offer."""
    skills = []

    # Try different possible skill fields
    if "skills_required" in offer:
        skills.extend(offer["skills_required"])
    if "skills" in offer:
        skills.extend(offer["skills"])
    if "competences" in offer:
        for comp in offer.get("competences", []):
            if isinstance(comp, dict) and "label" in comp:
                skills.append(comp["label"])
            elif isinstance(comp, str):
                skills.append(comp)

    return list(set(skills))  # Deduplicate


def run_backtest(
    profiles_dir: Path,
    offers_file: Path,
    output_dir: Path,
    max_profiles: int = 5,
    max_offers: int = 20,
) -> Path:
    """
    Run ESCO backtest on profiles × offers.

    Returns path to output CSV.
    """
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Load data
    profiles = load_profiles(profiles_dir)[:max_profiles]
    offers = load_offers(offers_file)[:max_offers]

    if not profiles:
        obs_log(
            "esco_backtest_run",
            run_id=run_id,
            profiles=0,
            offers=len(offers),
            rows_written=0,
            duration_ms=0,
            status="error",
            error_code="NO_PROFILES",
        )
        raise ValueError(f"No profiles found in {profiles_dir}")

    if not offers:
        obs_log(
            "esco_backtest_run",
            run_id=run_id,
            profiles=len(profiles),
            offers=0,
            rows_written=0,
            duration_ms=0,
            status="error",
            error_code="NO_OFFERS",
        )
        raise ValueError(f"No offers found in {offers_file}")

    # Load ESCO store
    store = get_esco_store()

    # Prepare output
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = output_dir / f"esco_phase2_{timestamp}.csv"

    rows_written = 0

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "profile_id",
                "offer_id",
                "match_score_current",
                "esco_coverage",
                "esco_matched_count",
                "esco_offer_total",
                "missing_top5",
                "mapped_profile_count",
                "mapped_offer_count",
            ],
        )
        writer.writeheader()

        for profile in profiles:
            profile_id = profile.get("profile_id", "unknown")
            profile_skills = extract_profile_skills(profile)
            profile_mapping = map_skills(profile_skills, store=store)
            profile_esco_ids = {m["esco_id"] for m in profile_mapping["mapped"]}

            for offer in offers:
                offer_id = offer.get("id", "unknown")
                offer_skills = extract_offer_skills(offer)
                offer_mapping = map_skills(offer_skills, store=store)
                offer_esco_ids = {m["esco_id"] for m in offer_mapping["mapped"]}

                # Compute coverage
                coverage = esco_coverage(profile_esco_ids, offer_esco_ids)

                # Get top 5 missing (labels if possible)
                missing_ids = coverage["missing_ids"][:5]
                missing_labels = []
                for mid in missing_ids:
                    label = store.uri_to_preferred.get(mid, mid.split("/")[-1])
                    missing_labels.append(label)
                missing_top5 = "; ".join(missing_labels) if missing_labels else ""

                row = {
                    "profile_id": profile_id,
                    "offer_id": offer_id,
                    "match_score_current": "NA",  # Matcher not called in silent mode
                    "esco_coverage": round(coverage["coverage"], 4),
                    "esco_matched_count": coverage["matched"],
                    "esco_offer_total": coverage["offer_total"],
                    "missing_top5": missing_top5,
                    "mapped_profile_count": len(profile_mapping["mapped"]),
                    "mapped_offer_count": len(offer_mapping["mapped"]),
                }
                writer.writerow(row)
                rows_written += 1

    duration_ms = int((time.time() - start_time) * 1000)

    obs_log(
        "esco_backtest_run",
        run_id=run_id,
        profiles=len(profiles),
        offers=len(offers),
        rows_written=rows_written,
        duration_ms=duration_ms,
        status="success",
    )

    return output_file


def main():
    parser = argparse.ArgumentParser(description="ESCO Silent Backtest Runner")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=DEFAULT_PROFILES_DIR,
        help="Directory containing profile JSON files",
    )
    parser.add_argument(
        "--offers-file",
        type=Path,
        default=DEFAULT_OFFERS_FILE,
        help="JSON file containing offers",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for CSV",
    )
    parser.add_argument(
        "--max-profiles",
        type=int,
        default=5,
        help="Maximum number of profiles to process",
    )
    parser.add_argument(
        "--max-offers",
        type=int,
        default=20,
        help="Maximum number of offers to process",
    )

    args = parser.parse_args()

    try:
        output_file = run_backtest(
            profiles_dir=args.profiles_dir,
            offers_file=args.offers_file,
            output_dir=args.output_dir,
            max_profiles=args.max_profiles,
            max_offers=args.max_offers,
        )
        print(f"Output: {output_file}", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
