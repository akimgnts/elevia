"""
rome_link.py - Read-only accessor for ROME link enrichment.
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"


def get_rome_link(offer_id: str) -> Optional[Dict[str, str]]:
    """
    Return ROME link info for an offer_id if present.
    Does not create or modify any tables.
    """
    if not DB_PATH.exists():
        return None

    conn = sqlite3.connect(str(DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT rome_code, rome_label FROM offer_rome_link WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
        if not row:
            return None
        return {"rome_code": row["rome_code"], "rome_label": row["rome_label"]}
    finally:
        conn.close()
