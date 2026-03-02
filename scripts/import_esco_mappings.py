#!/usr/bin/env python3
"""
scripts/import_esco_mappings.py — Import CSV of DOMAIN→ESCO mappings (idempotent).

DEV ONLY. Aucun impact sur la formule de scoring.

Usage:
  python scripts/import_esco_mappings.py --file apps/api/data/mappings/finance_legal.csv
  python scripts/import_esco_mappings.py --file apps/api/data/mappings/data_it.csv --dry-run
  python scripts/import_esco_mappings.py --file apps/api/data/mappings/finance_legal.csv --db /path/to/context.db

Options:
  --file PATH     CSV file to import (required)
  --db PATH       Path to context.db (default: apps/api/data/db/context.db)
  --dry-run       Read + validate only, no writes
  --strict        Fail immediately on first invalid row

CSV format (header obligatoire):
  cluster,token,esco_uri,esco_label,status,mapping_source

Rules:
  - Lines starting with # are comments (skipped)
  - Empty lines are skipped
  - status: ACTIVE (default) or INACTIVE — INACTIVE rows are skipped
  - mapping_source: manual (default), alias_lookup, or llm_suggestion
  - esco_uri must start with http://data.europa.eu/esco/
  - token is normalized via normalize_token() before insert
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path
from typing import Optional

_SRC = Path(__file__).parent.parent / "apps" / "api" / "src"
sys.path.insert(0, str(_SRC))

from compass.cluster_library import ClusterLibraryStore, normalize_token

# ── Constants ─────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {"cluster", "token", "esco_uri"}
VALID_STATUS      = {"ACTIVE", "INACTIVE"}
VALID_SOURCES     = {"manual", "alias_lookup", "llm_suggestion"}
ESCO_URI_PREFIX   = "http://data.europa.eu/esco/"


# ── Core import function (reusable from tests) ────────────────────────────────

def import_csv_file(
    csv_path: Path,
    store: ClusterLibraryStore,
    *,
    dry_run: bool = False,
    strict: bool = False,
) -> dict:
    """
    Import a CSV mapping file into the given ClusterLibraryStore.

    Returns a stats dict: {created, updated, unchanged, skipped, errors}.
    If dry_run=True, no writes are performed.
    If strict=True, raises ValueError on first invalid row.
    """
    stats = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0}
    error_lines: list[str] = []

    text = csv_path.read_text(encoding="utf-8")

    # Strip comment lines before feeding to csv.DictReader
    cleaned_lines = [
        line for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not cleaned_lines:
        return stats

    reader = csv.DictReader(io.StringIO("\n".join(cleaned_lines)))

    # Validate header
    if not reader.fieldnames:
        raise ValueError(f"Empty CSV or missing header: {csv_path}")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}. Got: {reader.fieldnames}")

    for line_num, row in enumerate(reader, start=2):  # start=2 because row 1 = header
        # ── Validate required fields ──────────────────────────────────────────
        cluster = (row.get("cluster") or "").strip().upper()
        token   = (row.get("token") or "").strip()
        esco_uri = (row.get("esco_uri") or "").strip()
        esco_label  = (row.get("esco_label") or "").strip() or None
        status      = (row.get("status") or "ACTIVE").strip().upper() or "ACTIVE"
        source      = (row.get("mapping_source") or "manual").strip().lower() or "manual"

        def _err(msg: str) -> bool:
            full = f"  line {line_num}: {msg}"
            error_lines.append(full)
            stats["errors"] += 1
            if strict:
                raise ValueError(full)
            return False

        if not cluster:
            _err("cluster is empty"); continue
        if not token:
            _err("token is empty"); continue
        if not esco_uri:
            _err("esco_uri is empty"); continue
        if not esco_uri.startswith(ESCO_URI_PREFIX):
            _err(f"esco_uri must start with '{ESCO_URI_PREFIX}', got: {esco_uri!r}"); continue
        if status not in VALID_STATUS:
            _err(f"status must be ACTIVE or INACTIVE, got: {status!r}"); continue
        if source not in VALID_SOURCES:
            _err(f"mapping_source must be one of {VALID_SOURCES}, got: {source!r}"); continue

        # INACTIVE rows are not imported
        if status == "INACTIVE":
            stats["skipped"] += 1
            continue

        token_norm = normalize_token(token)
        if not token_norm:
            _err(f"token {token!r} normalises to empty string"); continue

        # ── Determine created / updated / unchanged ───────────────────────────
        existing = store.get_esco_mapping(cluster, token_norm)

        if existing is None:
            if not dry_run:
                store.add_esco_mapping(cluster, token_norm, esco_uri, esco_label, source)
            stats["created"] += 1
        else:
            # Compare all mutable fields
            same = (
                existing["esco_uri"]        == esco_uri
                and existing.get("esco_label")   == esco_label
                and existing["mapping_source"]   == source
            )
            if same:
                stats["unchanged"] += 1
            else:
                if not dry_run:
                    store.add_esco_mapping(cluster, token_norm, esco_uri, esco_label, source)
                stats["updated"] += 1

    # Surface errors at end (unless strict already raised)
    if error_lines:
        for msg in error_lines:
            print(msg, file=sys.stderr)

    return stats


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import DOMAIN→ESCO mappings from CSV into context.db (idempotent).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--file", required=True, help="CSV file to import")
    parser.add_argument("--db",   default=None, help="Path to context.db")
    parser.add_argument("--dry-run", action="store_true", help="Read + validate only, no writes")
    parser.add_argument("--strict",  action="store_true", help="Fail fast on first invalid row")
    args = parser.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        print(f"ERROR: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    store = ClusterLibraryStore(db_path=args.db)
    mode  = " [DRY-RUN]" if args.dry_run else ""

    print(f"Importing{mode}: {csv_path}")
    print(f"  DB: {store._db_path}")

    try:
        stats = import_csv_file(csv_path, store, dry_run=args.dry_run, strict=args.strict)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    total = sum(stats.values())
    print(f"\nResults{mode}:")
    print(f"  created   = {stats['created']}")
    print(f"  updated   = {stats['updated']}")
    print(f"  unchanged = {stats['unchanged']}")
    print(f"  skipped   = {stats['skipped']} (INACTIVE rows)")
    print(f"  errors    = {stats['errors']}")
    print(f"  ─────────────────")
    print(f"  total rows = {total}")

    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
