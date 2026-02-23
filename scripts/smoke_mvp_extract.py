#!/usr/bin/env python3
"""
smoke_mvp_extract.py — JSON field extractor for smoke_mvp.sh

Usage:
  python3 scripts/smoke_mvp_extract.py <json_file> <field_path> [default]

field_path: dot-separated key path, e.g. "meta.offer_title", "items.0.offer_id"
"""
import json
import sys


def get_nested(obj, path: str, default=""):
    """Navigate dot-separated path in a dict/list."""
    parts = path.split(".")
    cur = obj
    for p in parts:
        if cur is None:
            return default
        if isinstance(cur, list):
            try:
                cur = cur[int(p)]
            except (ValueError, IndexError):
                return default
        elif isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return default
    return cur if cur is not None else default


def main():
    if len(sys.argv) < 3:
        print("Usage: smoke_mvp_extract.py <json_file> <field_path> [default]", file=sys.stderr)
        sys.exit(1)

    json_file = sys.argv[1]
    field_path = sys.argv[2]
    default = sys.argv[3] if len(sys.argv) > 3 else ""

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_file}: {e}", file=sys.stderr)
        print(default)
        return

    value = get_nested(data, field_path, default)
    if isinstance(value, (dict, list)):
        print(json.dumps(value))
    else:
        print(str(value) if value is not None else default)


if __name__ == "__main__":
    main()
