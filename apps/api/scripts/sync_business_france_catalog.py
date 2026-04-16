#!/usr/bin/env python3
"""
sync_business_france_catalog.py
===============================

Live-sync Business France offers into `offers.db` and purge stale BF offers
that are no longer present in the current Civiweb Azure catalog.

Flow:
  1. Scrape current BF catalog to a fresh raw JSONL file
  2. Ingest that raw file via the existing `ingest_business_france.py`
  3. Compare current live BF ids vs existing DB BF ids
  4. Delete stale BF rows from catalog tables

This script intentionally preserves user-history tables such as
`application_tracker`, `application_status_history`, and `apply_pack_runs`.
It only purges catalog-facing BF rows:
  - fact_offers
  - fact_offer_skills
  - offer_decisions
  - document_cache
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
RAW_BF_DIR = ROOT / "data" / "raw" / "business_france"
DB_PATH = ROOT / "data" / "db" / "offers.db"

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from ingest_business_france import extract_offer_fields  # type: ignore


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _latest_bf_raw() -> Path | None:
    if not RAW_BF_DIR.exists():
        return None
    files = sorted(RAW_BF_DIR.glob("bf_azure_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"[RUN] {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _backup_db() -> Path:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"offers.db not found: {DB_PATH}")
    backup_dir = ROOT / "data" / "db" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"offers_{_utc_stamp()}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"[BACKUP] {backup_path}")
    return backup_path


def _load_live_bf_ids(raw_file: Path) -> set[str]:
    current_ids: set[str] = set()
    with raw_file.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                payload = record.get("payload", {})
                if not isinstance(payload, dict):
                    continue
                offer = extract_offer_fields(payload)
                offer_id = offer.get("id")
                if isinstance(offer_id, str) and offer_id.startswith("BF-"):
                    current_ids.add(offer_id)
            except Exception as exc:
                print(f"[WARN] raw parse line {line_no}: {exc}")
    return current_ids


def _fetch_db_bf_ids(conn: sqlite3.Connection) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT id FROM fact_offers WHERE source='business_france'")
    return {row[0] for row in cur.fetchall() if row and row[0]}


def _delete_ids(cur: sqlite3.Cursor, table: str, column: str, ids: Iterable[str]) -> int:
    ids = list(ids)
    if not ids:
        return 0
    total = 0
    chunk_size = 400
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        placeholders = ",".join("?" for _ in chunk)
        sql = f"DELETE FROM {table} WHERE {column} IN ({placeholders})"
        cur.execute(sql, chunk)
        total += cur.rowcount if cur.rowcount != -1 else 0
    return total


def _purge_stale_bf(stale_ids: set[str]) -> dict[str, int]:
    if not stale_ids:
        return {"fact_offer_skills": 0, "offer_decisions": 0, "document_cache": 0, "fact_offers": 0}

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    try:
        cur = conn.cursor()
        stats = {
            "fact_offer_skills": _delete_ids(cur, "fact_offer_skills", "offer_id", stale_ids),
            "offer_decisions": _delete_ids(cur, "offer_decisions", "offer_id", stale_ids),
            "document_cache": _delete_ids(cur, "document_cache", "offer_id", stale_ids),
            "fact_offers": _delete_ids(cur, "fact_offers", "id", stale_ids),
        }
        conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _count_by_source() -> list[tuple[str, int]]:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        cur = conn.cursor()
        cur.execute("SELECT source, COUNT(*) FROM fact_offers GROUP BY source ORDER BY source")
        return [(row[0], row[1]) for row in cur.fetchall()]
    finally:
        conn.close()


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] DB missing: {DB_PATH}")
        return 1

    before_counts = _count_by_source()
    print(f"[BEFORE] {before_counts}")
    _backup_db()

    scraper = ROOT / "scripts" / "scrape_business_france_azure.py"
    ingestor = ROOT / "scripts" / "ingest_business_france.py"

    env = dict(**__import__("os").environ)
    env.setdefault("BF_AZURE_SKIP_DETAILS", "1")

    _run([sys.executable, str(scraper)], env=env)

    raw_file = _latest_bf_raw()
    if raw_file is None:
        print("[ERROR] no BF raw file found after scrape")
        return 1
    print(f"[RAW] {raw_file}")

    live_ids = _load_live_bf_ids(raw_file)
    print(f"[LIVE] current BF ids: {len(live_ids)}")
    if not live_ids:
        print("[ERROR] live BF id set is empty — aborting purge")
        return 1

    _run([sys.executable, str(ingestor), "--path", str(raw_file)], env=env)

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    try:
        db_ids_before_purge = _fetch_db_bf_ids(conn)
    finally:
        conn.close()

    stale_ids = db_ids_before_purge - live_ids
    new_or_kept = len(db_ids_before_purge & live_ids)
    print(f"[DIFF] db_bf={len(db_ids_before_purge)} live_bf={len(live_ids)} kept_or_updated={new_or_kept} stale={len(stale_ids)}")

    purge_stats = _purge_stale_bf(stale_ids)
    after_counts = _count_by_source()

    print("[PURGE]", json.dumps(purge_stats, ensure_ascii=False))
    print(f"[AFTER] {after_counts}")
    print("[DONE] business_france catalog synced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
