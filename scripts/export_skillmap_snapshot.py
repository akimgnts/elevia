from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPORT_ROOT = REPO_ROOT / "exports" / "skillmap"
API_ENV_PATH = REPO_ROOT / "apps" / "api" / ".env"
EXPORT_VERSION = "v1"
EXPORT_SOURCE = "skillmap_snapshot"
MAX_OFFERS = 400
MAX_SKILLS = 150
TOP_RELATED_SKILLS = 10
TOP_SAMPLE_OFFERS = 5
TOP_LIST_ITEMS = 12
TOP_WORKFLOWS = 5
TOP_WEBHOOKS = 24
TOP_INSIGHTS = 8

GENERIC_SKILL_LABELS = {
    "communication",
    "project management",
    "excel",
    "documentation",
    "compliance",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_repo_env(env_path: Path | None = None) -> None:
    env_path = env_path or API_ENV_PATH
    if not env_path.exists():
        return
    from dotenv import dotenv_values

    for key, value in dotenv_values(env_path).items():
        if isinstance(value, str) and value and key not in os.environ:
            os.environ[key] = value


def build_export_metadata(
    *,
    source: str,
    version: str,
    total_source_rows: int,
    exported_rows: int,
) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "source": source,
        "version": version,
        "total_source_rows": int(total_source_rows),
        "exported_rows": int(exported_rows),
    }


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _normalize_skill_label(label: str) -> str:
    return " ".join(str(label or "").strip().lower().split())


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _domain_sort_key(item: tuple[str, int]) -> tuple[int, str]:
    domain, count = item
    return (-count, domain)


def load_skillmap_source_rows(database_url: str) -> list[dict[str, Any]]:
    import psycopg

    sql = """
    SELECT
        co.id AS offer_id,
        co.external_id,
        co.title,
        co.company,
        co.country,
        co.contract_type,
        co.publication_date,
        co.source,
        co.description,
        ode.domain_tag,
        ode.confidence AS domain_confidence,
        os.canonical_id,
        os.label AS skill_label,
        os.importance_level,
        os.confidence AS skill_confidence
    FROM clean_offers co
    LEFT JOIN offer_domain_enrichment ode
      ON ode.source = co.source
     AND ode.external_id = co.external_id
    LEFT JOIN offer_skills os
      ON os.offer_id = co.id
    WHERE co.source = %s
      AND co.is_active IS TRUE
      AND co.title IS NOT NULL
      AND COALESCE(co.title, '') <> ''
    ORDER BY co.publication_date DESC NULLS LAST, co.id DESC, os.importance_level ASC NULLS LAST, os.label ASC NULLS LAST
    """
    with psycopg.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, ("business_france",))
            rows = cursor.fetchall()

    aggregated: dict[str, dict[str, Any]] = {}
    for (
        offer_id,
        external_id,
        title,
        company,
        country,
        contract_type,
        publication_date,
        source,
        description,
        domain_tag,
        domain_confidence,
        canonical_id,
        skill_label,
        importance_level,
        skill_confidence,
    ) in rows:
        key = str(offer_id)
        item = aggregated.setdefault(
            key,
            {
                "offer_id": key,
                "external_id": str(external_id or "").strip(),
                "title": _normalize_text(str(title or "")),
                "company": _normalize_text(str(company or "")),
                "country": _normalize_text(str(country or "")),
                "contract_type": _normalize_text(str(contract_type or "")),
                "published_at": publication_date.isoformat() if publication_date else None,
                "source": str(source or ""),
                "description": _normalize_text(str(description or "")),
                "domain": str(domain_tag or "other").strip() or "other",
                "domain_confidence": float(domain_confidence) if domain_confidence is not None else None,
                "skills": [],
                "skill_records": [],
            },
        )
        if canonical_id and skill_label:
            normalized_label = _normalize_skill_label(str(skill_label))
            if normalized_label:
                item["skill_records"].append(
                    {
                        "canonical_id": str(canonical_id),
                        "label": normalized_label,
                        "importance_level": str(importance_level or "").strip(),
                        "confidence": float(skill_confidence) if skill_confidence is not None else None,
                    }
                )
    for item in aggregated.values():
        item["skills"] = _dedupe_preserve_order([record["label"] for record in item["skill_records"]])
    return list(aggregated.values())


