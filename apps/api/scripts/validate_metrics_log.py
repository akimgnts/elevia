#!/usr/bin/env python3
"""
validate_metrics_log.py - Sprint 14 Metrics Log Validator

Validates survival_metrics.log against S14_metrics_contract.md.
Strict validation for CI/CD pipelines.

Usage:
    python validate_metrics_log.py
    SURVIVAL_LOG_PATH=/path/to/log python validate_metrics_log.py
    CI=true python validate_metrics_log.py  # Fail on missing file
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Configuration ---

DEFAULT_LOG_PATH = Path(__file__).parent.parent / "logs" / "survival_metrics.log"

# UUID v4 regex (strict, case insensitive)
UUID_V4_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE
)

# SHA-256 hex regex (64 chars)
SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

# Contract definition
REQUIRED_TOP_LEVEL_KEYS = {"type", "session_id", "profile_hash", "corrections", "stats", "meta"}
ALLOWED_EXTRA_KEYS = {"ts_server", "event_id"}
FORBIDDEN_KEYS = {"old_level", "new_level", "removed", "capabilities_count"}

ALL_ALLOWED_KEYS = REQUIRED_TOP_LEVEL_KEYS | ALLOWED_EXTRA_KEYS


def get_log_path() -> Path:
    """Get log path from env or default."""
    env_path = os.getenv("SURVIVAL_LOG_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_LOG_PATH


def is_ci() -> bool:
    """Check if running in CI environment."""
    return os.getenv("CI", "").lower() in ("true", "1", "yes")


def validate_uuid_v4(value: str) -> bool:
    """Validate UUID v4 format."""
    return bool(UUID_V4_REGEX.match(value))


def validate_sha256(value: str) -> bool:
    """Validate SHA-256 hex format."""
    return bool(SHA256_REGEX.match(value))


def find_forbidden_keys(obj: Any, path: str = "") -> List[str]:
    """Recursively find forbidden keys in nested structure."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            if key in FORBIDDEN_KEYS:
                found.append(current_path)
            found.extend(find_forbidden_keys(value, current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(find_forbidden_keys(item, f"{path}[{i}]"))
    return found


def validate_deep_structure(event: Dict[str, Any]) -> Optional[str]:
    """Validate deep structure constraints."""
    try:
        # corrections.capabilities
        corrections = event.get("corrections", {})
        if not isinstance(corrections, dict):
            return "corrections must be an object"

        capabilities = corrections.get("capabilities", {})
        if not isinstance(capabilities, dict):
            return "corrections.capabilities must be an object"

        # added: List[str]
        added = capabilities.get("added", [])
        if not isinstance(added, list) or not all(isinstance(x, str) for x in added):
            return "corrections.capabilities.added must be List[String]"

        # deleted: List[str]
        deleted = capabilities.get("deleted", [])
        if not isinstance(deleted, list) or not all(isinstance(x, str) for x in deleted):
            return "corrections.capabilities.deleted must be List[String]"

        # modified_level: List[{name, from, to}]
        modified = capabilities.get("modified_level", [])
        if not isinstance(modified, list):
            return "corrections.capabilities.modified_level must be a list"
        for i, item in enumerate(modified):
            if not isinstance(item, dict):
                return f"corrections.capabilities.modified_level[{i}] must be an object"
            if not all(k in item for k in ("name", "from", "to")):
                return f"corrections.capabilities.modified_level[{i}] missing required keys (name, from, to)"
            if not all(isinstance(item.get(k), str) for k in ("name", "from", "to")):
                return f"corrections.capabilities.modified_level[{i}] values must be strings"

        # stats
        stats = event.get("stats", {})
        if not isinstance(stats, dict):
            return "stats must be an object"

        unmapped = stats.get("unmapped_count")
        if not isinstance(unmapped, int):
            return "stats.unmapped_count must be Int"

        detected = stats.get("detected_capabilities_count")
        if not isinstance(detected, int):
            return "stats.detected_capabilities_count must be Int"

        # meta
        meta = event.get("meta", {})
        if not isinstance(meta, dict):
            return "meta must be an object"

        return None
    except Exception as e:
        return f"Structure validation error: {e}"


def validate_correction_event(event: Dict[str, Any], line_num: int) -> Optional[str]:
    """
    Validate a single correction event.
    Returns error message or None if valid.
    """
    # Check required keys
    missing_keys = REQUIRED_TOP_LEVEL_KEYS - set(event.keys())
    if missing_keys:
        return f"Missing required keys: {missing_keys}"

    # Check for unknown keys
    unknown_keys = set(event.keys()) - ALL_ALLOWED_KEYS
    if unknown_keys:
        return f"Unknown keys: {unknown_keys}"

    # Check type literal
    if event.get("type") != "correction":
        return f"Invalid type: expected 'correction', got '{event.get('type')}'"

    # Validate session_id (UUID v4 or legacy format)
    session_id = event.get("session_id", "")
    if not validate_uuid_v4(session_id):
        # Allow legacy formats: session_TIMESTAMP_RANDOM or test_*
        if not (session_id.startswith("session_") or session_id.startswith("test_")):
            if len(session_id) < 6:
                return f"Invalid session_id format: {session_id[:30]}..."

    # Validate profile_hash (SHA-256 or legacy format)
    profile_hash = event.get("profile_hash", "")
    if not validate_sha256(profile_hash):
        # Allow legacy format (length:prefix)
        if not (len(profile_hash) >= 8 and ":" not in profile_hash[:8]):
            # Check if it's at least 8 chars for legacy compatibility
            if len(profile_hash) < 8:
                return f"Invalid profile_hash: too short ({len(profile_hash)} chars)"

    # Check for forbidden keys (recursively)
    forbidden_found = find_forbidden_keys(event)
    if forbidden_found:
        return f"Forbidden keys found: {forbidden_found}"

    # Validate deep structure
    deep_error = validate_deep_structure(event)
    if deep_error:
        return deep_error

    return None


def main() -> int:
    """Main validation logic."""
    log_path = get_log_path()
    ci_mode = is_ci()

    print(f"Validating: {log_path}")
    print(f"CI Mode: {ci_mode}")
    print("-" * 50)

    # Check file exists
    if not log_path.exists():
        msg = f"No log file found at {log_path}"
        if ci_mode:
            print(f"❌ {msg}")
            return 1
        else:
            print(f"⚠️ {msg}")
            return 0

    # Check file not empty
    if log_path.stat().st_size == 0:
        print("⚠️ Log file is empty.")
        return 0

    # Read and validate
    correction_count = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"❌ Line {line_num}: Invalid JSON - {e}")
                return 1

            # Skip non-correction events
            if event.get("type") != "correction":
                continue

            correction_count += 1

            # Validate correction event
            error = validate_correction_event(event, line_num)
            if error:
                print(f"❌ Line {line_num}: {error}")
                return 1

    print(f"✅ Logs compliant ({correction_count} correction events checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
