#!/usr/bin/env python3
"""
scrapegraph_bf_runner.py - ScrapeGraphAI runner for the Business France fallback
==================================================================================

RUNS ONLY INSIDE THE ISOLATED FALLBACK VENV (/opt/scrape-fallback-venv, see
requirements-scrape-fallback.txt and the Dockerfile). Never imported by the
main FastAPI process — it is only invoked as a subprocess by
apps/api/src/api/utils/business_france_scrape_fallback.py, which is the only
supported entry point into this fallback path.

Contract: prints exactly ONE JSON line to stdout, always, success or failure:
    {"status": "success"|"error", "engine": "scrapegraph", "page_used": "...",
     "offers": [...], "offers_found": N, "error": "..."|null}

Never invents an offer id. An extracted item with no discoverable id
(explicit id/reference field, or the trailing path segment of its URL) is
dropped rather than assigned a random one.

Usage:
    python3 scrapegraph_bf_runner.py --url https://mon-vie-via.businessfrance.fr/offres --limit 10

Variables d'environnement :
    OPENAI_API_KEY        Réutilisé tel quel (même credential que le reste d'Elevia)
    SCRAPEGRAPH_LLM_MODEL Modèle LLM ScrapeGraphAI (défaut : openai/gpt-4o-mini)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

DEFAULT_URL = "https://mon-vie-via.businessfrance.fr/offres"
DEFAULT_MODEL = "openai/gpt-4o-mini"

EXTRACTION_PROMPT = (
    "Extract every job/VIE offer listed on this page as a JSON array named 'offers'. "
    "For each offer, extract exactly these fields when actually present on the page: "
    "external_id (the offer's own identifier, from the page content or its detail URL), "
    "title (mission title), company (organization/company name), "
    "location (city and/or country as shown), description (mission description), "
    "profile (candidate profile / requirements, if shown), "
    "publication_date (creation or publication date, if shown), "
    "offer_url (the absolute URL of the offer's detail page). "
    "Do not invent or guess any value that is not visibly present on the page. "
    "Omit a field entirely for a given offer if it is not present."
)


def _build_result(page_used: str) -> dict[str, Any]:
    return {
        "status": "error",
        "engine": "scrapegraph",
        "page_used": page_used,
        "offers": [],
        "offers_found": 0,
        "error": None,
    }


def _run_scrapegraph(url: str, limit: int, timeout: int) -> Any:
    """Isolated in its own function so the exact scrapegraphai call surface
    (which evolves across versions) is easy to adjust in one place."""
    from scrapegraphai.graphs import SmartScraperGraph

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    model = (os.environ.get("SCRAPEGRAPH_LLM_MODEL") or DEFAULT_MODEL).strip()

    graph_config = {
        "llm": {"api_key": api_key, "model": model},
        "verbose": False,
        "headless": True,
    }
    graph = SmartScraperGraph(prompt=EXTRACTION_PROMPT, source=url, config=graph_config)
    return graph.run()


def _extract_external_id(item: dict[str, Any]) -> str | None:
    for key in ("external_id", "id", "offer_id", "reference"):
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    url = (item.get("offer_url") or item.get("url") or "").strip()
    if url:
        tail = url.rstrip("/").rsplit("/", 1)[-1].strip()
        if tail:
            return tail
    return None


def _normalize_result(raw_result: Any, limit: int) -> list[dict[str, Any]]:
    items: list[Any] = []
    if isinstance(raw_result, list):
        items = raw_result
    elif isinstance(raw_result, dict):
        for key in ("offers", "result", "results", "content", "data"):
            value = raw_result.get(key)
            if isinstance(value, list):
                items = value
                break
        else:
            items = [raw_result] if raw_result else []

    cleaned: list[dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        external_id = _extract_external_id(item)
        if not external_id:
            continue  # never invent a random id for an offer we can't identify
        cleaned.append({**item, "external_id": external_id})
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description="ScrapeGraphAI fallback runner for Business France offers.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    result = _build_result(args.url)
    try:
        raw_result = _run_scrapegraph(args.url, args.limit, args.timeout)
        offers = _normalize_result(raw_result, args.limit)
        result["offers"] = offers
        result["offers_found"] = len(offers)
        result["status"] = "success" if offers else "error"
        if not offers:
            result["error"] = "scrapegraph returned zero usable offers"
    except ImportError as exc:
        result["error"] = f"scrapegraphai not importable in this venv: {exc}"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
