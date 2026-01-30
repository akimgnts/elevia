"""
rome_link.py - Read-only utility to fetch ROME link for an offer.

Not wired into any endpoint yet. Pure utility for future use.
"""

import sqlite3
from typing import Optional, TypedDict


class RomeLink(TypedDict):
    rome_code: Optional[str]
    rome_label: Optional[str]


def get_offer_rome_link(conn: sqlite3.Connection, offer_id: str) -> Optional[RomeLink]:
    """Return the ROME link for an offer, or None if not enriched yet."""
    try:
        row = conn.execute(
            "SELECT rome_code, rome_label FROM offer_rome_link WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        # Table doesn't exist
        return None

    if row is None:
        return None

    return RomeLink(rome_code=row[0], rome_label=row[1])
