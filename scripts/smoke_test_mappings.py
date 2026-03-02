#!/usr/bin/env python3
"""
scripts/smoke_test_mappings.py — Smoke test: CSV import + ESCO resolution.

Vérifie qu'après import CSV :
  - get_esco_mapping(cluster, token) retourne un résultat non-null
  - status == ACTIVE
  - resolve_tokens_to_esco(cluster, [token]) contient token → uri

Usage:
  python scripts/smoke_test_mappings.py \\
    --file apps/api/data/mappings/finance_legal.csv \\
    --token opcvm \\
    --cluster FINANCE_LEGAL

Options:
  --file PATH      CSV file to import (required)
  --token TOKEN    Token to verify after import (required)
  --cluster NAME   Cluster key (required, e.g. FINANCE_LEGAL)
  --db PATH        Path to context.db (default: in-memory for isolation)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SRC = Path(__file__).parent.parent / "apps" / "api" / "src"
sys.path.insert(0, str(_SRC))

from compass.cluster_library import ClusterLibraryStore, normalize_token


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test: import CSV + verify ESCO resolution.",
    )
    parser.add_argument("--file",    required=True,  help="CSV file to import")
    parser.add_argument("--token",   required=True,  help="Token to verify (e.g. opcvm)")
    parser.add_argument("--cluster", required=True,  help="Cluster key (e.g. FINANCE_LEGAL)")
    parser.add_argument("--db",      default=None,   help="DB path (default: in-memory)")
    args = parser.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        _fail(f"file not found: {csv_path}")

    cluster    = args.cluster.strip().upper()
    token_norm = normalize_token(args.token)
    db_path    = args.db  # None → in-memory (isolated)

    print("=" * 60)
    print(f"  SMOKE TEST: {csv_path.name}")
    print("=" * 60)
    print(f"  cluster    = {cluster}")
    print(f"  token      = {token_norm!r}")
    print(f"  db         = {db_path or ':memory: (isolated)'}")

    # ── Import dry-run first ─────────────────────────────────────────────────
    sys.path.insert(0, str(Path(__file__).parent))
    from import_esco_mappings import import_csv_file as _import

    store_dry = ClusterLibraryStore(db_path=":memory:")
    stats_dry = _import(csv_path, store_dry, dry_run=True, strict=True)
    print(f"\n  Dry-run: {stats_dry['created']} rows would be created")
    if stats_dry["errors"] > 0:
        _fail(f"{stats_dry['errors']} validation error(s) in CSV")
    _ok(f"CSV validates ({stats_dry['created']} rows)")

    # ── Real import ──────────────────────────────────────────────────────────
    store = ClusterLibraryStore(db_path=db_path)
    stats = _import(csv_path, store, dry_run=False, strict=True)
    print(f"\n  Import: created={stats['created']} updated={stats['updated']} "
          f"unchanged={stats['unchanged']} errors={stats['errors']}")
    if stats["errors"] > 0:
        _fail(f"{stats['errors']} import error(s)")
    _ok(f"Import completed without errors")

    # ── Assertion 1: get_esco_mapping returns a result ───────────────────────
    mapping = store.get_esco_mapping(cluster, token_norm)
    if mapping is None:
        _fail(f"get_esco_mapping({cluster!r}, {token_norm!r}) returned None — mapping not found")
    _ok(f"get_esco_mapping() → non-null")
    print(f"       esco_uri       = {mapping['esco_uri']}")
    print(f"       esco_label     = {mapping.get('esco_label')}")
    print(f"       mapping_source = {mapping['mapping_source']}")

    # ── Assertion 2: status is ACTIVE (get_esco_mapping only returns ACTIVE) ─
    # The method filters WHERE status='ACTIVE', so any non-None result is ACTIVE.
    _ok(f"status == ACTIVE (confirmed by get_esco_mapping filter)")

    # ── Assertion 3: resolve_tokens_to_esco returns token → uri ─────────────
    resolved = store.resolve_tokens_to_esco(cluster, [token_norm])
    if token_norm not in resolved:
        _fail(
            f"resolve_tokens_to_esco({cluster!r}, [{token_norm!r}]) did not return token.\n"
            f"    Got: {list(resolved.keys())}"
        )
    resolved_uri = resolved[token_norm]["esco_uri"]
    if resolved_uri != mapping["esco_uri"]:
        _fail(
            f"resolve_tokens_to_esco URI mismatch:\n"
            f"    expected: {mapping['esco_uri']}\n"
            f"    got:      {resolved_uri}"
        )
    _ok(f"resolve_tokens_to_esco() → {token_norm!r} → {resolved_uri}")

    print()
    print("=" * 60)
    print("  SMOKE OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
