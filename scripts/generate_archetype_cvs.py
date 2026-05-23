from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import math
import re
import sys


WORD_RE = re.compile(r"[a-z0-9]+")


OUTPUT_ROOT = Path("docs") / "ai" / "runtime_calibration" / "archetype_cvs"
REPO_ROOT = Path(__file__).resolve().parents[1]
API_ENV_PATH = REPO_ROOT / "apps" / "api" / ".env"

CENTRAL_SECTORS = {
    "finance_controller": {
        "slug": "finance_control",
        "central_domains": ("finance",),
        "peripheral_domains": ("data", "operations"),
        "keywords": ("budget", "forecast", "controll", "report", "sap", "finance", "cost"),
        "hybrid_evidence_keywords": (
            "budget",
            "budgeting",
            "forecast",
            "forecasting",
            "control",
            "controlling",
            "sap",
            "cost",
        ),
    },
    "hr_recruitment": {
        "slug": "hr_recruitment",
        "central_domains": ("hr",),
        "peripheral_domains": ("operations", "admin"),
        "keywords": ("recruit", "talent", "sourcing", "interview", "hr"),
        "hybrid_evidence_keywords": ("recruit", "recruitment", "talent", "sourcing", "interview"),
    },
    "data_analytics": {
        "slug": "data_analytics",
        "central_domains": ("data",),
        "peripheral_domains": ("finance", "engineering"),
        "keywords": ("sql", "dashboard", "analytics", "data", "bi", "report"),
        "hybrid_evidence_keywords": ("sql", "dashboard", "dashboards", "analytics", "data", "bi"),
    },
    "software_engineering": {
        "slug": "software_engineering",
        "central_domains": ("engineering",),
        "peripheral_domains": ("data", "operations"),
        "keywords": ("software", "developer", "engineering", "python", "java", "api"),
        "hybrid_evidence_keywords": ("software", "developer", "engineering", "python", "java", "api"),
    },
    "operations_process": {
        "slug": "operations_process",
        "central_domains": ("operations",),
        "peripheral_domains": ("supply", "finance"),
        "keywords": ("process", "operations", "lean", "supply", "planning", "logistics"),
        "hybrid_evidence_keywords": ("process", "operations", "lean", "planning", "logistics"),
    },
}

HYBRID_SECTORS = {
    "finance_bi": {
        "slug": "finance_bi",
        "min_offer_count": 10,
        "components": ("finance_controller", "data_analytics"),
    },
    "hr_operations": {
        "slug": "hr_operations",
        "min_offer_count": 10,
        "components": ("hr_recruitment", "operations_process"),
    },
    "data_software": {
        "slug": "data_software",
        "min_offer_count": 10,
        "components": ("data_analytics", "software_engineering"),
    },
    "operations_supply": {
        "slug": "operations_supply",
        "min_offer_count": 10,
        "explicit_sides": (
            {
                "domains": ("operations",),
                "keywords": ("process", "operations", "lean", "planning"),
            },
            {
                "domains": ("supply",),
                "keywords": ("supply", "logistics", "inventory", "procurement"),
            },
        ),
    },
}

ANCHOR_SKILL_ALLOWLIST = (
    "financial analysis",
    "recruitment",
    "sql querying",
    "internal control",
)

TOOL_SKILL_LABELS = (
    "sap",
    "sql",
    "sql querying",
    "python",
    "java",
    "api",
    "dashboards",
)

RENDER_REQUIRED_SECTION_LABELS = (
    "Orientation",
    "Profile Summary",
    "Experience Types",
    "Project Types",
    "Anchor Skills",
    "Support Skills",
    "Generic Skills To Limit",
    "Tools / Technologies",
    "Market Evidence",
)

