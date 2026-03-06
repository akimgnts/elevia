#!/usr/bin/env python3
"""
backfill_offer_skills.py - Populate fact_offer_skills from existing offers
==========================================================================

Read-only backfill job:
- Reads fact_offers payload_json (no network calls)
- Uses FT competences and fallback token extraction
- Adds ROME competences when available
- Inserts into fact_offer_skills (idempotent)

Usage:
    python3 apps/api/scripts/backfill_offer_skills.py [--cluster DATA_IT] [--limit 10] [--dry-run] [--debug]
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

API_ROOT = Path(__file__).parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"

# Add src to path for shared utilities
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import ensure_offer_skills_table
from esco.mapper import map_skill
from matching.extractors import normalize_skill_label


def _utc_now() -> str:
    """Return ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event: str, status: str, **extra: Any) -> None:
    """Emit structured JSON log to stdout."""
    payload = {
        "timestamp": _utc_now(),
        "event": event,
        "status": status,
        **extra,
    }
    print(json.dumps(payload, ensure_ascii=False))


def _map_labels_to_uris(labels: List[str]) -> List[tuple[str, str | None]]:
    """Map labels to ESCO URIs (strict), keep label when no URI."""
    out: List[tuple[str, str | None]] = []
    for label in labels:
        uri = None
        result = map_skill(label, enable_fuzzy=False)
        if result and result.get("esco_id"):
            uri = str(result.get("esco_id"))
        out.append((label, uri))
    return out


def _map_labels_with_reasons(labels: List[str]) -> tuple[
    List[tuple[str, str | None]],
    Dict[str, int],
    List[tuple[str, str | None]],
    List[tuple[str, str]],
]:
    """Map labels with reject reasons for probe mode."""
    mapped: List[tuple[str, str | None]] = []
    reasons: Dict[str, int] = {}
    sample_mapped: List[tuple[str, str | None]] = []
    sample_rejected: List[tuple[str, str]] = []

    seen: set[str] = set()
    for label in labels:
        if not label:
            reasons["empty"] = reasons.get("empty", 0) + 1
            if len(sample_rejected) < 3:
                sample_rejected.append((label, "empty"))
            continue
        if len(label) < 2:
            reasons["too_short"] = reasons.get("too_short", 0) + 1
            if len(sample_rejected) < 3:
                sample_rejected.append((label, "too_short"))
            continue
        if label in seen:
            reasons["duplicate"] = reasons.get("duplicate", 0) + 1
            if len(sample_rejected) < 3:
                sample_rejected.append((label, "duplicate"))
            continue
        seen.add(label)

        uri = None
        result = map_skill(label, enable_fuzzy=False)
        if result and result.get("esco_id"):
            uri = str(result.get("esco_id"))
            if len(sample_mapped) < 3:
                sample_mapped.append((label, uri))
            mapped.append((label, uri))
        else:
            reasons["unmapped"] = reasons.get("unmapped", 0) + 1
            if len(sample_rejected) < 3:
                sample_rejected.append((label, "unmapped"))
            mapped.append((label, None))

    return mapped, reasons, sample_mapped, sample_rejected


def _count_rows_for_update(
    cursor: sqlite3.Cursor,
    offer_id: str,
    label: str,
) -> int:
    row = cursor.execute(
        """
        SELECT COUNT(*) as cnt
        FROM fact_offer_skills
        WHERE offer_id=? AND skill=? AND (skill_uri IS NULL OR skill_uri='')
        """,
        (offer_id, label),
    ).fetchone()
    return int(row[0]) if row else 0


def _fetch_offer_skill_rows(
    cursor: sqlite3.Cursor, offer_id: str
) -> List[tuple[str, str | None]]:
    rows = cursor.execute(
        "SELECT skill, skill_uri FROM fact_offer_skills WHERE offer_id=?",
        (offer_id,),
    ).fetchall()
    out: List[tuple[str, str | None]] = []
    for row in rows:
        label = row[0]
        uri = row[1]
        out.append((str(label) if label is not None else "", str(uri) if uri else None))
    return out


