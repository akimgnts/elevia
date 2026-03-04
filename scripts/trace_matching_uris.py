#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from api.utils.inbox_catalog import load_catalog_offers  # type: ignore
from api.utils.pdf_text import extract_text_from_pdf  # type: ignore
from compass.domain_uris import build_domain_uris_for_text  # type: ignore
from matching import MatchingEngine  # type: ignore
from matching.extractors import extract_profile  # type: ignore
from profile.baseline_parser import run_baseline  # type: ignore
from profile.profile_cluster import detect_profile_cluster  # type: ignore


def _read_cv(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(data)
    return data.decode("utf-8", errors="ignore")


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _detect_cluster(baseline_result: Dict) -> str | None:
    skills_for_cluster: List[str] = []
    validated_items = baseline_result.get("validated_items") or []
    if validated_items:
        skills_for_cluster = [
            str(item.get("label") or item.get("uri") or "")
            for item in validated_items
            if isinstance(item, dict)
        ]
        skills_for_cluster = [s for s in skills_for_cluster if s]
    if not skills_for_cluster:
        skills_for_cluster = baseline_result.get("skills_canonical") or []
    if not skills_for_cluster:
        skills_for_cluster = baseline_result.get("skills_raw") or []
    cluster = detect_profile_cluster(skills_for_cluster).get("dominant_cluster")
    return cluster or None


def _split_uris(uris: List[str]) -> Tuple[List[str], List[str], List[str]]:
    esco: List[str] = []
    domain: List[str] = []
    other: List[str] = []
    for uri in uris:
        if uri.startswith("http://data.europa.eu/esco/"):
            esco.append(uri)
        elif uri.startswith("compass:skill:"):
            domain.append(uri)
        else:
            other.append(uri)
    return esco, domain, other


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace ESCO + DOMAIN URIs used by matching.")
    parser.add_argument("--cv", required=True, help="Path to CV PDF or TXT")
    parser.add_argument("--offer-id", required=True, help="Offer id to trace")
    args = parser.parse_args()

    cv_path = Path(args.cv)
    if not cv_path.exists():
        print(f"[trace] CV not found: {cv_path}", file=sys.stderr)
        return 2

    cv_text = _read_cv(cv_path)
    baseline = run_baseline(cv_text, profile_id=f"trace-{cv_path.stem}")
    profile = baseline.get("profile") or {}

    cluster = _detect_cluster(baseline)
    cluster_key = cluster.upper() if cluster else None
    esco_labels = baseline.get("validated_labels") or []
    domain_tokens, domain_uris = build_domain_uris_for_text(
        cv_text,
        esco_labels,
        cluster_key,
    )

    if domain_uris:
        profile.setdefault("domain_uris", domain_uris)
        profile.setdefault("domain_uri_count", len(domain_uris))
        profile.setdefault("domain_tokens", domain_tokens)
        combined = _dedupe_preserve_order((profile.get("skills_uri") or []) + domain_uris)
        profile["skills_uri"] = combined

    offers = load_catalog_offers()
    offer = None
    for item in offers:
        if str(item.get("id") or "") == str(args.offer_id):
            offer = item
            break
    if offer is None:
        print(f"[trace] Offer id not found: {args.offer_id}", file=sys.stderr)
        return 3

    offer_uris = offer.get("skills_uri") or []
    offer_domain = offer.get("domain_uris") or []
    if offer_domain:
        offer_uris = _dedupe_preserve_order(list(offer_uris) + list(offer_domain))
        offer["skills_uri"] = offer_uris

    profile_uris = profile.get("skills_uri") or []
    profile_esco, profile_domain, _ = _split_uris(profile_uris)
    offer_esco, offer_domain, _ = _split_uris(offer_uris)

    profile_esco_set = set(profile_esco)
    profile_domain_set = set(profile_domain)
    offer_esco_set = set(offer_esco)
    offer_domain_set = set(offer_domain)

    esco_overlap = len(profile_esco_set & offer_esco_set)
    domain_overlap = len(profile_domain_set & offer_domain_set)
    total_overlap = len(set(profile_uris) & set(offer_uris))

    engine = MatchingEngine([offer])
    extracted = extract_profile(profile)
    result = engine.score_offer(extracted, offer)

    output = {
        "profile": {
            "profile_id": profile.get("id") or profile.get("profile_id"),
            "cluster": cluster_key,
            "esco_uris": profile_esco,
            "domain_uris": profile_domain,
        },
        "offer": {
            "offer_id": offer.get("id") or offer.get("offer_id"),
            "cluster": offer.get("offer_cluster"),
            "esco_uris": offer_esco,
            "domain_uris": offer_domain,
        },
        "intersections": {
            "esco_overlap_count": esco_overlap,
            "domain_overlap_count": domain_overlap,
            "total_overlap_count": total_overlap,
        },
        "score": {
            "total": result.score,
            "breakdown": result.breakdown,
            "skills_debug": (result.match_debug or {}).get("skills"),
        },
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