QUICK_MODE_ROWS = [
    {
        "source": "business_france",
        "external_id": "Q-001",
        "title": "Financial Controller Analyst",
        "description": "budget control monthly reporting project delivery",
        "offer_domain_enrichment": {"domain_tags": ["finance"]},
        "offer_skills": [{"skill_label": "internal control"}, {"skill_label": "sap"}, {"skill_label": "communication"}],
    },
    {
        "source": "business_france",
        "external_id": "Q-002",
        "title": "Financial Controller Lead",
        "description": "budget control monthly reporting project delivery",
        "offer_domain_enrichment": {"domain_tags": ["finance", "operations"]},
        "offer_skills": [{"skill_label": "financial analysis"}, {"skill_label": "sap"}, {"skill_label": "communication"}],
    },
    {
        "source": "business_france",
        "external_id": "Q-003",
        "title": "Financial Controller Manager",
        "description": "project forecasting process improvement",
        "offer_domain_enrichment": {"domain_tags": ["finance", "data"]},
        "offer_skills": [{"skill_label": "communication"}, {"skill_label": "project coordination"}],
    },
    {
        "source": "business_france",
        "external_id": "Q-004",
        "title": "Financial Controller Specialist",
        "description": "budget control project forecasting",
        "offer_domain_enrichment": {"domain_tags": ["finance"]},
        "offer_skills": [{"skill_label": "internal control"}, {"skill_label": "sql querying"}],
    },
]


def _build_output_path(output_root: Path, sector_type: str, sector_slug: str, suffix: str) -> Path:
    if sector_type not in {"central", "hybrid"}:
        raise ValueError(f"unsupported sector_type: {sector_type}")
    if not sector_slug:
        raise ValueError("sector_slug must not be empty")
    return Path(output_root) / sector_type / f"{sector_slug}{suffix}"


def _load_repo_env(env_path: Path | None = None) -> None:
    env_path = env_path or API_ENV_PATH
    if not env_path.exists():
        return
    from dotenv import dotenv_values

    for key, value in dotenv_values(env_path).items():
        if isinstance(value, str) and value and key not in os.environ:
            os.environ[key] = value


def build_markdown_output_path(
    *,
    sector_slug: str,
    output_root: Path = OUTPUT_ROOT,
    sector_type: str = "central",
) -> Path:
    return _build_output_path(output_root, sector_type, sector_slug, ".md")


def build_json_output_path(
    *,
    sector_slug: str,
    output_root: Path = OUTPUT_ROOT,
    sector_type: str = "central",
) -> Path:
    return _build_output_path(output_root, sector_type, sector_slug, ".json")


def _normalize_text(*parts: object) -> str:
    tokens: list[str] = []
    for part in parts:
        if not part:
            continue
        tokens.extend(WORD_RE.findall(str(part).lower()))
    return " ".join(tokens)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _extract_domain_tags(payload: object) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, dict):
        raw_values = []
        domain_tag = payload.get("domain_tag")
        if domain_tag:
            raw_values.append(domain_tag)
        domain_tags = payload.get("domain_tags")
        if isinstance(domain_tags, list):
            raw_values.extend(domain_tags)
        return _dedupe_preserve_order([str(value).strip().lower() for value in raw_values if value])
    if isinstance(payload, list):
        return _dedupe_preserve_order([str(value).strip().lower() for value in payload if value])
    return [str(payload).strip().lower()]


def _extract_skill_fields(payload: object) -> tuple[list[str], list[str]]:
    if not isinstance(payload, list):
        return [], []
    labels: list[str] = []
    uris: list[str] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        label = entry.get("skill_label") or entry.get("label") or entry.get("skill")
        uri = entry.get("skill_uri") or entry.get("uri")
        if label:
            labels.append(str(label).strip().lower())
        if uri:
            uris.append(str(uri).strip())
    return _dedupe_preserve_order(labels), _dedupe_preserve_order(uris)


def normalize_bf_offer_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for row in rows:
        source = str(row.get("source") or "business_france")
        external_id = str(row["external_id"])
        title = str(row.get("title") or "")
        description = str(row.get("description") or "")
        domain_tags = _extract_domain_tags(row.get("offer_domain_enrichment"))
        skill_labels, skill_uris = _extract_skill_fields(row.get("offer_skills"))
        normalized.append(
            {
                "source": source,
                "external_id": external_id,
                "offer_id": f"{source}:{external_id}",
                "title": title,
                "description": description,
                "text": _normalize_text(title, description),
                "domain_tags": domain_tags,
                "skill_labels": skill_labels,
                "skill_uris": skill_uris,
            }
        )
    return normalized


