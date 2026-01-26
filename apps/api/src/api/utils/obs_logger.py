"""
obs_logger.py - Structured observability logging
Sprint 21 - Minimal observability for API endpoints

Outputs JSON to stdout for Railway/container ingestion.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now() -> str:
    """Return ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def obs_log(
    event: str,
    *,
    run_id: Optional[str] = None,
    profile_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    status: str = "success",
    error_code: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a structured observability event to stdout.

    Required fields per Sprint 21:
    - run_id: Unique identifier for the operation
    - profile_id: Profile identifier (if applicable)
    - duration_ms: Operation duration in milliseconds
    - status: success | error | warning
    - error_code: Machine-readable error code (if status=error)

    Args:
        event: Event name (cv_ingested, match_run, catalog_fetch)
        run_id: Unique run identifier
        profile_id: Profile ID if applicable
        duration_ms: Duration in milliseconds
        status: Operation status
        error_code: Error code if applicable
        extra: Additional context fields
    """
    log_entry = {
        "timestamp": _utc_now(),
        "event": event,
        "run_id": run_id or str(uuid.uuid4())[:8],
        "status": status,
    }

    if profile_id is not None:
        log_entry["profile_id"] = profile_id

    if duration_ms is not None:
        log_entry["duration_ms"] = duration_ms

    if error_code is not None:
        log_entry["error_code"] = error_code

    if extra:
        log_entry.update(extra)

    # Output as JSON line to stdout
    print(json.dumps(log_entry), file=sys.stdout, flush=True)