def build_offer_export_item(offer: dict[str, Any]) -> dict[str, Any]:
    skills = _dedupe_preserve_order([str(skill) for skill in offer.get("skills", []) if str(skill or "").strip()])
    return {
        "offer_id": str(offer.get("offer_id") or ""),
        "external_id": str(offer.get("external_id") or ""),
        "title": str(offer.get("title") or "").strip(),
        "company": str(offer.get("company") or "").strip(),
        "country": str(offer.get("country") or "").strip(),
        "domain": str(offer.get("domain") or "").strip(),
        "domain_confidence": offer.get("domain_confidence"),
        "contract_type": str(offer.get("contract_type") or "").strip(),
        "top_skills": skills[:8],
        "skill_count": len(skills),
        "published_at": offer.get("published_at"),
        "source": str(offer.get("source") or "").strip(),
    }


def build_offers_export(
    offers: list[dict[str, Any]],
    *,
    max_offers: int,
) -> list[dict[str, Any]]:
    ranked = sorted(
        offers,
        key=lambda item: (
            -len(item.get("skills", [])),
            item.get("domain") == "other",
            item.get("published_at") or "",
            item.get("offer_id") or "",
        ),
        reverse=False,
    )
    ranked = sorted(
        ranked,
        key=lambda item: (
            len(item.get("skills", [])),
            0 if item.get("domain") != "other" else 1,
            item.get("published_at") or "",
            item.get("offer_id") or "",
        ),
        reverse=True,
    )
    return [build_offer_export_item(offer) for offer in ranked[:max_offers]]


def build_skills_export(
    offers: list[dict[str, Any]],
    *,
    max_skills: int,
    generic_skill_labels: set[str] | None = None,
) -> list[dict[str, Any]]:
    generic_skill_labels = {str(label).strip().lower() for label in (generic_skill_labels or set())}
    skill_counts: Counter[str] = Counter()
    skill_domains: dict[str, set[str]] = defaultdict(set)
    skill_titles: dict[str, Counter[str]] = defaultdict(Counter)
    skill_companies: dict[str, Counter[str]] = defaultdict(Counter)
    skill_samples: dict[str, list[dict[str, str]]] = defaultdict(list)
    pair_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for offer in offers:
        raw_skill_values = offer.get("skills") or offer.get("top_skills") or []
        raw_skills = [_normalize_skill_label(skill) for skill in raw_skill_values]
        skills = _dedupe_preserve_order([skill for skill in raw_skills if skill])
        domain = str(offer.get("domain") or "").strip()
        title = str(offer.get("title") or "").strip()
        company = str(offer.get("company") or "").strip()
        for skill in skills:
            skill_counts[skill] += 1
            if domain:
                skill_domains[skill].add(domain)
            if title:
                skill_titles[skill][title] += 1
            if company:
                skill_companies[skill][company] += 1
            if len(skill_samples[skill]) < TOP_SAMPLE_OFFERS:
                skill_samples[skill].append(
                    {
                        "offer_id": str(offer.get("offer_id") or ""),
                        "title": title,
                        "company": company,
                        "domain": domain,
                    }
                )
        filtered_for_pairs = [skill for skill in skills if skill not in generic_skill_labels and skill_counts[skill] >= 0]
        for idx, left in enumerate(filtered_for_pairs):
            for right in filtered_for_pairs[idx + 1 :]:
                pair_counts[left][right] += 1
                pair_counts[right][left] += 1

    items: list[dict[str, Any]] = []
    for skill, frequency in skill_counts.most_common(max_skills):
        related = [
            {"label": label, "count": count}
            for label, count in pair_counts.get(skill, Counter()).most_common(TOP_RELATED_SKILLS)
            if label not in generic_skill_labels
        ]
        items.append(
            {
                "skill_id": skill.replace(" ", "_"),
                "label": skill,
                "frequency": frequency,
                "domains": sorted(skill_domains.get(skill, set())),
                "top_titles": [label for label, _ in skill_titles.get(skill, Counter()).most_common(5)],
                "top_companies": [label for label, _ in skill_companies.get(skill, Counter()).most_common(5)],
                "related_skills": related,
                "sample_offers": skill_samples.get(skill, [])[:TOP_SAMPLE_OFFERS],
            }
        )
    return items