def compute_sector_fit(offer: dict[str, object], sector_key: str) -> dict[str, object]:
    sector = CENTRAL_SECTORS[sector_key]
    domain_tags = set(offer.get("domain_tags", []))
    keywords = sector["keywords"]

    central_domain_hits = sorted(domain_tags.intersection(sector["central_domains"]))
    peripheral_domain_hits = sorted(domain_tags.intersection(sector["peripheral_domains"]))
    matched_keywords = _match_exact_keywords(offer, keywords)

    central_score = len(central_domain_hits) * 6 + len(matched_keywords) * 2
    peripheral_score = len(peripheral_domain_hits) * 4 + len(matched_keywords)

    return {
        "central_score": central_score,
        "peripheral_score": peripheral_score,
        "central_domain_hits": central_domain_hits,
        "peripheral_domain_hits": peripheral_domain_hits,
        "matched_keywords": matched_keywords,
    }


def _build_selection_entry(
    offer: dict[str, object],
    *,
    fit: dict[str, object],
    score: int,
) -> dict[str, object]:
    return {
        "offer": offer,
        "fit": fit,
        "score": score,
    }


def _offer_evidence_tokens(offer: dict[str, object]) -> set[str]:
    tokens = set(str(offer.get("text") or "").split())
    for label in offer.get("skill_labels", []):
        tokens.update(WORD_RE.findall(str(label).lower()))
    return tokens


def _match_exact_keywords(
    offer: dict[str, object],
    keywords: tuple[str, ...],
) -> list[str]:
    offer_tokens = _offer_evidence_tokens(offer)
    return [keyword for keyword in keywords if keyword in offer_tokens]


def _build_hybrid_side_fit(
    offer: dict[str, object],
    *,
    side_key: str,
    domains: tuple[str, ...],
    keywords: tuple[str, ...],
    side_kind: str,
    source_sector_key: str | None = None,
) -> dict[str, object]:
    domain_tags = set(offer.get("domain_tags", []))
    domain_hits = sorted(domain_tags.intersection(domains))
    matched_keywords = _match_exact_keywords(offer, keywords)
    side_fit = {
        "side_key": side_key,
        "side_kind": side_kind,
        "domain_hits": domain_hits,
        "matched_keywords": matched_keywords,
        "score": len(domain_hits) * 6 + len(matched_keywords) * 2,
    }
    if source_sector_key is not None:
        side_fit["source_sector_key"] = source_sector_key
    return side_fit


def select_central_sector_offers(
    offers: list[dict[str, object]],
    *,
    sector_key: str,
    target_count: int,
) -> list[dict[str, object]]:
    central_target = math.floor(target_count * 0.8)
    ranked: list[tuple[int, int, str, dict[str, object], dict[str, object]]] = []
    for offer in offers:
        fit = compute_sector_fit(offer, sector_key)
        if fit["central_score"] <= 0 or not fit["central_domain_hits"]:
            continue
        ranked.append((fit["central_score"], fit["peripheral_score"], str(offer["offer_id"]), offer, fit))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [
        _build_selection_entry(offer, fit=fit, score=central_score)
        for central_score, _, _, offer, fit in ranked[:central_target]
    ]


def select_coherent_peripheral_offers(
    offers: list[dict[str, object]],
    *,
    sector_key: str,
    already_selected_offer_ids: set[str],
    target_count: int,
) -> list[dict[str, object]]:
    central_target = math.floor(target_count * 0.8)
    peripheral_target = max(target_count - central_target, 0)
    ranked: list[tuple[int, int, str, dict[str, object], dict[str, object]]] = []
    for offer in offers:
        offer_id = str(offer["offer_id"])
        if offer_id in already_selected_offer_ids:
            continue
        fit = compute_sector_fit(offer, sector_key)
        if fit["peripheral_score"] <= 0 or not fit["peripheral_domain_hits"]:
            continue
        ranked.append((fit["peripheral_score"], fit["central_score"], offer_id, offer, fit))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [
        _build_selection_entry(offer, fit=fit, score=peripheral_score)
        for peripheral_score, _, _, offer, fit in ranked[:peripheral_target]
    ]


