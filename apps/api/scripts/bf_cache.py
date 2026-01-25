#!/usr/bin/env python3
"""
bf_cache.py - Business France Cache Utilities
Sprint 20.1 - BF Fallback Survival Patch

Provides hardened cache operations:
- Anti-poisoning: validate before write
- Atomic writes: tmp + fsync + replace
- Safe reads: skip invalid lines
- Staleness tracking: mtime-based age

Usage:
    from bf_cache import (
        validate_offers_minimal,
        atomic_write_jsonl,
        read_jsonl_best_effort,
        cache_age_hours,
    )
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Optional


# Staleness thresholds (hours)
CACHE_WARNING_HOURS = 24
CACHE_CRITICAL_HOURS = 72


def validate_offers_minimal(offers: list) -> bool:
    """
    Validate offers list meets minimal requirements.

    Requirements:
    - Must be a non-empty list
    - Each offer must be a dict
    - Each offer must have a non-empty "id" field

    Args:
        offers: List of offer dicts to validate

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(offers, list):
        return False

    if len(offers) == 0:
        return False

    for offer in offers:
        if not isinstance(offer, dict):
            return False

        offer_id = offer.get("id")
        if not offer_id:
            # Check alternate id fields (BF uses different formats)
            offer_id = offer.get("offer_id") or offer.get("reference")
            if not offer_id:
                return False

    return True


def atomic_write_jsonl(path: Path, records: list, run_id: str, fetched_at: str) -> bool:
    """
    Atomically write records to JSONL file.

    Process:
    1. Write to temp file in same directory
    2. fsync to ensure data on disk
    3. Atomic rename (os.replace)

    If any step fails, the original file is untouched.

    Args:
        path: Target JSONL file path
        records: List of offer payloads to write
        run_id: Run identifier for metadata
        fetched_at: ISO timestamp for metadata

    Returns:
        True if write succeeded, False otherwise
    """
    if not records:
        return False

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (required for atomic rename)
    fd = None
    tmp_path = None

    try:
        fd, tmp_path = tempfile.mkstemp(
            suffix=".jsonl.tmp",
            dir=str(path.parent),
            prefix=".bf_cache_"
        )

        # Write all records
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None  # fd is now owned by the file object
            for offer in records:
                record = {
                    "run_id": run_id,
                    "fetched_at": fetched_at,
                    "payload": offer,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # Flush Python buffers
            f.flush()
            # Sync to disk
            os.fsync(f.fileno())

        # Atomic replace
        os.replace(tmp_path, path)
        return True

    except Exception:
        # Clean up temp file on failure
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return False


def read_jsonl_best_effort(path: Path, min_valid: int = 1) -> tuple[list, int, int]:
    """
    Read JSONL file, skipping invalid lines.

    Args:
        path: JSONL file to read
        min_valid: Minimum valid offers required (default 1)

    Returns:
        Tuple of (offers_list, valid_count, skipped_count)
        Returns ([], 0, 0) if file doesn't exist or min_valid not met
    """
    if not path.exists():
        return [], 0, 0

    offers = []
    skipped = 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                    payload = record.get("payload")

                    if isinstance(payload, dict):
                        offers.append(payload)
                    else:
                        skipped += 1

                except json.JSONDecodeError:
                    skipped += 1
                    continue

    except Exception:
        return [], 0, 0

    # Check minimum valid threshold
    if len(offers) < min_valid:
        return [], len(offers), skipped

    return offers, len(offers), skipped


def cache_age_hours(path: Path) -> Optional[float]:
    """
    Calculate cache file age in hours from mtime.

    Args:
        path: Path to cache file

    Returns:
        Age in hours (float), or None if file doesn't exist
    """
    if not path.exists():
        return None

    try:
        mtime = path.stat().st_mtime
        age_seconds = time.time() - mtime
        return age_seconds / 3600.0
    except OSError:
        return None


def get_staleness_level(age_hours: Optional[float]) -> str:
    """
    Determine staleness level from cache age.

    Args:
        age_hours: Cache age in hours

    Returns:
        "fresh" (<24h), "warning" (24-72h), "critical" (>72h), or "unknown"
    """
    if age_hours is None:
        return "unknown"

    if age_hours > CACHE_CRITICAL_HOURS:
        return "critical"
    elif age_hours > CACHE_WARNING_HOURS:
        return "warning"
    else:
        return "fresh"
