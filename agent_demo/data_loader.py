from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
OFFERS_DB_PATH = REPO_ROOT / "apps" / "api" / "data" / "db" / "offers.db"


@dataclass(frozen=True)
class OfferRecord:
    id: str
    title: str
    company: str
    city: str
    country: str
    source: str
    publication_date: str
    description: str
    payload: dict

    @property
    def is_vie(self) -> bool:
        return bool(self.payload.get("is_vie", self.payload.get("missionType") == "VIE"))


class OfferDataUnavailable(RuntimeError):
    """Raised when the repo offer data source cannot be opened."""


def _connect_read_only(db_path: Path | None = None) -> sqlite3.Connection:
    db_path = db_path or OFFERS_DB_PATH
    if not db_path.exists():
        raise OfferDataUnavailable(f"offers.db not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_offer(row: sqlite3.Row) -> OfferRecord:
    payload = {}
    payload_raw = row["payload_json"]
    if payload_raw:
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = {}
    return OfferRecord(
        id=row["id"],
        title=row["title"],
        company=row["company"] or "Entreprise non renseignée",
        city=row["city"] or "Ville non renseignée",
        country=row["country"] or "Pays non renseigné",
        source=row["source"],
        publication_date=row["publication_date"] or "",
        description=row["description"] or "",
        payload=payload,
    )


def list_offers(limit: int = 10, source: str = "business_france") -> list[OfferRecord]:
    query = """
        SELECT id, source, title, description, company, city, country, publication_date, payload_json
        FROM fact_offers
    """
    params: list[object] = []
    if source:
        query += " WHERE source = ?"
        params.append(source)
    query += " ORDER BY publication_date DESC, id DESC LIMIT ?"
    params.append(limit)

    with _connect_read_only() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_offer(row) for row in rows]


def get_offer(offer_id: str) -> Optional[OfferRecord]:
    with _connect_read_only() as conn:
        row = conn.execute(
            """
            SELECT id, source, title, description, company, city, country, publication_date, payload_json
            FROM fact_offers
            WHERE id = ?
            """,
            (offer_id,),
        ).fetchone()
    return _row_to_offer(row) if row else None


def get_latest_offer(source: str = "business_france") -> Optional[OfferRecord]:
    offers = list_offers(limit=1, source=source)
    return offers[0] if offers else None


def resolve_offer(offer_id: Optional[str] = None, source: str = "business_france") -> OfferRecord:
    offer = get_offer(offer_id) if offer_id else get_latest_offer(source=source)
    if not offer:
        selector = offer_id or f"latest source={source}"
        raise OfferDataUnavailable(f"No offer available for selector: {selector}")
    return offer


def load_candidate_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Candidate file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Candidate file is empty: {path}")
    return text


def format_offer_for_prompt(offer: OfferRecord, max_description_chars: int = 4000) -> str:
    payload = offer.payload or {}
    role_lines: list[str] = [
        f"Offer ID: {offer.id}",
        f"Title: {offer.title}",
        f"Company: {offer.company}",
        f"Location: {offer.city}, {offer.country}",
        f"Source: {offer.source}",
    ]
    if offer.publication_date:
        role_lines.append(f"Publication date: {offer.publication_date}")
    if payload.get("missionType"):
        role_lines.append(f"Contract type: {payload['missionType']}")
    if payload.get("missionDuration"):
        role_lines.append(f"Duration (months): {payload['missionDuration']}")

    details: list[str] = []
    if payload.get("missionDescription"):
        details.append("Mission description:\n" + str(payload["missionDescription"]).strip())
    if payload.get("missionProfile"):
        details.append("Candidate profile:\n" + str(payload["missionProfile"]).strip())
    if payload.get("organizationPresentation"):
        details.append("Company context:\n" + str(payload["organizationPresentation"]).strip())
    if not details:
        details.append("Description:\n" + offer.description.strip())

    body = "\n\n".join(details).strip()
    if max_description_chars and len(body) > max_description_chars:
        body = body[: max_description_chars - 1].rstrip() + "…"

    return "\n".join(role_lines) + "\n\n" + body


def format_offer_listing(offers: Iterable[OfferRecord]) -> str:
    lines = []
    for offer in offers:
        lines.append(
            f"{offer.id} | {offer.title} | {offer.company} | {offer.city}, {offer.country} | {offer.publication_date}"
        )
    return "\n".join(lines)