def select_hybrid_sector_offers(
    offers: list[dict[str, object]],
    *,
    sector_key: str,
    target_count: int,
) -> list[dict[str, object]]:
    config = HYBRID_SECTORS[sector_key]
    if len(offers) < config["min_offer_count"]:
        raise ValueError(
            f"hybrid sector {sector_key} requires at least {config['min_offer_count']} offers"
        )

    ranked: list[tuple[int, str, dict[str, object], dict[str, object]]] = []
    for offer in offers:
        side_scores: list[int] = []
        side_fits: list[dict[str, object]] = []
        components = config.get("components", ())
        explicit_sides = config.get("explicit_sides", ())
        if components:
            for component in components:
                sector = CENTRAL_SECTORS[component]
                side_fit = _build_hybrid_side_fit(
                    offer,
                    side_key=component,
                    domains=sector["central_domains"],
                    keywords=sector["hybrid_evidence_keywords"],
                    side_kind="component",
                    source_sector_key=component,
                )
                side_fits.append(side_fit)
                if not side_fit["domain_hits"] or not side_fit["matched_keywords"]:
                    side_scores.append(0)
                    continue
                side_scores.append(side_fit["score"])
        else:
            for index, side in enumerate(explicit_sides, start=1):
                side_fit = _build_hybrid_side_fit(
                    offer,
                    side_key=f"explicit_side_{index}",
                    domains=side["domains"],
                    keywords=side["keywords"],
                    side_kind="explicit",
                )
                side_fits.append(side_fit)
                if not side_fit["domain_hits"] or not side_fit["matched_keywords"]:
                    side_scores.append(0)
                    continue
                side_scores.append(side_fit["score"])
        if len(side_scores) != 2 or any(score <= 0 for score in side_scores):
            continue
        total_score = sum(side_scores)
        ranked.append(
            (
                total_score,
                str(offer["offer_id"]),
                offer,
                {
                    "side_fits": side_fits,
                    "side_scores": side_scores,
                    "total_score": total_score,
                },
            )
        )
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        _build_selection_entry(offer, fit=fit, score=total_score)
        for total_score, _, offer, fit in ranked[:target_count]
    ]


def _extract_offer_from_selection_entry(entry: dict[str, object]) -> dict[str, object]:
    offer = entry.get("offer")
    if isinstance(offer, dict):
        return offer
    return entry