def build_overview_export(offers: list[dict[str, Any]], skills: list[dict[str, Any]]) -> dict[str, Any]:
    domains = Counter(str(item.get("domain") or "") for item in offers if str(item.get("domain") or "").strip())
    countries = Counter(str(item.get("country") or "") for item in offers if str(item.get("country") or "").strip())
    titles = Counter(str(item.get("title") or "") for item in offers if str(item.get("title") or "").strip())
    companies = Counter(str(item.get("company") or "") for item in offers if str(item.get("company") or "").strip())
    return {
        "source_summary": {"source": "business_france_snapshot"},
        "totals": {
            "offers": len(offers),
            "skills": len(skills),
            "domains": len(domains),
            "countries": len(countries),
        },
        "top_domains": [{"domain": domain, "count": count} for domain, count in sorted(domains.items(), key=_domain_sort_key)[:TOP_LIST_ITEMS]],
        "top_skills": [
            {"label": item["label"], "frequency": item["frequency"]}
            for item in skills[:TOP_LIST_ITEMS]
        ],
        "top_countries": [{"country": country, "count": count} for country, count in countries.most_common(TOP_LIST_ITEMS)],
        "top_titles": [{"title": title, "count": count} for title, count in titles.most_common(TOP_LIST_ITEMS)],
        "top_companies": [{"company": company, "count": count} for company, count in companies.most_common(TOP_LIST_ITEMS)],
    }


def build_workflows_export(
    *,
    offers: list[dict[str, Any]],
    domains: list[str],
    top_skills: list[str],
) -> list[dict[str, Any]]:
    workflows = [
        ("wf-offer-ingestion", "Offer Ingestion Pipeline", "ingestion", "healthy"),
        ("wf-skill-enrichment", "Skill Enrichment Pipeline", "enrichment", "healthy"),
        ("wf-domain-classification", "Domain Classification Pipeline", "classification", "degraded"),
        ("wf-market-report", "Market Report Generator", "reporting", "healthy"),
        ("wf-webhook-sync", "Webhook Sync Notion Slack n8n", "sync", "healthy"),
    ]
    offer_ids = [str(offer.get("offer_id") or "") for offer in offers[:6] if str(offer.get("offer_id") or "").strip()]
    items: list[dict[str, Any]] = []
    for idx, (workflow_id, name, workflow_type, status) in enumerate(workflows[:TOP_WORKFLOWS]):
        domain = domains[idx % len(domains)] if domains else "other"
        skill = top_skills[idx % len(top_skills)] if top_skills else "unknown"
        items.append(
            {
                "workflow_id": workflow_id,
                "name": name,
                "type": workflow_type,
                "status": status,
                "trigger": "scheduled" if idx < 4 else "webhook",
                "input_domains": [domain],
                "input_skills": [skill],
                "throughput_estimate": max(len(offers) - idx * 17, 24),
                "last_run_at": _utc_now_iso(),
                "success_rate": round(0.99 - idx * 0.03, 2),
                "linked_entities": {"offers": offer_ids[:3], "skills": [skill]},
                "synthetic": True,
                "evidence_refs": {
                    "domains": [domain],
                    "skills": [skill],
                    "offers": offer_ids[:3],
                },
            }
        )
    return items


