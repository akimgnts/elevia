"""
market_insights.py - Read-only aggregated VIE market insights.

No matching, no scoring, no LLM. Pure data aggregation from offers.db.
Cached in-memory for 1 hour (TTL configurable via ELEVIA_INSIGHTS_TTL_S).
"""
from __future__ import annotations

import os
import json
import sqlite3
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.utils.db import DB_PATH
from api.utils.skill_display import display_skill_label
from compass.roles.occupation_signature_filter import LOW_SIGNAL_SEED_IDS
from compass.roles.role_family_map import map_role_family_to_sector
from compass.roles.role_resolver import DISPLAY_CONFIDENCE_THRESHOLD, RoleResolver
from offer.offer_cluster import detect_offer_cluster
from compass.canonical.canonical_store import get_canonical_store

router = APIRouter(prefix="/insights", tags=["insights"])

_CACHE: Dict[str, Any] = {}
_CACHE_TS: float = 0.0
_CACHE_TTL: float = float(os.getenv("ELEVIA_INSIGHTS_TTL_S", "3600"))
_CACHE_LOCK = threading.Lock()
_REFRESH_THREAD: threading.Thread | None = None
_CACHE_FILE = DB_PATH.parent.parent / "cache" / "vie_market_insights.json"

SECTOR_LABELS: Dict[str, str] = {
    "DATA_IT": "Data / IT",
    "FINANCE_LEGAL": "Finance & Légal",
    "SUPPLY_OPS": "Supply & Ops",
    "MARKETING_SALES": "Marketing & Sales",
    "ENGINEERING_INDUSTRY": "Ingénierie",
    "ADMIN_HR": "RH & Admin",
    "OTHER": "Autres",
}

# Skills too generic to surface (case-insensitive match on label)
_SKILL_NOISE = frozenset({
    # Languages
    "anglais", "english", "français", "french", "espagnol", "spanish",
    "allemand", "mandarin", "portugais",
    # Office / admin tools
    "microsoft office", "pack office", "ms office", "office", "word",
    "powerpoint", "excel", "utiliser un logiciel de tableur",
    # Pure soft / meta (too ubiquitous to be signal)
    "communication", "communiquer", "conseiller d'autres personnes",
    "conseiller d’autres personnes", "service administratif", "service clients",
    # VIE noise
    "vie", "vié", "permis b", "permis de conduire",
    # Off-topic items
    "boissons alcoolisées", "alcool", "wine", "beer", "vin", "bière",
    "boisson", "boissons", "spiritueux",
    # Too generic / weak for public dashboarding
    "informatique", "planifier", "physique", "arabe", "chinois", "less",
})
_MIN_SECTOR_SKILL_COUNT = 2

_COMPANY_SUFFIXES = {
    "sa", "sas", "sasu", "sarl", "gmbh", "inc", "ltd", "llc", "plc", "bv", "ag",
    "spa", "srl", "pte", "co", "corp", "groupe", "group",
}

_TOP_ROLE_LIMIT = 5
_TOP_ROLE_SKILL_LIMIT = 3
_TOP_ROLE_FALLBACK_CONFIDENCE = 0.50


def _clean_skill(label: str) -> str:
    raw = (label or "").strip().lower()
    if not raw:
        return ""
    cleaned = (
        raw.replace("’", "'")
        .replace("/", " ")
        .replace("|", " ")
        .replace(";", " ")
        .replace(",", " ")
    )
    cleaned = " ".join(cleaned.split())
    cleaned = cleaned.strip("- ")
    return cleaned


def _normalize_company(name: str) -> str:
    base = (name or "").strip().lower()
    base = base.replace("&", " ")
    base = base.replace(".", " ")
    base = base.replace(",", " ")
    parts = [p for p in base.split() if p]
    while parts and parts[-1] in _COMPANY_SUFFIXES:
        parts.pop()
    base = " ".join(parts)
    base = "".join(ch for ch in base if ch.isalnum())
    return base


