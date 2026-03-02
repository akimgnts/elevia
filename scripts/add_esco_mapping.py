#!/usr/bin/env python3
"""
scripts/add_esco_mapping.py — Add a DOMAIN→ESCO mapping to context.db.

DEV ONLY. No impact on scoring formula.

Usage:
  python scripts/add_esco_mapping.py \\
    --cluster FINANCE \\
    --token opcvm \\
    --uri http://data.europa.eu/esco/skill/XXXX \\
    --label "Gestion de fonds d'investissement" \\
    --source manual
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src/ to path so compass.cluster_library is importable without installing
_SRC = Path(__file__).parent.parent / "apps" / "api" / "src"
sys.path.insert(0, str(_SRC))

from compass.cluster_library import ClusterLibraryStore, normalize_token


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add or update a DOMAIN→ESCO mapping in context.db.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cluster", required=True, help="Cluster key (e.g. FINANCE, DATA_IT)")
    parser.add_argument("--token", required=True, help="Domain token to map (will be normalized)")
    parser.add_argument("--uri", required=True, help="Target ESCO URI")
    parser.add_argument("--label", default=None, help="Human-readable ESCO label (optional)")
    parser.add_argument(
        "--source",
        default="manual",
        choices=["manual", "alias_lookup", "llm_suggestion"],
        help="Mapping source (default: manual)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to context.db (default: apps/api/data/db/context.db)",
    )
    args = parser.parse_args()

    cluster = args.cluster.strip().upper()
    token_norm = normalize_token(args.token)

    if not token_norm:
        print(f"ERROR: token '{args.token}' normalises to empty string.", file=sys.stderr)
        sys.exit(1)

    store = ClusterLibraryStore(db_path=args.db)

    # Insert / upsert — always ACTIVE (see add_esco_mapping SQL)
    store.add_esco_mapping(
        cluster=cluster,
        token=token_norm,
        esco_uri=args.uri.strip(),
        esco_label=args.label.strip() if args.label else None,
        mapping_source=args.source,
    )

    print("Mapping added:")
    print(f"  cluster={cluster}")
    print(f"  token={token_norm}")
    print(f"  uri={args.uri.strip()}")
    print(f"  label={args.label or '(none)'}")
    print(f"  source={args.source}")
    print(f"  status=ACTIVE")

    # Verification round-trip
    result = store.get_esco_mapping(cluster, token_norm)
    if result and result["esco_uri"] == args.uri.strip():
        print("\nVerification OK")
    else:
        print(
            f"\nWARNING: verification failed. get_esco_mapping returned: {result}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
