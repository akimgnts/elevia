"""
rome_link.py - Read-only utility to fetch ROME link for an offer.

Not wired into any endpoint yet. Pure utility for future use.
"""

import sqlite3
from typing import Dict, Iterable, Optional, TypedDict


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


def get_offer_rome_links(conn: sqlite3.Connection, offer_ids: Iterable[str]) -> Dict[str, RomeLink]:
    """Return a mapping of offer_id -> RomeLink for known offers."""
    ids = [oid for oid in offer_ids if oid]
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    try:
        rows = conn.execute(
            f"SELECT offer_id, rome_code, rome_label FROM offer_rome_link WHERE offer_id IN ({placeholders})",
            ids,
        ).fetchall()
    except sqlite3.OperationalError:
        return {}

    links: Dict[str, RomeLink] = {}
    for row in rows:
        links[str(row[0])] = RomeLink(rome_code=row[1], rome_label=row[2])
    return links