def aggregate_sector_skill_evidence(
    selected_entries: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    sample_offers = [_extract_offer_from_selection_entry(entry) for entry in selected_entries]
    sample_offer_count = len(sample_offers)
    sample_domain_tags = sorted(
        {
            domain_tag
            for offer in sample_offers
            for domain_tag in offer.get("domain_tags", [])
        }
    )
    sample_domain_count = len(sample_domain_tags)

    aggregated: dict[str, dict[str, object]] = {}
    for offer in sample_offers:
        offer_id = str(offer.get("offer_id") or "")
        domain_tags = [str(domain_tag) for domain_tag in offer.get("domain_tags", [])]
        for skill_label in offer.get("skill_labels", []):
            skill = str(skill_label)
            evidence = aggregated.setdefault(
                skill,
                {
                    "skill_label": skill,
                    "offer_ids": set(),
                    "domain_tags": set(),
                    "sample_offer_count": sample_offer_count,
                    "sample_domain_tags": sample_domain_tags,
                    "sample_domain_count": sample_domain_count,
                    "is_allowlisted": skill in ANCHOR_SKILL_ALLOWLIST,
                },
            )
            evidence["offer_ids"].add(offer_id)
            evidence["domain_tags"].update(domain_tags)

    finalized: dict[str, dict[str, object]] = {}
    for skill_label, evidence in aggregated.items():
        offer_ids = sorted(evidence["offer_ids"])
        domain_tags = sorted(evidence["domain_tags"])
        offer_count = len(offer_ids)
        density = offer_count / sample_offer_count if sample_offer_count else 0.0
        domain_dispersion = (
            len(domain_tags) / sample_domain_count if sample_domain_count else 0.0
        )
        finalized[skill_label] = {
            "skill_label": skill_label,
            "offer_count": offer_count,
            "offer_ids": offer_ids,
            "domain_tags": domain_tags,
            "density": density,
            "domain_dispersion": domain_dispersion,
            "evidence_count": offer_count,
            "sample_offer_count": sample_offer_count,
            "sample_domain_tags": sample_domain_tags,
            "is_allowlisted": bool(evidence["is_allowlisted"]),
        }
    return finalized


def classify_sector_skills(
    aggregated_skill_evidence: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    classified: dict[str, dict[str, object]] = {}
    for skill_label, evidence in aggregated_skill_evidence.items():
        offer_count = int(evidence["offer_count"])
        density = float(evidence["density"])
        domain_tags = list(evidence["domain_tags"])
        domain_dispersion = float(evidence["domain_dispersion"])
        is_allowlisted = bool(evidence["is_allowlisted"])

        classification = "SUPPORT"
        if domain_dispersion >= 0.6 and len(domain_tags) > 1:
            classification = "GENERIC"
        elif offer_count > 0 and is_allowlisted:
            classification = "ANCHOR"
        elif density >= 0.6 and len(domain_tags) <= 1:
            classification = "ANCHOR"

        classified[skill_label] = {
            **evidence,
            "classification": classification,
        }
    return classified


def select_promotable_skill_evidence(
    classified_skill_evidence: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    promotable = [
        evidence
        for evidence in classified_skill_evidence.values()
        if evidence["evidence_count"] > 0 and evidence["classification"] in {"ANCHOR", "SUPPORT"}
    ]
    promotable.sort(
        key=lambda evidence: (
            0 if evidence["classification"] == "ANCHOR" else 1,
            -float(evidence["density"]),
            -int(evidence["offer_count"]),
            str(evidence["skill_label"]),
        )
    )
    return promotable


def _tokenize_free_text(text: object) -> list[str]:
    return WORD_RE.findall(str(text).lower())


def _extract_recurrent_terms(
    selected_entries: list[dict[str, object]],
    *,
    field_name: str,
    ngram_size: int,
    top_k: int,
    min_count: int,
) -> list[dict[str, object]]:
    counts: Counter[str] = Counter()
    for entry in selected_entries:
        offer = _extract_offer_from_selection_entry(entry)
        tokens = _tokenize_free_text(offer.get(field_name, ""))
        if len(tokens) < ngram_size:
            continue
        for index in range(len(tokens) - ngram_size + 1):
            phrase = " ".join(tokens[index : index + ngram_size])
            counts[phrase] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        {"label": label, "evidence_count": count}
        for label, count in ranked
        if count >= min_count
    ][:top_k]


def _build_orientation(selected_entries: list[dict[str, object]]) -> dict[str, object]:
    offers = [_extract_offer_from_selection_entry(entry) for entry in selected_entries]
    return {
        "offer_count": len(offers),
        "domain_tags": sorted(
            {
                domain_tag
                for offer in offers
                for domain_tag in offer.get("domain_tags", [])
            }
        ),
    }


def _partition_render_skill_sections(
    classified_skill_evidence: dict[str, dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    sections = {
        "anchor_skills": [],
        "support_skills": [],
        "generic_skills_to_limit": [],
        "tools_technologies": [],
    }
    used_labels: set[str] = set()

    for skill_label in sorted(classified_skill_evidence):
        evidence = classified_skill_evidence[skill_label]
        if evidence["evidence_count"] <= 0:
            continue
        item = {
            "skill_label": skill_label,
            "classification": evidence["classification"],
            "offer_count": evidence["offer_count"],
            "evidence_count": evidence["evidence_count"],
            "domain_tags": evidence["domain_tags"],
        }
        if skill_label in TOOL_SKILL_LABELS:
            sections["tools_technologies"].append(item)
            used_labels.add(skill_label)
            continue
        if skill_label in used_labels:
            continue
        if evidence["classification"] == "ANCHOR":
            sections["anchor_skills"].append(item)
        elif evidence["classification"] == "SUPPORT":
            sections["support_skills"].append(item)
        elif evidence["classification"] == "GENERIC":
            sections["generic_skills_to_limit"].append(item)
        used_labels.add(skill_label)

    return sections


def _ensure_render_evidence(payload: dict[str, object]) -> None:
    if not payload["anchor_skills"]:
        raise ValueError("insufficient evidence: anchor skills missing")
    if not payload["profile_summary"]:
        raise ValueError("insufficient evidence: profile summary missing")
    if not payload["experience_types"]:
        raise ValueError("insufficient evidence: experience types missing")
    if not payload["project_types"]:
        raise ValueError("insufficient evidence: project types missing")
    if payload["market_evidence"]["offer_count"] <= 0:
        raise ValueError("insufficient evidence: market evidence missing")


def _render_markdown_list(items: list[dict[str, object]], key: str = "label") -> list[str]:
    if not items:
        return ["- None"]
    rendered: list[str] = []
    for item in items:
        label = item[key]
        evidence_count = item.get("evidence_count") or item.get("offer_count")
        rendered.append(f"- {label} ({evidence_count})")
    return rendered


def render_archetype_markdown(render_payload: dict[str, object]) -> str:
    lines = [
        f"# {render_payload['sector_slug']}",
        "",
        "## Orientation",
        *[f"- {tag}" for tag in render_payload["orientation"]["domain_tags"]],
        "",
        "## Profile Summary",
        *_render_markdown_list(render_payload["profile_summary"]),
        "",
        "## Experience Types",
        *_render_markdown_list(render_payload["experience_types"]),
        "",
        "## Project Types",
        *_render_markdown_list(render_payload["project_types"]),
        "",
        "## Anchor Skills",
        *_render_markdown_list(render_payload["anchor_skills"], key="skill_label"),
        "",
        "## Support Skills",
        *_render_markdown_list(render_payload["support_skills"], key="skill_label"),
        "",
        "## Generic Skills To Limit",
        *_render_markdown_list(render_payload["generic_skills_to_limit"], key="skill_label"),
        "",
        "## Tools / Technologies",
        *_render_markdown_list(render_payload["tools_technologies"], key="skill_label"),
        "",
        "## Market Evidence",
        f"- offer_count ({render_payload['market_evidence']['offer_count']})",
        *[f"- {offer_id}" for offer_id in render_payload["market_evidence"]["offer_ids"]],
    ]
    return "\n".join(lines)


def build_archetype_render_artifact(
    *,
    sector_slug: str,
    sector_type: str,
    selected_entries: list[dict[str, object]],
    classified_skill_evidence: dict[str, dict[str, object]],
    output_root: Path = OUTPUT_ROOT,
) -> dict[str, object]:
    orientation = _build_orientation(selected_entries)
    profile_summary = _extract_recurrent_terms(
        selected_entries,
        field_name="title",
        ngram_size=1,
        top_k=3,
        min_count=2,
    )
    experience_types = _extract_recurrent_terms(
        selected_entries,
        field_name="title",
        ngram_size=2,
        top_k=3,
        min_count=2,
    )
    project_types = _extract_recurrent_terms(
        selected_entries,
        field_name="description",
        ngram_size=2,
        top_k=3,
        min_count=2,
    )
    skill_sections = _partition_render_skill_sections(classified_skill_evidence)
    market_evidence = {
        "offer_count": orientation["offer_count"],
        "offer_ids": sorted(
            _extract_offer_from_selection_entry(entry)["offer_id"] for entry in selected_entries
        ),
        "domain_tags": orientation["domain_tags"],
    }

    render_payload = {
        "sector_slug": sector_slug,
        "sector_type": sector_type,
        "orientation": orientation,
        "profile_summary": profile_summary,
        "experience_types": experience_types,
        "project_types": project_types,
        "anchor_skills": skill_sections["anchor_skills"],
        "support_skills": skill_sections["support_skills"],
        "generic_skills_to_limit": skill_sections["generic_skills_to_limit"],
        "tools_technologies": skill_sections["tools_technologies"],
        "market_evidence": market_evidence,
    }
    _ensure_render_evidence(render_payload)

    return {
        "markdown_path": build_markdown_output_path(
            sector_slug=sector_slug,
            output_root=output_root,
            sector_type=sector_type,
        ),
        "json_path": build_json_output_path(
            sector_slug=sector_slug,
            output_root=output_root,
            sector_type=sector_type,
        ),
        "markdown": render_archetype_markdown(render_payload),
        "json": render_payload,
    }


def _clean_offers_has_active_column(conn) -> bool:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'clean_offers'
              AND column_name = 'is_active'
            LIMIT 1
            """
        )
        return cursor.fetchone() is not None


def load_business_france_offer_rows_from_postgres(database_url: str) -> list[dict[str, object]]:
    import psycopg

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        active_clause = "AND co.is_active IS TRUE" if _clean_offers_has_active_column(conn) else ""
        sql = f"""
        SELECT
            co.id AS offer_id,
            co.source,
            co.external_id,
            co.title,
            co.description,
            COALESCE(ode.domain_tag, 'other') AS domain_tag,
            os.label AS skill_label
        FROM clean_offers co
        LEFT JOIN offer_domain_enrichment ode
          ON ode.source = co.source AND ode.external_id = co.external_id
        LEFT JOIN offer_skills os
          ON os.offer_id = co.id
        WHERE co.source = %s
          {active_clause}
          AND co.title IS NOT NULL
          AND COALESCE(co.description, '') <> ''
        ORDER BY co.id
        """
        with conn.cursor() as cursor:
            cursor.execute(sql, ("business_france",))
            rows = cursor.fetchall()

    aggregated: dict[str, dict[str, object]] = {}
    for offer_id, source, external_id, title, description, domain_tag, skill_label in rows:
        key = str(offer_id)
        item = aggregated.setdefault(
            key,
            {
                "source": str(source),
                "external_id": str(external_id),
                "title": title or "",
                "description": description or "",
                "offer_domain_enrichment": {"domain_tags": []},
                "offer_skills": [],
            },
        )
        if domain_tag and domain_tag not in item["offer_domain_enrichment"]["domain_tags"]:
            item["offer_domain_enrichment"]["domain_tags"].append(str(domain_tag))
        if skill_label:
            item["offer_skills"].append({"skill_label": str(skill_label).strip().lower()})
    return list(aggregated.values())


def load_quick_mode_offer_rows() -> list[dict[str, object]]:
    return QUICK_MODE_ROWS


def _delete_file_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _write_render_artifact_files(artifact: dict[str, object]) -> None:
    markdown_path = Path(artifact["markdown_path"])
    json_path = Path(artifact["json_path"])
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(str(artifact["markdown"]) + "\n")
    json_path.write_text(json.dumps(artifact["json"], indent=2, sort_keys=True) + "\n")


def _build_central_selected_entries(
    offers: list[dict[str, object]],
    *,
    sector_key: str,
    target_count: int,
) -> list[dict[str, object]]:
    central = select_central_sector_offers(offers, sector_key=sector_key, target_count=target_count)
    peripheral = select_coherent_peripheral_offers(
        offers,
        sector_key=sector_key,
        already_selected_offer_ids={entry["offer"]["offer_id"] for entry in central},
        target_count=target_count,
    )
    return central + peripheral


def _build_classified_skill_evidence(selected_entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return classify_sector_skills(aggregate_sector_skill_evidence(selected_entries))


def _attempt_render_sector(
    *,
    sector_slug: str,
    sector_type: str,
    selected_entries: list[dict[str, object]],
    output_root: Path,
) -> dict[str, object]:
    classified = _build_classified_skill_evidence(selected_entries)
    return build_archetype_render_artifact(
        sector_slug=sector_slug,
        sector_type=sector_type,
        selected_entries=selected_entries,
        classified_skill_evidence=classified,
        output_root=output_root,
    )


def generate_archetype_cvs(
    *,
    rows: list[dict[str, object]],
    output_root: Path = OUTPUT_ROOT,
) -> dict[str, object]:
    offers = normalize_bf_offer_rows(rows)
    output_root = Path(output_root)
    summary = {
        "central_created": [],
        "central_refused": [],
        "hybrid_created": [],
        "hybrid_refused": [],
    }

    for sector_key, config in CENTRAL_SECTORS.items():
        sector_slug = config["slug"]
        markdown_path = build_markdown_output_path(
            sector_slug=sector_slug,
            output_root=output_root,
            sector_type="central",
        )
        json_path = build_json_output_path(
            sector_slug=sector_slug,
            output_root=output_root,
            sector_type="central",
        )
        try:
            selected_entries = _build_central_selected_entries(offers, sector_key=sector_key, target_count=10)
            if not selected_entries:
                raise ValueError("no selected offers")
            artifact = _attempt_render_sector(
                sector_slug=sector_slug,
                sector_type="central",
                selected_entries=selected_entries,
                output_root=output_root,
            )
            _write_render_artifact_files(artifact)
            summary["central_created"].append(sector_slug)
        except ValueError as exc:
            _delete_file_if_exists(markdown_path)
            _delete_file_if_exists(json_path)
            summary["central_refused"].append({"sector": sector_slug, "reason": str(exc)})

    for sector_key, config in HYBRID_SECTORS.items():
        sector_slug = config["slug"]
        markdown_path = build_markdown_output_path(
            sector_slug=sector_slug,
            output_root=output_root,
            sector_type="hybrid",
        )
        json_path = build_json_output_path(
            sector_slug=sector_slug,
            output_root=output_root,
            sector_type="hybrid",
        )
        try:
            selected_entries = select_hybrid_sector_offers(offers, sector_key=sector_key, target_count=10)
            if len(selected_entries) < config["min_offer_count"]:
                raise ValueError(f"requires at least {config['min_offer_count']} evidenced offers")
            artifact = _attempt_render_sector(
                sector_slug=sector_slug,
                sector_type="hybrid",
                selected_entries=selected_entries,
                output_root=output_root,
            )
            _write_render_artifact_files(artifact)
            summary["hybrid_created"].append(sector_slug)
        except ValueError as exc:
            _delete_file_if_exists(markdown_path)
            _delete_file_if_exists(json_path)
            summary["hybrid_refused"].append({"sector": sector_slug, "reason": str(exc)})

    return summary


def _print_generation_summary(summary: dict[str, object]) -> None:
    for slug in summary["central_created"]:
        print(f"central created: {slug}")
    for item in summary["central_refused"]:
        print(f"central refused: {item['sector']} :: {item['reason']}")
    for slug in summary["hybrid_created"]:
        print(f"hybrid created: {slug}")
    for item in summary["hybrid_refused"]:
        print(f"hybrid refused: {item['sector']} :: {item['reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("auto", "pg", "quick"), default="auto")
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    args = parser.parse_args(argv)

    _load_repo_env()
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    mode = args.mode
    if mode == "auto":
        mode = "pg" if database_url else "quick"

    if mode == "pg":
        if not database_url:
            print("ERROR: DATABASE_URL not set", file=sys.stderr)
            return 2
        rows = load_business_france_offer_rows_from_postgres(database_url)
    else:
        rows = load_quick_mode_offer_rows()

    summary = generate_archetype_cvs(rows=rows, output_root=Path(args.output_root))
    _print_generation_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