def _cluster_company_names(raw_names: List[str]) -> Dict[str, str]:
    import difflib

    normalized = {raw: _normalize_company(raw) for raw in raw_names}
    clusters: Dict[str, str] = {}
    canonical_keys: List[str] = []
    for raw in sorted(raw_names):
        key = normalized[raw]
        if not key:
            clusters[raw] = raw.strip()
            continue
        matched = None
        for canon in canonical_keys:
            if key == canon:
                matched = canon
                break
            if len(key) >= 6 and len(canon) >= 6 and (key.startswith(canon) or canon.startswith(key)):
                matched = canon
                break
            if difflib.SequenceMatcher(None, key, canon).ratio() >= 0.88:
                matched = canon
                break
        if matched is None:
            canonical_keys.append(key)
            matched = key
        clusters[raw] = matched
    buckets: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for raw, key in clusters.items():
        buckets[key][raw] += 1
    display: Dict[str, str] = {}
    for key, variants in buckets.items():
        display[key] = sorted(variants.items(), key=lambda x: (-x[1], len(x[0])))[0][0]
    return {raw: display[key] for raw, key in clusters.items()}


def _normalize_market_skill(
    *,
    store,
    raw_skill: str,
    skill_uri: str | None,
) -> tuple[str, str] | None:
    if skill_uri and store.is_loaded():
        entry = store.id_to_skill.get(skill_uri)
        if entry:
            label = str(entry.get("label") or raw_skill or "").strip()
            if not label:
                return None
            cleaned = _clean_skill(label)
            if not cleaned:
                return None
            if skill_uri in LOW_SIGNAL_SEED_IDS:
                return None
            skill_type = str(entry.get("skill_type") or "").strip().lower()
            cluster_name = str(entry.get("cluster_name") or "").strip().upper()
            if skill_type == "generic" or cluster_name == "GENERIC_TRANSVERSAL":
                return None
            return skill_uri, display_skill_label(label)

    cleaned = _clean_skill(raw_skill)
    if not cleaned or cleaned in _SKILL_NOISE:
        return None
    return f"label:{cleaned}", display_skill_label(cleaned)


def _aggregate_market_skills(
    *,
    conn: sqlite3.Connection,
    store,
    offer_cluster_map: Dict[str, str],
) -> tuple[
    Dict[str, int],
    Dict[str, str],
    Dict[str, Dict[str, int]],
    Dict[str, List[str]],
    Dict[str, List[str]],
]:
    skill_freq: Dict[str, int] = defaultdict(int)
    skill_labels: Dict[str, str] = {}
    skill_sector_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    resolver_skills_by_offer: Dict[str, List[str]] = defaultdict(list)
    display_skills_by_offer: Dict[str, List[str]] = defaultdict(list)
    seen_by_offer: Dict[str, set[str]] = defaultdict(set)

    for row in conn.execute(
        "SELECT offer_id, skill, skill_uri FROM fact_offer_skills WHERE skill IS NOT NULL"
    ):
        offer_id = str(row["offer_id"])
        raw_skill = str(row["skill"] or "")
        skill_uri = row["skill_uri"]
        resolver_skills_by_offer[offer_id].append(skill_uri or raw_skill)

        normalized = _normalize_market_skill(store=store, raw_skill=raw_skill, skill_uri=skill_uri)
        if not normalized:
            continue
        skill_key, display_label = normalized
        if skill_key in seen_by_offer[offer_id]:
            continue
        seen_by_offer[offer_id].add(skill_key)

        skill_freq[skill_key] += 1
        skill_labels.setdefault(skill_key, display_label)
        if offer_id in offer_cluster_map:
            skill_sector_counts[skill_key][offer_cluster_map[offer_id]] += 1
        display_skills_by_offer[offer_id].append(display_label)

    for offer_id, labels in list(display_skills_by_offer.items()):
        display_skills_by_offer[offer_id] = sorted(set(labels))

    return (
        skill_freq,
        skill_labels,
        skill_sector_counts,
        resolver_skills_by_offer,
        display_skills_by_offer,
    )


def _aggregate_market_skills_fast(
    *,
    conn: sqlite3.Connection,
    offer_cluster_map: Dict[str, str],
) -> tuple[
    Dict[str, int],
    Dict[str, str],
    Dict[str, Dict[str, int]],
    Dict[str, List[str]],
]:
    skill_freq: Dict[str, int] = defaultdict(int)
    skill_labels: Dict[str, str] = {}
    skill_sector_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    display_skills_by_offer: Dict[str, List[str]] = defaultdict(list)
    seen_by_offer: Dict[str, set[str]] = defaultdict(set)

    for row in conn.execute("SELECT offer_id, skill FROM fact_offer_skills WHERE skill IS NOT NULL"):
        offer_id = str(row["offer_id"])
        cleaned = _clean_skill(str(row["skill"] or ""))
        if not cleaned or cleaned in _SKILL_NOISE:
            continue
        skill_key = f"label:{cleaned}"
        if skill_key in seen_by_offer[offer_id]:
            continue
        seen_by_offer[offer_id].add(skill_key)
        display_label = display_skill_label(cleaned)
        skill_freq[skill_key] += 1
        skill_labels.setdefault(skill_key, display_label)
        if offer_id in offer_cluster_map:
            skill_sector_counts[skill_key][offer_cluster_map[offer_id]] += 1
        display_skills_by_offer[offer_id].append(display_label)

    for offer_id, labels in list(display_skills_by_offer.items()):
        display_skills_by_offer[offer_id] = sorted(set(labels))

    return skill_freq, skill_labels, skill_sector_counts, display_skills_by_offer


