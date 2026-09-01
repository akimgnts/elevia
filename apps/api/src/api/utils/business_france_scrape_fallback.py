"""
business_france_scrape_fallback.py - ScrapeGraphAI fallback for Business France ingestion
============================================================================================

Fallback acquisition path used ONLY when the primary Civiweb API path
(apps/api/scripts/scrape_business_france_azure.py -> fetch_catalog()) fails
(HTTP non-2xx, invalid JSON, network exception, empty body, or zero offers
when offers were expected).

Isolation (why this module never imports scrapegraphai directly):
`pip install --dry-run -r requirements.txt scrapegraphai` forces major
upgrades of fastapi/pydantic/httpx/openai/pypdf/python-multipart/uvicorn
to satisfy scrapegraphai's transitive floor pins (langchain>=1.2.0,
pydantic>=2.12.5, ...). That is exactly the kind of breakage
"ne casse aucune dépendance existante" rules out for the main API process.

So scrapegraphai and its full dependency tree (langchain, playwright, ...)
are installed in a SEPARATE virtualenv (see requirements-scrape-fallback.txt
and the Dockerfile: /opt/scrape-fallback-venv). This module only shells out
to scripts/scrapegraph_bf_runner.py — which runs inside that isolated venv —
and parses its single-line JSON stdout contract. The main FastAPI process's
dependency graph is completely unaffected whether or not this fallback venv
exists or works.

Role of this fallback (deliberately minimal):
    WEB page -> raw structured offer dicts -> caller persists via persist_raw_offers()
Nothing else. No enrichment, no scoring, no cleaning — those stay exactly as
they are downstream of raw_offers.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# apps/api/src/api/utils/business_france_scrape_fallback.py -> parents[3] == apps/api
API_ROOT = Path(__file__).resolve().parents[3]
RUNNER_SCRIPT = API_ROOT / "scripts" / "scrapegraph_bf_runner.py"

ENV_FALLBACK_VENV_PYTHON = "SCRAPEGRAPH_VENV_PYTHON"
DEFAULT_FALLBACK_VENV_PYTHON = "/opt/scrape-fallback-venv/bin/python"

DEFAULT_TARGET_URL = "https://mon-vie-via.businessfrance.fr/offres"
FALLBACK_MAX_OFFERS = 20  # experimental engine — never a backfill, see DECISIONS.md
DEFAULT_TIMEOUT_SEC = 90
SUBPROCESS_TIMEOUT_MARGIN_SEC = 30


@dataclass
class FallbackResult:
    """Result of one ScrapeGraphAI fallback attempt."""

    status: str  # "success" | "error" | "unavailable"
    engine: str = "scrapegraph"
    page_used: str | None = None
    offers: list[dict[str, Any]] = field(default_factory=list)
    offers_recovered: int = 0
    error: str | None = None


def _resolve_fallback_python() -> str | None:
    override = (os.environ.get(ENV_FALLBACK_VENV_PYTHON) or "").strip()
    candidate = Path(override) if override else Path(DEFAULT_FALLBACK_VENV_PYTHON)
    return str(candidate) if candidate.exists() else None


def is_fallback_available() -> bool:
    """True only if the isolated venv AND the runner script both exist."""
    return _resolve_fallback_python() is not None and RUNNER_SCRIPT.exists()


def scrape_business_france_offers(
    *,
    url: str = DEFAULT_TARGET_URL,
    limit: int = FALLBACK_MAX_OFFERS,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> FallbackResult:
    """
    Runs the ScrapeGraphAI fallback (isolated venv, subprocess) and returns
    offers already reshaped to the same envelope keys produced by
    scrape_business_france_azure.normalize_payload(): id / title /
    description / company / city / country / publicationDate / offerUrl /
    bf_source — so callers can feed the result straight into the same
    persist_raw_offers() path used by the primary API scraper.

    Never persists anything itself — pure acquisition, no DB writes.
    """
    limit = max(1, min(int(limit), FALLBACK_MAX_OFFERS))

    python_bin = _resolve_fallback_python()
    if not python_bin:
        return FallbackResult(
            status="unavailable",
            page_used=url,
            error=(
                f"scrape-fallback venv not provisioned "
                f"({ENV_FALLBACK_VENV_PYTHON} unset and {DEFAULT_FALLBACK_VENV_PYTHON} missing)"
            ),
        )
    if not RUNNER_SCRIPT.exists():
        return FallbackResult(status="unavailable", page_used=url, error=f"runner script missing: {RUNNER_SCRIPT}")

    cmd = [python_bin, str(RUNNER_SCRIPT), "--url", url, "--limit", str(limit), "--timeout", str(timeout)]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + SUBPROCESS_TIMEOUT_MARGIN_SEC,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return FallbackResult(
            status="error", page_used=url,
            error=f"scrapegraph runner timed out after {timeout + SUBPROCESS_TIMEOUT_MARGIN_SEC}s",
        )
    except Exception as exc:
        return FallbackResult(status="error", page_used=url, error=f"failed to launch scrapegraph runner: {exc}")

    stdout_lines = (completed.stdout or "").strip().splitlines()
    if not stdout_lines:
        return FallbackResult(
            status="error",
            page_used=url,
            error=(completed.stderr or "empty runner output").strip()[:500],
        )
    try:
        payload = json.loads(stdout_lines[-1])
    except json.JSONDecodeError as exc:
        return FallbackResult(status="error", page_used=url, error=f"unparsable runner output: {exc}")

    raw_offers = payload.get("offers") or []
    normalized = [_normalize_fallback_offer(o) for o in raw_offers if isinstance(o, dict)]
    # Never persist an offer without a real Business France id — no random ids invented.
    normalized = [o for o in normalized if o.get("id")]
    # Dedupe by id within this single batch (idempotence is enforced downstream
    # by UNIQUE(source, external_id), but a clean batch should not rely on that).
    seen_ids: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for offer in normalized:
        if offer["id"] in seen_ids:
            continue
        seen_ids.add(offer["id"])
        deduped.append(offer)
    normalized = deduped

    if normalized:
        return FallbackResult(
            status="success",
            page_used=payload.get("page_used") or url,
            offers=normalized,
            offers_recovered=len(normalized),
        )
    return FallbackResult(
        status="error",
        page_used=payload.get("page_used") or url,
        error=payload.get("error") or "scrapegraph returned zero usable offers",
    )


def _normalize_fallback_offer(item: dict[str, Any]) -> dict[str, Any]:
    external_id = item.get("external_id") or item.get("id")
    external_id = str(external_id).strip() if external_id not in (None, "") else ""
    offer_url = (item.get("offer_url") or item.get("url") or "").strip()
    if not external_id and offer_url:
        # Defense in depth: the runner already derives an id from the URL tail
        # when no explicit id is present, but this normalizer must not rely
        # solely on the runner having done so — never invent an id, but do
        # derive one deterministically from the URL when possible.
        tail = offer_url.rstrip("/").rsplit("/", 1)[-1].strip()
        external_id = tail
    if not offer_url and external_id:
        offer_url = f"https://mon-vie-via.businessfrance.fr/offres/{external_id}"
    return {
        "id": external_id or None,
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "profile": item.get("profile") or "",
        "company": item.get("company") or "",
        "city": item.get("location") or item.get("city") or "",
        "country": item.get("country") or "",
        "publicationDate": item.get("publication_date") or item.get("publicationDate"),
        "offerUrl": offer_url or None,
        "bf_source": "BF_SCRAPEGRAPH_FALLBACK",
    }
