"""
rome_link.py - Read-only utility to fetch ROME link for an offer.

Not wired into any endpoint yet. Pure utility for future use.
"""

import sqlite3
from typing import Dict, Iterable, List, Optional, TypedDict


class RomeLink(TypedDict):
    rome_code: Optional[str]
    rome_label: Optional[str]


class RomeCompetence(TypedDict):
    competence_code: str
    competence_label: str
    esco_uri: Optional[str]


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


def get_rome_competences_for_rome_codes(
    conn: sqlite3.Connection,
    rome_codes: Iterable[str],
    limit_per_rome: int = 3,
) -> Dict[str, List[RomeCompetence]]:
    """Return a mapping of rome_code -> list of up to N competences."""
    codes = [code for code in rome_codes if code]
    if not codes:
        return {}

    placeholders = ",".join("?" for _ in codes)
    try:
        rows = conn.execute(
            f"""
            SELECT b.rome_code, c.competence_code, c.competence_label, c.esco_uri
            FROM bridge_rome_metier_competence b
            JOIN dim_rome_competence c ON c.competence_code = b.competence_code
            WHERE b.rome_code IN ({placeholders})
            ORDER BY b.rome_code ASC, c.competence_code ASC
            """,
            codes,
        ).fetchall()
    except sqlite3.OperationalError:
        return {}

    result: Dict[str, List[RomeCompetence]] = {}
    for row in rows:
        rome_code = str(row[0])
        bucket = result.setdefault(rome_code, [])
        if len(bucket) >= limit_per_rome:
            continue
        bucket.append(
            RomeCompetence(
                competence_code=row[1],
                competence_label=row[2],
                esco_uri=row[3],
            )
        )
    return result