def _count_role_supported_skills(
    *,
    resolved_offer_roles: List[Dict[str, Any]],
    display_skills_by_offer: Dict[str, List[str]],
) -> Dict[str, int]:
    supported_counts: Dict[str, int] = defaultdict(int)
    for row in resolved_offer_roles:
        if float(row.get("confidence") or 0.0) < DISPLAY_CONFIDENCE_THRESHOLD:
            continue
        for skill_label in sorted(set(display_skills_by_offer.get(str(row["offer_id"]), []))):
            supported_counts[skill_label] += 1
    return supported_counts


def _resolve_offer_roles(
    *,
    offer_rows: List[sqlite3.Row],
    offer_cluster_map: Dict[str, str],
    resolver_skills_by_offer: Dict[str, List[str]],
    display_skills_by_offer: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    role_resolver = RoleResolver()
    resolved: List[Dict[str, Any]] = []
    for row in offer_rows:
        offer_id = str(row["id"])
        result = role_resolver.resolve_role_for_offer(
            {
                "title": row["title"] or "",
                "description": row["description"] or "",
                "skills_canonical": resolver_skills_by_offer.get(offer_id, []),
            }
        )
        confidence = float(result.get("occupation_confidence") or 0.0)
        candidate = next(iter(result.get("candidate_occupations") or []), None)
        role_label = str((candidate or {}).get("occupation_title") or "").strip()
        if not role_label:
            continue
        role_family = str((candidate or {}).get("role_family") or "")
        role_sector = map_role_family_to_sector(role_family) if role_family else "OTHER"
        resolved.append(
            {
                "offer_id": offer_id,
                "offer_sector": offer_cluster_map.get(offer_id, "OTHER"),
                "role": role_label,
                "role_family": role_family,
                "role_sector": role_sector,
                "confidence": confidence,
                "skills": list(display_skills_by_offer.get(offer_id, [])),
            }
        )
    return resolved


def _rank_roles(
    role_rows: List[Dict[str, Any]],
    *,
    mode: str,
) -> List[Dict[str, Any]]:
    role_counts: Dict[str, int] = defaultdict(int)
    role_skill_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in role_rows:
        role_label = str(row["role"])
        role_counts[role_label] += 1
        for skill_label in sorted(set(row.get("skills") or [])):
            role_skill_counts[role_label][skill_label] += 1

    ranked_roles = sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))[:_TOP_ROLE_LIMIT]
    top_roles: List[Dict[str, Any]] = []
    for role_label, count in ranked_roles:
        ranked_skills = sorted(
            role_skill_counts.get(role_label, {}).items(),
            key=lambda item: (-item[1], item[0]),
        )[:_TOP_ROLE_SKILL_LIMIT]
        top_roles.append(
            {
                "role": role_label,
                "count": count,
                "skills": [label for label, _ in ranked_skills],
                "mode": mode,
            }
        )
    return top_roles