def build_webhook_events_export(
    *,
    offers: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources = ["slack", "notion", "n8n", "github"]
    statuses = ["delivered", "delivered", "delivered", "retrying", "failed"]
    items: list[dict[str, Any]] = []
    for idx in range(min(TOP_WEBHOOKS, max(len(offers), 1))):
        offer = offers[idx % len(offers)] if offers else {}
        workflow = workflows[idx % len(workflows)] if workflows else {}
        source = sources[idx % len(sources)]
        status = statuses[idx % len(statuses)]
        items.append(
            {
                "event_id": f"evt-{idx + 1:04d}",
                "source": source,
                "status": status,
                "event_type": "offer.snapshot.updated" if idx % 2 == 0 else "skill.graph.refreshed",
                "related_workflow_id": workflow.get("workflow_id"),
                "domain": offer.get("domain"),
                "skill_refs": list(offer.get("top_skills", []))[:2],
                "offer_refs": [offer.get("offer_id")] if offer.get("offer_id") else [],
                "created_at": _utc_now_iso(),
                "latency_ms": 120 + (idx * 37),
                "synthetic": True,
                "evidence_refs": {
                    "domains": [offer.get("domain")] if offer.get("domain") else [],
                    "skills": list(offer.get("top_skills", []))[:2],
                    "offers": [offer.get("offer_id")] if offer.get("offer_id") else [],
                },
            }
        )
    return items


def build_insights_export(
    *,
    overview: dict[str, Any],
    skills: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
) -> dict[str, Any]:
    top_domain = overview.get("top_domains", [{}])[0]
    top_skill = skills[0] if skills else {}
    second_skill = skills[1] if len(skills) > 1 else {}
    highlights = [
        {
            "insight_id": "ins-001",
            "title": f"{top_domain.get('domain', 'other').title()} remains the highest-pressure domain",
            "summary": f"{top_domain.get('count', 0)} offers currently cluster in this domain.",
            "synthetic": True,
            "evidence_refs": {"domains": [top_domain.get('domain')], "skills": [], "offers": []},
        },
        {
            "insight_id": "ins-002",
            "title": f"{top_skill.get('label', 'unknown')} is the strongest recurring automation signal",
            "summary": f"Observed in {top_skill.get('frequency', 0)} exported offers.",
            "synthetic": True,
            "evidence_refs": {"domains": top_skill.get("domains", []), "skills": [top_skill.get("label")], "offers": []},
        },
    ]
    automation_opportunities = [
        {
            "title": "Automate domain drift review for high-volume skills",
            "workflow_ref": workflows[2]["workflow_id"] if len(workflows) > 2 else None,
            "synthetic": True,
            "evidence_refs": {"skills": [top_skill.get("label"), second_skill.get("label")], "domains": top_skill.get("domains", [])},
        },
        {
            "title": "Publish weekly market enrichment digest to Slack/Notion",
            "workflow_ref": workflows[-1]["workflow_id"] if workflows else None,
            "synthetic": True,
            "evidence_refs": {"skills": [], "domains": [top_domain.get("domain")]},
        },
    ]
    return {
        "highlights": highlights[:TOP_INSIGHTS],
        "emerging_skill_clusters": [
            {
                "label": item["label"],
                "domains": item["domains"],
                "frequency": item["frequency"],
                "synthetic": True,
                "evidence_refs": {"skills": [item["label"]], "domains": item["domains"]},
            }
            for item in skills[: min(6, len(skills))]
        ],
        "domain_pressure_signals": [
            {
                "domain": domain["domain"],
                "count": domain["count"],
                "synthetic": True,
                "evidence_refs": {"domains": [domain["domain"]]},
            }
            for domain in overview.get("top_domains", [])[:6]
        ],
        "automation_opportunities": automation_opportunities,
        "market_anomalies": [
            {
                "title": "High recurrence of cross-domain management vocabulary",
                "summary": "Generic orchestration skills still dominate several adjacent domains.",
                "synthetic": True,
                "evidence_refs": {"skills": [top_skill.get("label")], "domains": [top_domain.get("domain")]},
            }
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_skillmap_snapshot(database_url: str) -> dict[str, Any]:
    source_rows = load_skillmap_source_rows(database_url)
    offers = build_offers_export(source_rows, max_offers=MAX_OFFERS)
    skills = build_skills_export(offers, max_skills=MAX_SKILLS, generic_skill_labels=GENERIC_SKILL_LABELS)
    overview = build_overview_export(offers, skills)
    domains = [item["domain"] for item in overview["top_domains"]]
    top_skill_labels = [item["label"] for item in skills[:TOP_LIST_ITEMS]]
    workflows = build_workflows_export(offers=offers, domains=domains, top_skills=top_skill_labels)
    webhook_events = build_webhook_events_export(offers=offers, workflows=workflows)
    insights = build_insights_export(overview=overview, skills=skills, workflows=workflows)

    files = {
        "overview": EXPORT_ROOT / "overview.json",
        "skills": EXPORT_ROOT / "skills.json",
        "offers": EXPORT_ROOT / "offers.json",
        "workflows": EXPORT_ROOT / "workflows.json",
        "webhook-events": EXPORT_ROOT / "webhook-events.json",
        "insights": EXPORT_ROOT / "insights.json",
    }

    overview_payload = {
        "export_metadata": build_export_metadata(
            source=EXPORT_SOURCE,
            version=EXPORT_VERSION,
            total_source_rows=len(source_rows),
            exported_rows=len(offers),
        ),
        **overview,
    }
    skills_payload = {
        "export_metadata": build_export_metadata(
            source=EXPORT_SOURCE,
            version=EXPORT_VERSION,
            total_source_rows=len(source_rows),
            exported_rows=len(skills),
        ),
        "items": skills,
    }
    offers_payload = {
        "export_metadata": build_export_metadata(
            source=EXPORT_SOURCE,
            version=EXPORT_VERSION,
            total_source_rows=len(source_rows),
            exported_rows=len(offers),
        ),
        "items": offers,
    }
    workflows_payload = {
        "export_metadata": build_export_metadata(
            source=EXPORT_SOURCE,
            version=EXPORT_VERSION,
            total_source_rows=len(source_rows),
            exported_rows=len(workflows),
        ),
        "items": workflows,
    }
    webhook_payload = {
        "export_metadata": build_export_metadata(
            source=EXPORT_SOURCE,
            version=EXPORT_VERSION,
            total_source_rows=len(source_rows),
            exported_rows=len(webhook_events),
        ),
        "items": webhook_events,
    }
    insights_payload = {
        "export_metadata": build_export_metadata(
            source=EXPORT_SOURCE,
            version=EXPORT_VERSION,
            total_source_rows=len(source_rows),
            exported_rows=sum(len(items) for items in insights.values() if isinstance(items, list)),
        ),
        **insights,
    }

    _write_json(files["overview"], overview_payload)
    _write_json(files["skills"], skills_payload)
    _write_json(files["offers"], offers_payload)
    _write_json(files["workflows"], workflows_payload)
    _write_json(files["webhook-events"], webhook_payload)
    _write_json(files["insights"], insights_payload)

    return {
        "offers_exported": len(offers),
        "skills_exported": len(skills),
        "domains_detected": len(overview["top_domains"]),
        "workflows_generated": len(workflows),
        "webhooks_generated": len(webhook_events),
        "insights_generated": sum(len(items) for items in insights.values() if isinstance(items, list)),
        "files": {name: str(path) for name, path in files.items()},
    }


def main() -> int:
    _load_repo_env()
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL not set")

    result = export_skillmap_snapshot(database_url)
    print("SkillMap snapshot export complete")
    print(f"- offers exported: {result['offers_exported']}")
    print(f"- skills exported: {result['skills_exported']}")
    print(f"- domains detected: {result['domains_detected']}")
    print(f"- workflows generated: {result['workflows_generated']}")
    print(f"- webhooks generated: {result['webhooks_generated']}")
    print(f"- insights generated: {result['insights_generated']}")
    for name, path in result["files"].items():
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