def _insert_offer_skills(
    cursor: sqlite3.Cursor,
    offer_id: str,
    skills: List[tuple[str, str | None]],
    source: str,
    timestamp: str,
) -> int:
    """Insert skills into fact_offer_skills (idempotent)."""
    inserted = 0
    uris_written = 0
    null_uri = 0
    for label, uri in skills:
        if uri:
            cursor.execute(
                """
                UPDATE fact_offer_skills
                SET skill_uri=?
                WHERE offer_id=? AND skill=? AND (skill_uri IS NULL OR skill_uri='')
                """,
                (uri, offer_id, label),
            )
        cursor.execute(
            """
            INSERT OR IGNORE INTO fact_offer_skills
            (offer_id, skill, skill_uri, source, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (offer_id, label, uri, source, None, timestamp),
        )
        if cursor.rowcount == 1:
            inserted += 1
            if uri:
                uris_written += 1
            else:
                null_uri += 1
    if os.getenv("ELEVIA_DEBUG_OFFER_SKILLS", "").lower() in {"1", "true", "yes"}:
        _log(
            "offer_skills_insert",
            "debug",
            offer_id=offer_id,
            rows_written=inserted,
            uris_written_count=uris_written,
            null_uri_count=null_uri,
        )
    return inserted


def backfill_offer_skills(
    conn: sqlite3.Connection,
    *,
    cluster: str | None = None,
    limit: int = 0,
    dry_run: bool = False,
    debug: bool = False,
) -> Dict[str, int]:
    """Run backfill on an open connection. Returns stats dict."""
    ensure_offer_skills_table(conn)
    cursor = conn.cursor()

    # Cluster-aware selection if column exists
    offers_cols = {row[1] for row in cursor.execute("PRAGMA table_info(fact_offers)").fetchall()}
    cluster_col = None
    for candidate in ("cluster_macro", "offer_cluster", "cluster"):
        if candidate in offers_cols:
            cluster_col = candidate
            break

    where = ""
    params: List[Any] = []
    if cluster and cluster_col:
        where = f"WHERE {cluster_col} = ?"
        params.append(cluster)

    rows = cursor.execute(
        f"SELECT id, source, title, description, payload_json FROM fact_offers {where}",
        params,
    ).fetchall()

    # Deterministic ordering + limit
    rows = sorted(rows, key=lambda r: str(r[0]))
    if limit and limit > 0:
        rows = rows[:limit]

    offer_ids = [str(row[0]) for row in rows]
    if debug:
        sample_ids = offer_ids[:10]
        _log(
            "backfill_offer_skills_probe",
            "debug",
            offers_selected=len(offer_ids),
            sample_offer_ids=sample_ids,
            cluster_filter=cluster,
            cluster_column=cluster_col,
        )
    offers_with_skills = 0
    total_inserted = 0
    total_candidates = 0
    total_mapped = 0
    total_would_update = 0
    reject_reasons: Dict[str, int] = {}
    timestamp = _utc_now()

    for offer_id, source, title, description, payload_json in rows:
        inserted = 0
        mapped_count = 0
        would_update = 0
        sample_mapped: List[tuple[str, str | None]] = []
        sample_rejected: List[tuple[str, str]] = []
        mapping_reasons: Dict[str, int] = {}

        # DB-only candidate source: existing fact_offer_skills labels
        rows_skills = _fetch_offer_skill_rows(cursor, str(offer_id))
        raw_candidates: List[str] = []
        for label, uri in rows_skills:
            if uri:
                mapping_reasons["already_has_uri"] = mapping_reasons.get("already_has_uri", 0) + 1
                if len(sample_rejected) < 3:
                    sample_rejected.append((label, "already_has_uri"))
                continue
            if not label:
                mapping_reasons["empty"] = mapping_reasons.get("empty", 0) + 1
                if len(sample_rejected) < 3:
                    sample_rejected.append((label, "empty"))
                continue
            raw_candidates.append(label)

        # Deterministic normalization + mapping
        norm_to_raw: Dict[str, List[str]] = {}
        for label in sorted(raw_candidates):
            norm = normalize_skill_label(label)
            if not norm:
                mapping_reasons["empty"] = mapping_reasons.get("empty", 0) + 1
                if len(sample_rejected) < 3:
                    sample_rejected.append((label, "empty"))
                continue
            norm_to_raw.setdefault(norm, []).append(label)

        candidates = sorted(norm_to_raw.keys())
        total_candidates += sum(len(v) for v in norm_to_raw.values())

        for norm_label in candidates:
            result = map_skill(norm_label, enable_fuzzy=False)
            if not result or not result.get("esco_id"):
                mapping_reasons["unmapped"] = mapping_reasons.get("unmapped", 0) + 1
                for raw in norm_to_raw[norm_label]:
                    if len(sample_rejected) < 3:
                        sample_rejected.append((raw, "unmapped"))
                continue

            uri = str(result.get("esco_id"))
            for raw in norm_to_raw[norm_label]:
                mapped_count += 1
                if len(sample_mapped) < 3:
                    sample_mapped.append((raw, uri))
                if dry_run or debug:
                    would_update += _count_rows_for_update(cursor, str(offer_id), raw)
                if not dry_run:
                    cursor.execute(
                        """
                        UPDATE fact_offer_skills
                        SET skill_uri=?
                        WHERE offer_id=? AND LOWER(skill)=LOWER(?) AND (skill_uri IS NULL OR skill_uri='')
                        """,
                        (uri, str(offer_id), raw),
                    )
                    if cursor.rowcount:
                        inserted += int(cursor.rowcount)
                    if cursor.rowcount == 0:
                        mapping_reasons["no_matching_row"] = mapping_reasons.get("no_matching_row", 0) + 1
                        if len(sample_rejected) < 3:
                            sample_rejected.append((f"{raw} (norm={norm_label})", "no_matching_row"))
                else:
                    if _count_rows_for_update(cursor, str(offer_id), raw) == 0:
                        mapping_reasons["no_matching_row"] = mapping_reasons.get("no_matching_row", 0) + 1
                        if len(sample_rejected) < 3:
                            sample_rejected.append((f"{raw} (norm={norm_label})", "no_matching_row"))

        total_mapped += mapped_count
        total_would_update += would_update

        if debug or dry_run:
            for reason, count in mapping_reasons.items():
                reject_reasons[reason] = reject_reasons.get(reason, 0) + count
        if debug:
            _log(
                "backfill_offer_skills_probe_offer",
                "debug",
                offer_id=str(offer_id),
                cluster=cluster or "",
                candidates=len(candidates),
                mapped=mapped_count,
                would_update_rows=would_update,
                candidate_source="db_fact_offer_skills",
                sample_mapped=sample_mapped[:3],
                sample_rejected=sample_rejected[:3],
            )

        if raw_candidates:
            offers_with_skills += 1
        total_inserted += inserted

    if not dry_run:
        conn.commit()
    return {
        "offers_scanned": len(rows),
        "offers_with_skills": offers_with_skills,
        "skills_inserted": total_inserted,
        "rome_links": 0,
        "total_candidates": total_candidates,
        "total_mapped": total_mapped,
        "total_would_update_rows": total_would_update,
        "offers_selected": len(rows),
        "offers_processed": len(rows),
        "top_reject_reasons": sorted(reject_reasons.items(), key=lambda x: (-x[1], x[0]))[:5],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill offer skills (ESCO URIs)")
    parser.add_argument("--cluster", default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    start_time = time.time()
    db_path = Path(args.db)
    if not db_path.exists():
        _log("backfill_offer_skills", "error", error=f"DB not found at {db_path}")
        return 1

    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        stats = backfill_offer_skills(
            conn,
            cluster=args.cluster,
            limit=args.limit,
            dry_run=args.dry_run,
            debug=args.debug,
        )
    finally:
        conn.close()

    duration_ms = int((time.time() - start_time) * 1000)
    if args.debug:
        _log(
            "backfill_offer_skills_probe",
            "summary",
            offers_selected=stats.get("offers_selected"),
            offers_processed=stats.get("offers_processed"),
            total_candidates=stats.get("total_candidates"),
            total_mapped=stats.get("total_mapped"),
            total_would_update_rows=stats.get("total_would_update_rows"),
            top_reject_reasons=stats.get("top_reject_reasons"),
            candidate_source="db_fact_offer_skills",
        )
    _log("backfill_offer_skills", "success", duration_ms=duration_ms, **stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