def _compute_top_roles(
    *,
    resolved_offer_roles: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    strict_global = [row for row in resolved_offer_roles if row["confidence"] >= DISPLAY_CONFIDENCE_THRESHOLD]
    fallback_global = [row for row in resolved_offer_roles if row["confidence"] >= _TOP_ROLE_FALLBACK_CONFIDENCE]
    top_roles = _rank_roles(strict_global or fallback_global, mode="high_confidence" if strict_global else "fallback")

    sectors = sorted({str(row["offer_sector"] or "OTHER") for row in resolved_offer_roles})
    sector_top_roles: List[Dict[str, Any]] = []
    for sector in sectors:
        sector_rows = [row for row in resolved_offer_roles if row["offer_sector"] == sector]
        aligned_strict = [
            row
            for row in sector_rows
            if row["confidence"] >= DISPLAY_CONFIDENCE_THRESHOLD and row["role_sector"] == sector
        ]
        any_strict = [row for row in sector_rows if row["confidence"] >= DISPLAY_CONFIDENCE_THRESHOLD]
        aligned_fallback = [
            row
            for row in sector_rows
            if row["confidence"] >= _TOP_ROLE_FALLBACK_CONFIDENCE and row["role_sector"] == sector
        ]
        any_fallback = [row for row in sector_rows if row["confidence"] >= _TOP_ROLE_FALLBACK_CONFIDENCE]

        chosen_rows: List[Dict[str, Any]] = []
        chosen_mode = "empty"
        if aligned_strict:
            chosen_rows = aligned_strict
            chosen_mode = "aligned_high_confidence"
        elif any_strict:
            chosen_rows = any_strict
            chosen_mode = "high_confidence"
        elif aligned_fallback:
            chosen_rows = aligned_fallback
            chosen_mode = "aligned_fallback"
        elif any_fallback:
            chosen_rows = any_fallback
            chosen_mode = "fallback"

        for item in _rank_roles(chosen_rows, mode=chosen_mode):
            sector_top_roles.append({"sector": sector, **item})
    return top_roles, sector_top_roles


def _compute() -> Dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        store = get_canonical_store()

        def _resolve_skill_label(skill: str, skill_uri: str | None) -> str:
            if skill_uri and store.is_loaded():
                entry = store.id_to_skill.get(skill_uri)
                if entry and isinstance(entry.get("label"), str):
                    return entry["label"]
            return skill

        # ── Total offers ─────────────────────────────────────────────────
        total_offers: int = conn.execute(
            "SELECT COUNT(*) FROM fact_offers"
        ).fetchone()[0]

        # ── Countries ────────────────────────────────────────────────────
        country_rows = conn.execute(
            """
            SELECT country, COUNT(*) AS cnt
            FROM fact_offers
            WHERE country IS NOT NULL AND trim(country) != ''
            GROUP BY country
            ORDER BY cnt DESC
            """
        ).fetchall()
        country_counts: List[Dict] = [
            {"country": r["country"], "count": r["cnt"]} for r in country_rows
        ]
        top_countries: List[Dict] = country_counts[:12]
        total_countries: int = conn.execute(
            "SELECT COUNT(DISTINCT country) FROM fact_offers WHERE country IS NOT NULL"
        ).fetchone()[0]

        # ── Cluster classification ────────────────────────────────────────
        offer_rows = conn.execute(
            "SELECT id, title, description FROM fact_offers"
        ).fetchall()

        skill_by_offer: Dict[str, List[str]] = defaultdict(list)
        for row in conn.execute(
            "SELECT offer_id, skill, skill_uri FROM fact_offer_skills WHERE skill IS NOT NULL"
        ):
            label = _resolve_skill_label(row["skill"], row["skill_uri"])
            skill_by_offer[row["offer_id"]].append(label)

        sector_counts: Dict[str, int] = defaultdict(int)
        offer_cluster_map: Dict[str, str] = {}
        for row in offer_rows:
            cluster, _, _ = detect_offer_cluster(
                row["title"],
                row["description"],
                skill_by_offer.get(row["id"], []),
            )
            sector_counts[cluster] += 1
            offer_cluster_map[row["id"]] = cluster

        sectors_distribution = sorted(
            [
                {"sector": s, "label": SECTOR_LABELS.get(s, s), "count": c}
                for s, c in sector_counts.items()
            ],
            key=lambda x: -x["count"],
        )

        # ── Skills (canonical-first, deduped per offer, deterministic) ───
        (
            skill_freq,
            skill_labels,
            skill_sector_counts,
            resolver_skills_by_offer,
            display_skills_by_offer,
        ) = _aggregate_market_skills(
            conn=conn,
            store=store,
            offer_cluster_map=offer_cluster_map,
        )
        resolved_offer_roles = _resolve_offer_roles(
            offer_rows=offer_rows,
            offer_cluster_map=offer_cluster_map,
            resolver_skills_by_offer=resolver_skills_by_offer,
            display_skills_by_offer=display_skills_by_offer,
        )
        role_supported_skill_counts = _count_role_supported_skills(
            resolved_offer_roles=resolved_offer_roles,
            display_skills_by_offer=display_skills_by_offer,
        )

        total_skills = len(skill_freq)
        total_skill_occurrences: int = sum(skill_freq.values()) or 1

        clean_skills = sorted(
            skill_freq.items(),
            key=lambda x: (
                -x[1],
                -role_supported_skill_counts.get(skill_labels.get(x[0], x[0]), 0),
                skill_labels.get(x[0], x[0]),
            ),
        )

        sector_skill_totals: Dict[str, int] = defaultdict(int)
        for sk, smap in skill_sector_counts.items():
            for sector, count in smap.items():
                sector_skill_totals[sector] += count

        top_skills: List[Dict] = []
        for skill_key, count in clean_skills[:12]:
            smap = skill_sector_counts.get(skill_key, {})
            dominant = max(smap, key=smap.get) if smap else "OTHER"
            top_skills.append({
                "skill": skill_labels.get(skill_key, skill_key),
                "count": count,
                "dominant_sector": dominant,
                "display_label": skill_labels.get(skill_key, skill_key),
                "role_supported_count": role_supported_skill_counts.get(skill_labels.get(skill_key, skill_key), 0),
            })

        # ── Sector × Country matrix (full) ───────────────────────────────
        country_by_offer: Dict[str, str] = {}
        for row in conn.execute(
            "SELECT id, country FROM fact_offers WHERE country IS NOT NULL AND trim(country) != ''"
        ):
            country_by_offer[row["id"]] = row["country"]

        sector_country_raw: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for offer_id, cluster in offer_cluster_map.items():
            country = country_by_offer.get(offer_id)
            if country:
                sector_country_raw[cluster][country] += 1

        sector_country_counts: List[Dict] = []
        for sector, country_map in sector_country_raw.items():
            for country, count in country_map.items():
                sector_country_counts.append(
                    {"sector": sector, "country": country, "count": count}
                )

        sector_country_matrix = sorted(
            sector_country_counts, key=lambda x: (x["sector"], -x["count"])
        )[:160]

        # ── Sector × Company matrix ───────────────────────────────────────
        company_by_offer: Dict[str, str] = {}
        for row in conn.execute(
            "SELECT id, company FROM fact_offers WHERE company IS NOT NULL AND trim(company) != ''"
        ):
            company_by_offer[row["id"]] = row["company"]
        company_normalized = _cluster_company_names(list(company_by_offer.values()))

        sector_company_raw: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for offer_id, cluster in offer_cluster_map.items():
            company = company_by_offer.get(offer_id)
            if company:
                sector_company_raw[cluster][company_normalized.get(company, company)] += 1

        sector_company_counts: List[Dict] = []
        for sector, company_map in sector_company_raw.items():
            for company, count in company_map.items():
                sector_company_counts.append(
                    {"sector": sector, "company": company, "count": count}
                )

        sector_companies = sorted(
            sector_company_counts, key=lambda x: (x["sector"], -x["count"])
        )[:160]

        company_counts_map: Dict[str, int] = defaultdict(int)
        for company in company_by_offer.values():
            company_counts_map[company_normalized.get(company, company)] += 1
        company_counts = [
            {"company": k, "count": v}
            for k, v in sorted(company_counts_map.items(), key=lambda x: (-x[1], x[0]))
        ]

        # ── Heatmap: sector × skill ───────────────────────────────────────
        top_skill_labels = {s["skill"] for s in top_skills}
        matrix_raw: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for skill_key, smap in skill_sector_counts.items():
            display_label = skill_labels.get(skill_key, skill_key)
            if display_label not in top_skill_labels:
                continue
            for sector, count in smap.items():
                matrix_raw[sector][display_label] += count

        sector_skill_matrix: List[Dict] = []
        for sector, skill_map in matrix_raw.items():
            total = max(sector_counts.get(sector, 1), 1)
            for skill, count in skill_map.items():
                sector_skill_matrix.append(
                    {
                        "sector": sector,
                        "skill": skill,
                        "count": count,
                        "relative": round(count / total, 3),
                    }
                )

        # ── Sector skill distinctiveness ────────────────────────────────
        sector_distinctive_skills: List[Dict] = []
        for skill_key, smap in skill_sector_counts.items():
            display_label = skill_labels.get(skill_key, skill_key)
            skill_lc = display_label.lower().strip()
            if skill_lc in _SKILL_NOISE or len(display_label) < 2:
                continue
            global_count = skill_freq.get(skill_key, 0)
            if global_count <= 0:
                continue
            global_share = global_count / total_skill_occurrences
            for sector, count in smap.items():
                if count < _MIN_SECTOR_SKILL_COUNT:
                    continue
                sector_total = sector_skill_totals.get(sector, 0)
                if sector_total <= 0:
                    continue
                sector_share = count / sector_total
                distinctiveness = sector_share / global_share if global_share else 0.0
                sector_distinctive_skills.append(
                    {
                        "sector": sector,
                        "skill": display_label,
                        "count": count,
                        "sector_share": round(sector_share, 4),
                        "global_share": round(global_share, 6),
                        "distinctiveness": round(distinctiveness, 4),
                        "display_label": display_label,
                    }
                )
        sector_distinctive_skills.sort(
            key=lambda x: (x["sector"], -x["distinctiveness"], -x["count"], x["skill"])
        )

        # ── Key insights ──────────────────────────────────────────────────
        top3_names = ", ".join(c["country"] for c in top_countries[:3])
        top3_count = sum(c["count"] for c in top_countries[:3])
        pct_top3 = round(top3_count / total_offers * 100) if total_offers else 0

        s0 = sectors_distribution[0]["label"] if sectors_distribution else ""
        s1 = sectors_distribution[1]["label"] if len(sectors_distribution) > 1 else ""
        pct_top2 = round(
            sum(s["count"] for s in sectors_distribution[:2]) / total_offers * 100
        ) if total_offers else 0

        top_skill_name = top_skills[0]["skill"] if top_skills else ""

        key_insights = [
            f"Les opportunités VIE se concentrent sur {top3_names} — {pct_top3}% du corpus.",
            f"{s0} et {s1} dominent avec {pct_top2}% du volume total des offres.",
            f"'{top_skill_name}' est la compétence la plus demandée, présente dans plusieurs secteurs.",
        ]
        top_roles, sector_top_roles = _compute_top_roles(
            resolved_offer_roles=resolved_offer_roles,
        )

    finally:
        conn.close()

    return {
        "total_offers": total_offers,
        "total_countries": total_countries,
        "total_sectors": len([s for s in sector_counts if s != "OTHER"]),
        "total_skills": total_skills,
        "country_counts": country_counts,
        "top_countries": top_countries[:10],
        "sectors_distribution": sectors_distribution,
        "top_skills": top_skills,
        "sector_skill_matrix": sector_skill_matrix,
        "sector_distinctive_skills": sector_distinctive_skills,
        "sector_country_matrix": sector_country_matrix,
        "sector_country_counts": sector_country_counts,
        "sector_companies": sector_companies,
        "sector_company_counts": sector_company_counts,
        "company_counts": company_counts,
        "key_insights": key_insights,
        "top_roles": top_roles,
        "sector_top_roles": sector_top_roles,
    }


def _compute_lightweight() -> Dict[str, Any]:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        total_offers: int = conn.execute("SELECT COUNT(*) FROM fact_offers").fetchone()[0]

        country_rows = conn.execute(
            """
            SELECT country, COUNT(*) AS cnt
            FROM fact_offers
            WHERE country IS NOT NULL AND trim(country) != ''
            GROUP BY country
            ORDER BY cnt DESC
            """
        ).fetchall()
        country_counts: List[Dict[str, Any]] = [{"country": r["country"], "count": r["cnt"]} for r in country_rows]
        top_countries = country_counts[:12]
        total_countries: int = conn.execute(
            "SELECT COUNT(DISTINCT country) FROM fact_offers WHERE country IS NOT NULL"
        ).fetchone()[0]

        offer_rows = conn.execute("SELECT id, title, description FROM fact_offers").fetchall()

        skill_by_offer: Dict[str, List[str]] = defaultdict(list)
        for row in conn.execute("SELECT offer_id, skill FROM fact_offer_skills WHERE skill IS NOT NULL"):
            label = str(row["skill"] or "").strip()
            if label:
                skill_by_offer[str(row["offer_id"])].append(label)

        sector_counts: Dict[str, int] = defaultdict(int)
        offer_cluster_map: Dict[str, str] = {}
        for row in offer_rows:
            cluster, _, _ = detect_offer_cluster(
                row["title"],
                row["description"],
                skill_by_offer.get(row["id"], []),
            )
            sector_counts[cluster] += 1
            offer_cluster_map[row["id"]] = cluster

        sectors_distribution = sorted(
            [{"sector": s, "label": SECTOR_LABELS.get(s, s), "count": c} for s, c in sector_counts.items()],
            key=lambda x: -x["count"],
        )

        skill_freq, skill_labels, skill_sector_counts, _display_skills_by_offer = _aggregate_market_skills_fast(
            conn=conn,
            offer_cluster_map=offer_cluster_map,
        )
        total_skills = len(skill_freq)
        total_skill_occurrences: int = sum(skill_freq.values()) or 1
        clean_skills = sorted(skill_freq.items(), key=lambda x: (-x[1], skill_labels.get(x[0], x[0])))

        sector_skill_totals: Dict[str, int] = defaultdict(int)
        for _skill_key, sector_map in skill_sector_counts.items():
            for sector, count in sector_map.items():
                sector_skill_totals[sector] += count

        top_skills: List[Dict[str, Any]] = []
        for skill_key, count in clean_skills[:12]:
            smap = skill_sector_counts.get(skill_key, {})
            dominant = max(smap, key=smap.get) if smap else "OTHER"
            label = skill_labels.get(skill_key, skill_key)
            top_skills.append(
                {
                    "skill": label,
                    "count": count,
                    "dominant_sector": dominant,
                    "display_label": label,
                    "role_supported_count": 0,
                }
            )

        country_by_offer: Dict[str, str] = {}
        for row in conn.execute("SELECT id, country FROM fact_offers WHERE country IS NOT NULL AND trim(country) != ''"):
            country_by_offer[row["id"]] = row["country"]

        sector_country_raw: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for offer_id, cluster in offer_cluster_map.items():
            country = country_by_offer.get(offer_id)
            if country:
                sector_country_raw[cluster][country] += 1

        sector_country_counts: List[Dict[str, Any]] = []
        for sector, country_map in sector_country_raw.items():
            for country, count in country_map.items():
                sector_country_counts.append({"sector": sector, "country": country, "count": count})
        sector_country_matrix = sorted(sector_country_counts, key=lambda x: (x["sector"], -x["count"]))[:160]

        company_by_offer: Dict[str, str] = {}
        for row in conn.execute("SELECT id, company FROM fact_offers WHERE company IS NOT NULL AND trim(company) != ''"):
            company_by_offer[row["id"]] = row["company"]
        company_normalized = _cluster_company_names(list(company_by_offer.values()))

        sector_company_raw: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for offer_id, cluster in offer_cluster_map.items():
            company = company_by_offer.get(offer_id)
            if company:
                sector_company_raw[cluster][company_normalized.get(company, company)] += 1

        sector_company_counts: List[Dict[str, Any]] = []
        for sector, company_map in sector_company_raw.items():
            for company, count in company_map.items():
                sector_company_counts.append({"sector": sector, "company": company, "count": count})
        sector_companies = sorted(sector_company_counts, key=lambda x: (x["sector"], -x["count"]))[:160]

        company_counts_map: Dict[str, int] = defaultdict(int)
        for company in company_by_offer.values():
            company_counts_map[company_normalized.get(company, company)] += 1
        company_counts = [
            {"company": k, "count": v}
            for k, v in sorted(company_counts_map.items(), key=lambda x: (-x[1], x[0]))
        ]

        top_skill_labels = {s["skill"] for s in top_skills}
        matrix_raw: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for skill_key, smap in skill_sector_counts.items():
            display_label = skill_labels.get(skill_key, skill_key)
            if display_label not in top_skill_labels:
                continue
            for sector, count in smap.items():
                matrix_raw[sector][display_label] += count

        sector_skill_matrix: List[Dict[str, Any]] = []
        for sector, skill_map in matrix_raw.items():
            total = max(sector_counts.get(sector, 1), 1)
            for skill, count in skill_map.items():
                sector_skill_matrix.append(
                    {"sector": sector, "skill": skill, "count": count, "relative": round(count / total, 3)}
                )

        sector_distinctive_skills: List[Dict[str, Any]] = []
        for skill_key, smap in skill_sector_counts.items():
            display_label = skill_labels.get(skill_key, skill_key)
            global_count = skill_freq.get(skill_key, 0)
            if global_count <= 0:
                continue
            global_share = global_count / total_skill_occurrences
            for sector, count in smap.items():
                if count < _MIN_SECTOR_SKILL_COUNT:
                    continue
                sector_total = sector_skill_totals.get(sector, 0)
                if sector_total <= 0:
                    continue
                sector_share = count / sector_total
                distinctiveness = sector_share / global_share if global_share else 0.0
                sector_distinctive_skills.append(
                    {
                        "sector": sector,
                        "skill": display_label,
                        "count": count,
                        "sector_share": round(sector_share, 4),
                        "global_share": round(global_share, 6),
                        "distinctiveness": round(distinctiveness, 4),
                        "display_label": display_label,
                    }
                )
        sector_distinctive_skills.sort(key=lambda x: (x["sector"], -x["distinctiveness"], -x["count"], x["skill"]))

        top3_names = ", ".join(c["country"] for c in top_countries[:3])
        top3_count = sum(c["count"] for c in top_countries[:3])
        pct_top3 = round(top3_count / total_offers * 100) if total_offers else 0
        s0 = sectors_distribution[0]["label"] if sectors_distribution else ""
        s1 = sectors_distribution[1]["label"] if len(sectors_distribution) > 1 else ""
        pct_top2 = round(sum(s["count"] for s in sectors_distribution[:2]) / total_offers * 100) if total_offers else 0
        top_skill_name = top_skills[0]["skill"] if top_skills else ""
        key_insights = [
            f"Les opportunités VIE se concentrent sur {top3_names} — {pct_top3}% du corpus.",
            f"{s0} et {s1} dominent avec {pct_top2}% du volume total des offres.",
            f"'{top_skill_name}' est la compétence la plus demandée, présente dans plusieurs secteurs.",
        ]

    finally:
        conn.close()

    return {
        "total_offers": total_offers,
        "total_countries": total_countries,
        "total_sectors": len([s for s in sector_counts if s != "OTHER"]),
        "total_skills": total_skills,
        "country_counts": country_counts,
        "top_countries": top_countries[:10],
        "sectors_distribution": sectors_distribution,
        "top_skills": top_skills,
        "sector_skill_matrix": sector_skill_matrix,
        "sector_distinctive_skills": sector_distinctive_skills,
        "sector_country_matrix": sector_country_matrix,
        "sector_country_counts": sector_country_counts,
        "sector_companies": sector_companies,
        "sector_company_counts": sector_company_counts,
        "company_counts": company_counts,
        "key_insights": key_insights,
        "top_roles": [],
        "sector_top_roles": [],
    }


def _write_disk_cache(payload: Dict[str, Any]) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _CACHE_FILE.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(
            {
                "generated_at": time.time(),
                "payload": payload,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    tmp_path.replace(_CACHE_FILE)


def _load_disk_cache() -> tuple[Dict[str, Any] | None, float | None]:
    if not _CACHE_FILE.exists():
        return None, None
    try:
        raw = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        payload = raw.get("payload") if isinstance(raw, dict) else None
        generated_at = float(raw.get("generated_at") or _CACHE_FILE.stat().st_mtime) if isinstance(raw, dict) else _CACHE_FILE.stat().st_mtime
        if not isinstance(payload, dict):
            return None, None
        return payload, max(0.0, time.time() - generated_at)
    except Exception:
        return None, None


def _compute_and_store() -> Dict[str, Any]:
    payload = _compute()
    with _CACHE_LOCK:
        global _CACHE, _CACHE_TS
        _CACHE = payload
        _CACHE_TS = time.monotonic()
    _write_disk_cache(payload)
    return payload


def _refresh_cache_background() -> None:
    global _REFRESH_THREAD
    if _REFRESH_THREAD is not None and _REFRESH_THREAD.is_alive():
        return

    def _runner() -> None:
        try:
            _compute_and_store()
        except Exception:
            return

    _REFRESH_THREAD = threading.Thread(target=_runner, name="market-insights-refresh", daemon=True)
    _REFRESH_THREAD.start()


def _get_cached_market_insights() -> Dict[str, Any]:
    global _CACHE, _CACHE_TS
    now = time.monotonic()
    with _CACHE_LOCK:
        if _CACHE and (now - _CACHE_TS) <= _CACHE_TTL:
            return _CACHE

    disk_payload, disk_age_s = _load_disk_cache()
    if disk_payload:
        with _CACHE_LOCK:
            _CACHE = disk_payload
            if disk_age_s is not None and disk_age_s <= _CACHE_TTL:
                _CACHE_TS = now
            else:
                _CACHE_TS = 0.0
        if disk_age_s is not None and disk_age_s > _CACHE_TTL:
            _refresh_cache_background()
        return disk_payload

    payload = _compute_lightweight()
    with _CACHE_LOCK:
        _CACHE = payload
        _CACHE_TS = now
    _write_disk_cache(payload)
    _refresh_cache_background()
    return payload


@router.get("/vie-market")
def get_vie_market_insights() -> JSONResponse:
    """Aggregated VIE market insights — read-only, cached 1 h."""
    return JSONResponse(_get_cached_market_insights())


@router.get("/top-roles")
def get_market_insight_top_roles() -> JSONResponse:
    payload = _get_cached_market_insights()
    return JSONResponse({"top_roles": payload.get("top_roles", [])})
