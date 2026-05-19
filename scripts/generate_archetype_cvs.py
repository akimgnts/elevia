from __future__ import annotations

from pathlib import Path
import math
import re


WORD_RE = re.compile(r"[a-z0-9]+")


OUTPUT_ROOT = Path("exports") / "archetype_cvs"

CENTRAL_SECTORS = {
    "finance_controller": {
        "slug": "finance_control",
        "central_domains": ("finance",),
        "peripheral_domains": ("data", "operations"),
        "keywords": ("budget", "forecast", "controll", "report", "sap", "finance", "cost"),
        "hybrid_evidence_keywords": ("budget", "forecast", "controll", "sap", "cost"),
    },
    "hr_recruitment": {
        "slug": "hr_recruitment",
        "central_domains": ("hr",),
        "peripheral_domains": ("operations", "admin"),
        "keywords": ("recruit", "talent", "sourcing", "interview", "hr"),
        "hybrid_evidence_keywords": ("recruit", "talent", "sourcing", "interview"),
    },
    "data_analytics": {
        "slug": "data_analytics",
        "central_domains": ("data",),
        "peripheral_domains": ("finance", "engineering"),
        "keywords": ("sql", "dashboard", "analytics", "data", "bi", "report"),
        "hybrid_evidence_keywords": ("sql", "dashboard", "analytics", "data", "bi"),
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


def _build_output_path(output_root: Path, sector_type: str, sector_slug: str, suffix: str) -> Path:
    if sector_type not in {"central", "hybrid"}:
        raise ValueError(f"unsupported sector_type: {sector_type}")
    if not sector_slug:
        raise ValueError("sector_slug must not be empty")
    return Path(output_root) / sector_type / f"{sector_slug}{suffix}"


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
    skill_labels = offer.get("skill_labels", [])
    text = str(offer.get("text") or "")
    keywords = sector["keywords"]

    central_domain_hits = sorted(domain_tags.intersection(sector["central_domains"]))
    peripheral_domain_hits = sorted(domain_tags.intersection(sector["peripheral_domains"]))

    matched_keywords: list[str] = []
    for keyword in keywords:
        in_skill = any(keyword in label for label in skill_labels)
        in_text = keyword in text
        if in_skill or in_text:
            matched_keywords.append(keyword)

    central_score = len(central_domain_hits) * 6 + len(matched_keywords) * 2
    peripheral_score = len(peripheral_domain_hits) * 4 + len(matched_keywords)

    return {
        "central_score": central_score,
        "peripheral_score": peripheral_score,
        "central_domain_hits": central_domain_hits,
        "peripheral_domain_hits": peripheral_domain_hits,
        "matched_keywords": matched_keywords,
    }


def _compute_explicit_hybrid_side_fit(
    offer: dict[str, object],
    side_config: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    domain_tags = set(offer.get("domain_tags", []))
    skill_labels = offer.get("skill_labels", [])
    text = str(offer.get("text") or "")

    domain_hits = sorted(domain_tags.intersection(side_config["domains"]))
    matched_keywords: list[str] = []
    for keyword in side_config["keywords"]:
        in_skill = any(keyword in label for label in skill_labels)
        in_text = keyword in text
        if in_skill or in_text:
            matched_keywords.append(keyword)

    score = len(domain_hits) * 6 + len(matched_keywords) * 2
    return {
        "score": score,
        "domain_hits": domain_hits,
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


def _has_component_hybrid_evidence(fit: dict[str, object], sector_key: str) -> bool:
    hybrid_keywords = set(CENTRAL_SECTORS[sector_key]["hybrid_evidence_keywords"])
    return bool(hybrid_keywords.intersection(fit["matched_keywords"]))


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
                fit = compute_sector_fit(offer, component)
                side_fits.append(
                    {
                        "sector_key": component,
                        **fit,
                    }
                )
                if not fit["central_domain_hits"] or not _has_component_hybrid_evidence(fit, component):
                    side_scores.append(0)
                    continue
                side_scores.append(fit["central_score"] + fit["peripheral_score"])
        else:
            for side in explicit_sides:
                fit = _compute_explicit_hybrid_side_fit(offer, side)
                side_fits.append(fit)
                if not fit["domain_hits"] or not fit["matched_keywords"]:
                    side_scores.append(0)
                    continue
                side_scores.append(fit["score"])
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
