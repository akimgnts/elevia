#!/usr/bin/env python3
"""
print_offer_uri_gaps.py — Pretty-print ESCO/Compass URI gap analysis.

Reads the JSON exported by audit_offer_uri_overlap.py and displays
the top-N gap lists in a compact, terminal-readable format.

Usage:
  python apps/api/scripts/print_offer_uri_gaps.py
  python apps/api/scripts/print_offer_uri_gaps.py --top 5
  python apps/api/scripts/print_offer_uri_gaps.py --namespace compass
  python apps/api/scripts/print_offer_uri_gaps.py --namespace all --top 15
  python apps/api/scripts/print_offer_uri_gaps.py --json /tmp/my_export.json

Exit codes:
  0  success
  2  input file not found
  3  expected key missing in JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_JSON = Path("/tmp/elevia_offer_uri_overlap.json")


# ── Formatting helpers ────────────────────────────────────────────────────────


def _shorten_uri(uri: str, width: int = 70) -> str:
    """Shorten long URIs for display while keeping them readable."""
    if len(uri) <= width:
        return uri
    # Keep the meaningful tail (last 2 path segments)
    parts = uri.rstrip("/").split("/")
    tail = "/".join(parts[-2:]) if len(parts) >= 2 else uri
    prefix = uri.split("/")[2] if "/" in uri else ""  # domain
    shortened = f"{prefix}/…/{tail}"
    return shortened if len(shortened) < len(uri) else uri


def _print_offer_missing(items: list, top: int, title: str) -> None:
    """
    Section A: offer URIs missing in profile.
    Item fields: uri, count, share
    """
    print(f"\n{'─' * 72}")
    print(f"  {title}")
    print(f"{'─' * 72}")
    if not items:
        print("  (empty)")
        return
    shown = items[:top]
    for i, item in enumerate(shown, 1):
        uri = item.get("uri", "?")
        count = item.get("count", "?")
        share = item.get("share")
        share_str = f"share={share:.4f}" if isinstance(share, float) else ""
        parts = [f"count={count}"]
        if share_str:
            parts.append(share_str)
        print(f"  {i:>2}. {_shorten_uri(uri)}")
        print(f"       {' | '.join(parts)}")


def _print_profile_missing(items: list, top: int, title: str) -> None:
    """
    Section B: profile URIs missing in offers.
    Item fields: uri, offer_count
    """
    print(f"\n{'─' * 72}")
    print(f"  {title}")
    print(f"{'─' * 72}")
    if not items:
        print("  (empty)")
        return
    shown = items[:top]
    for i, item in enumerate(shown, 1):
        uri = item.get("uri", "?")
        offer_count = item.get("offer_count", "?")
        print(f"  {i:>2}. {_shorten_uri(uri)}")
        print(f"       offer_count={offer_count}")


def _print_namespace(data: dict, ns_key: str, top: int, label: str) -> None:
    """Print both sections for one namespace.

    The audit script writes ``gaps_esco`` / ``gaps_compass`` when
    ``--namespace all`` is used, but falls back to the generic ``gaps`` key
    when a single namespace is requested (e.g. ``--namespace esco``).
    Try the specific key first, then ``gaps``.
    """
    block = data.get(ns_key)
    if block is None:
        block = data.get("gaps")
    if block is None:
        print(
            f"\n  ⚠  Key '{ns_key}' (or 'gaps') not found in JSON.\n"
            f"     Re-run audit_offer_uri_overlap.py to regenerate.",
            file=sys.stderr,
        )
        sys.exit(3)

    offer_missing_key = "top_offer_uris_missing_in_profile_top20"
    profile_missing_key = "top_profile_uris_missing_in_offers_top20"

    for key in (offer_missing_key, profile_missing_key):
        if key not in block:
            print(
                f"\n  ⚠  Key '{ns_key}.{key}' not found in JSON.\n"
                f"     Re-run audit_offer_uri_overlap.py to regenerate.",
                file=sys.stderr,
            )
            sys.exit(3)

    _print_offer_missing(
        block[offer_missing_key],
        top,
        f"[{label}] TOP offer URIs missing in profile ({top})",
    )
    _print_profile_missing(
        block[profile_missing_key],
        top,
        f"[{label}] TOP profile URIs missing in offers ({top})",
    )


# ── CLI ───────────────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Pretty-print URI gap analysis from audit_offer_uri_overlap.py output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--json",
        dest="json_path",
        default=str(DEFAULT_JSON),
        metavar="PATH",
        help=f"Path to the JSON export (default: {DEFAULT_JSON})",
    )
    p.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of entries to show per section (default: 10)",
    )
    p.add_argument(
        "--namespace",
        choices=["esco", "compass", "all"],
        default="esco",
        help="Namespace to display: esco | compass | all (default: esco)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    json_path = Path(args.json_path)

    if not json_path.exists():
        print(
            f"\n  ⚠  File not found: {json_path}\n"
            f"     Run audit_offer_uri_overlap.py first to generate it.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"\n  ⚠  Invalid JSON in {json_path}: {exc}", file=sys.stderr)
        sys.exit(3)

    top = max(1, args.top)
    print(f"\n  Source : {json_path}")
    print(f"  Top    : {top} per section")
    print(f"  NS     : {args.namespace}")

    if args.namespace in ("esco", "all"):
        _print_namespace(data, "gaps_esco", top, "ESCO")

    if args.namespace in ("compass", "all"):
        _print_namespace(data, "gaps_compass", top, "COMPASS")

    print(f"\n{'─' * 72}\n")


if __name__ == "__main__":
    main()
