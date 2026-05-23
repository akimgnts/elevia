#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))
_venv_site_packages = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))


BUSINESS_FRANCE_SOURCE = "business_france"
DOMAIN_ORDER = [
    "data",
    "finance",
    "sales",
    "marketing",
    "hr",
    "supply",
    "operations",
    "engineering",
    "legal",
    "admin",
    "other",
]
GENERIC_SIGNALS = [
    "reporting",
    "analysis",
    "communication",
    "management",
    "sql",
    "excel",
    "kpi",
]
STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "will", "into", "your", "you",
    "des", "les", "une", "dans", "pour", "avec", "sur", "aux", "par", "and", "our", "their",
    "nous", "vous", "elle", "ils", "elles", "plus", "moins", "over", "under", "role", "mission",
    "poste", "missions", "support", "analyst", "analysis", "reporting", "business", "data",
    "team", "work", "working", "responsible", "responsibilities", "experience", "offre", "offer",
}
TOOL_PATTERNS = [
    "sap", "salesforce", "hubspot", "power bi", "tableau", "looker", "looker studio",
    "excel", "sql", "python", "postgresql", "mysql", "snowflake", "bigquery", "airflow",
    "dbt", "spark", "databricks", "aws", "azure", "gcp", "docker", "kubernetes", "linux",
    "jira", "servicenow", "workday", "successfactors", "mailchimp", "wordpress", "canva",
    "figma", "terraform", "gitlab", "github", "powerpoint", "crm",
]
EMERGING_PATTERNS = {
    "Finance Ops": ("finance", ("sap", "excel", "reporting", "process", "control")),
    "Sales Ops": ("sales", ("crm", "salesforce", "reporting", "kpi", "forecast")),
    "RevOps": (None, ("crm", "hubspot", "salesforce", "revenue", "forecast")),
    "HR Operations": ("hr", ("hris", "successfactors", "onboarding", "reporting", "process")),
    "Supply Analytics": ("supply", ("forecast", "inventory", "stock", "excel", "analysis")),
    "Marketing Ops": ("marketing", ("campaign", "automation", "dashboard", "reporting", "analytics")),
    "Project Operations": ("operations", ("project", "pmo", "governance", "process", "reporting")),
    "Backend Automation": ("engineering", ("backend", "api", "automation", "docker", "kubernetes")),
    "Cybersecurity": ("engineering", ("security", "cyber", "iam", "soc", "network")),
    "Compliance": (None, ("compliance", "regulatory", "audit", "governance", "ifrs")),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    return re.findall(r"[a-z0-9][a-z0-9\+\-_/\.]{1,}", normalized)


def _contains(text: str, term: str) -> bool:
    normalized = _normalize_text(term)
    if not normalized:
        return False
    if " " in normalized:
        return normalized in text
    return re.search(rf"\b{re.escape(normalized)}\b", text) is not None


def _connect_db():
    import psycopg

    load_dotenv(REPO_ROOT / "apps" / "api" / ".env")
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL not set in environment or apps/api/.env")
    return psycopg.connect(database_url, connect_timeout=15)


def _fetch_one_value(conn, sql: str, params: tuple[Any, ...] = ()) -> Any:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


def _table_exists(conn, table_name: str) -> bool:
    return bool(_fetch_one_value(conn, "SELECT to_regclass(%s)", (f"public.{table_name}",)))


def _fetch_all_dicts(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [col.name for col in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def load_quick_rows() -> list[dict[str, Any]]:
    rows = []
    domain_map = {
        "Data Analyst VIE - KPI & Reporting": "data",
        "Business Intelligence Analyst VIE - Tableau": "data",
        "Data Ops Analyst VIE - Normalisation": "data",
        "Analytics Engineer VIE - API & BI": "data",
        "Reporting Analyst VIE - Power BI": "data",
        "Business Analyst VIE - Operations": "operations",
        "Data Reporting Analyst VIE - CRM": "sales",
        "Data Ops VIE - Inventory": "supply",
        "Product Ops Analyst VIE - Metrics": "operations",
        "Supply Analyst VIE - Forecasting": "supply",
        "ML Engineer VIE - Deep Learning": "engineering",
        "Backend Engineer VIE - Golang": "engineering",
        "DevOps Engineer VIE - Cloud": "engineering",
        "Quant Researcher VIE - Finance": "finance",
        "Fullstack Engineer VIE - React/Node": "engineering",
    }
    payload = json.loads((REPO_ROOT / "apps" / "api" / "fixtures" / "offers" / "vie_catalog.json").read_text(encoding="utf-8"))
    for item in payload:
        rows.append(
            {
                "external_id": item["id"],
                "title": item["title"],
                "company": item.get("company"),
                "country": item.get("country"),
                "description": item.get("description", ""),
                "domain_tag": domain_map.get(item["title"], "other"),
                "confidence": 0.9,
                "method": "fixture",
                "evidence": item.get("skills", []),
                "skill_labels": item.get("skills", []),
            }
        )
    return rows


def load_postgres_rows() -> tuple[list[dict[str, Any]], dict[str, bool]]:
    with _connect_db() as conn:
        has_offer_domain_enrichment = _table_exists(conn, "offer_domain_enrichment")
        has_offer_skills = _table_exists(conn, "offer_skills")
        has_fact_offer_skills = _table_exists(conn, "fact_offer_skills")

        skills_sql = """
            SELECT source, external_id, label AS skill_label
            FROM offer_skills
            WHERE source = %s
        """
        fact_skills_sql = """
            SELECT co.source, co.external_id, fos.skill AS skill_label
            FROM fact_offer_skills fos
            JOIN clean_offers co
              ON co.id = fos.offer_id
            WHERE co.source = %s
        """

        skill_rows: list[dict[str, Any]] = []
        if has_offer_skills:
            skill_rows = _fetch_all_dicts(conn, skills_sql, (BUSINESS_FRANCE_SOURCE,))
        elif has_fact_offer_skills:
            skill_rows = _fetch_all_dicts(conn, fact_skills_sql, (BUSINESS_FRANCE_SOURCE,))

        skill_map: dict[tuple[str, str], list[str]] = defaultdict(list)
        for row in skill_rows:
            key = (str(row["source"]), str(row["external_id"]))
            label = str(row.get("skill_label") or "").strip()
            if label:
                skill_map[key].append(label)

        if has_offer_domain_enrichment:
            rows = _fetch_all_dicts(
                conn,
                """
                SELECT
                  co.source,
                  co.external_id,
                  co.title,
                  co.company,
                  co.country,
                  co.description,
                  ode.domain_tag,
                  ode.confidence,
                  ode.method,
                  ode.evidence
                FROM clean_offers co
                JOIN offer_domain_enrichment ode
                  ON ode.source = co.source
                 AND ode.external_id = co.external_id
                WHERE co.source = %s
                  AND COALESCE(co.is_active, TRUE) = TRUE
                ORDER BY co.external_id
                """,
                (BUSINESS_FRANCE_SOURCE,),
            )
        else:
            rows = _fetch_all_dicts(
                conn,
                """
                SELECT
                  co.source,
                  co.external_id,
                  co.title,
                  co.company,
                  co.country,
                  co.description,
                  'other' AS domain_tag,
                  0.0 AS confidence,
                  'missing_domain_enrichment' AS method,
                  '[]'::jsonb AS evidence
                FROM clean_offers co
                WHERE co.source = %s
                  AND COALESCE(co.is_active, TRUE) = TRUE
                ORDER BY co.external_id
                """,
                (BUSINESS_FRANCE_SOURCE,),
            )

        for row in rows:
            key = (str(row["source"]), str(row["external_id"]))
            evidence = row.get("evidence")
            if isinstance(evidence, str):
                try:
                    evidence = json.loads(evidence)
                except Exception:
                    evidence = [evidence]
            row["evidence"] = evidence if isinstance(evidence, list) else []
            row["skill_labels"] = skill_map.get(key, [])

        return rows, {
            "offer_domain_enrichment": has_offer_domain_enrichment,
            "offer_skills": has_offer_skills,
            "fact_offer_skills": has_fact_offer_skills,
        }


def _aggregate_domain_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row.get("domain_tag") or "other") for row in rows)
    total = sum(counts.values()) or 1
    distribution = []
    for domain in DOMAIN_ORDER:
        n = counts.get(domain, 0)
        distribution.append({"domain": domain, "offer_count": n, "pct": round((n * 100.0) / total, 2)})
    return distribution


def _top_titles(rows: list[dict[str, Any]], domain: str, limit: int = 10) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    original: dict[str, str] = {}
    for row in rows:
        if str(row.get("domain_tag")) != domain:
            continue
        title = str(row.get("title") or "").strip()
        key = _normalize_text(title)
        if not key:
            continue
        counts[key] += 1
        original.setdefault(key, title)
    return [{"title": original[key], "count": count} for key, count in counts.most_common(limit)]


def _top_skills(rows: list[dict[str, Any]], domain: str, limit: int = 15) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows:
        if str(row.get("domain_tag")) != domain:
            continue
        for skill in row.get("skill_labels", []):
            label = _normalize_text(skill)
            if label:
                counts[label] += 1
    return [{"skill": skill, "count": count} for skill, count in counts.most_common(limit)]


def _top_tools(rows: list[dict[str, Any]], domain: str, limit: int = 12) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows:
        if str(row.get("domain_tag")) != domain:
            continue
        text = _normalize_text(" ".join([
            str(row.get("title") or ""),
            str(row.get("description") or ""),
            " ".join(row.get("skill_labels", [])),
        ]))
        for tool in TOOL_PATTERNS:
            if _contains(text, tool):
                counts[tool] += 1
    return [{"tool": tool, "count": count} for tool, count in counts.most_common(limit)]


def _top_context_keywords(rows: list[dict[str, Any]], domain: str, limit: int = 15) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rows:
        if str(row.get("domain_tag")) != domain:
            continue
        tokens = _tokenize(" ".join([
            str(row.get("title") or ""),
            str(row.get("description") or ""),
            " ".join(row.get("evidence", [])),
        ]))
        for token in tokens:
            if token in STOPWORDS or token in GENERIC_SIGNALS:
                continue
            if len(token) < 4:
                continue
            counts[token] += 1
    return [{"keyword": token, "count": count} for token, count in counts.most_common(limit)]


def _representative_examples(rows: list[dict[str, Any]], domain: str, limit: int = 3) -> list[dict[str, Any]]:
    filtered = [row for row in rows if str(row.get("domain_tag")) == domain]
    filtered.sort(
        key=lambda row: (
            -(float(row.get("confidence") or 0.0)),
            -len(row.get("skill_labels", [])),
            str(row.get("title") or ""),
        )
    )
    examples = []
    for row in filtered[:limit]:
        examples.append(
            {
                "external_id": str(row.get("external_id")),
                "title": str(row.get("title") or ""),
                "company": str(row.get("company") or ""),
                "country": str(row.get("country") or ""),
                "confidence": float(row.get("confidence") or 0.0),
                "method": str(row.get("method") or ""),
                "evidence": row.get("evidence", [])[:6],
            }
        )
    return examples


def _build_signal_domain_map(rows: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    signal_domain_map: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        domain = str(row.get("domain_tag") or "other")
        text = _normalize_text(" ".join([
            str(row.get("title") or ""),
            str(row.get("description") or ""),
            " ".join(row.get("skill_labels", [])),
        ]))
        for signal in GENERIC_SIGNALS:
            if _contains(text, signal):
                signal_domain_map[signal][domain] += 1
    return signal_domain_map


def _generic_signal_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signal_domain_map = _build_signal_domain_map(rows)
    output = []
    for signal in GENERIC_SIGNALS:
        by_domain = signal_domain_map.get(signal, Counter())
        total = sum(by_domain.values())
        contextualizers = []
        for domain, count in by_domain.most_common(5):
            top_tools = _top_tools(rows, domain, limit=5)
            top_keywords = _top_context_keywords(rows, domain, limit=5)
            contextualizers.append(
                {
                    "domain": domain,
                    "count": count,
                    "tools": [item["tool"] for item in top_tools[:3]],
                    "keywords": [item["keyword"] for item in top_keywords[:3]],
                }
            )
        output.append(
            {
                "signal": signal,
                "total_count": total,
                "domains": [{"domain": domain, "count": count} for domain, count in by_domain.most_common()],
                "why_noisy": "appears across multiple business domains with weak standalone semantics",
                "contextualizers": contextualizers,
            }
        )
    return output


def _domain_specific_discriminants(rows: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    signal_counts: Counter[str] = Counter()
    domain_rows = [row for row in rows if str(row.get("domain_tag")) == domain]
    other_rows = [row for row in rows if str(row.get("domain_tag")) != domain]
    for row in domain_rows:
        text = _normalize_text(" ".join([
            str(row.get("title") or ""),
            str(row.get("description") or ""),
            " ".join(row.get("skill_labels", [])),
            " ".join(row.get("evidence", [])),
        ]))
        for tool in TOOL_PATTERNS:
            if _contains(text, tool):
                signal_counts[tool] += 1
        for skill in row.get("skill_labels", []):
            label = _normalize_text(skill)
            if label and label not in GENERIC_SIGNALS:
                signal_counts[label] += 1
    results = []
    for signal, count in signal_counts.most_common(20):
        other_count = 0
        for row in other_rows:
            text = _normalize_text(" ".join([
                str(row.get("title") or ""),
                str(row.get("description") or ""),
                " ".join(row.get("skill_labels", [])),
                " ".join(row.get("evidence", [])),
            ]))
            if _contains(text, signal):
                other_count += 1
        if count < 2:
            continue
        specificity = round(count / max(count + other_count, 1), 3)
        if specificity >= 0.55:
            results.append({"signal": signal, "count": count, "specificity": specificity})
    return results[:10]


def _domain_noise_signals(rows: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    text_counter: Counter[str] = Counter()
    for row in rows:
        if str(row.get("domain_tag")) != domain:
            continue
        text = _normalize_text(" ".join([
            str(row.get("title") or ""),
            str(row.get("description") or ""),
            " ".join(row.get("skill_labels", [])),
        ]))
        for signal in GENERIC_SIGNALS:
            if _contains(text, signal):
                text_counter[signal] += 1
    return [{"signal": signal, "count": count} for signal, count in text_counter.most_common(8)]


def _domain_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    for domain in DOMAIN_ORDER:
        domain_rows = [row for row in rows if str(row.get("domain_tag") or "other") == domain]
        reports.append(
            {
                "domain": domain,
                "offer_count": len(domain_rows),
                "top_titles": _top_titles(rows, domain),
                "top_skills": _top_skills(rows, domain),
                "top_tools": _top_tools(rows, domain),
                "context_keywords": _top_context_keywords(rows, domain),
                "representative_offers": _representative_examples(rows, domain),
                "discriminant_signals": _domain_specific_discriminants(rows, domain),
                "generic_or_noisy_signals": _domain_noise_signals(rows, domain),
            }
        )
    return reports


def _emerging_patterns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for pattern_name, (expected_domain, keywords) in EMERGING_PATTERNS.items():
        matches = []
        for row in rows:
            domain = str(row.get("domain_tag") or "other")
            if expected_domain and domain != expected_domain:
                continue
            text = _normalize_text(" ".join([
                str(row.get("title") or ""),
                str(row.get("description") or ""),
                " ".join(row.get("skill_labels", [])),
            ]))
            matched_keywords = [keyword for keyword in keywords if _contains(text, keyword)]
            if len(matched_keywords) >= 2:
                matches.append(
                    {
                        "external_id": str(row.get("external_id")),
                        "title": str(row.get("title") or ""),
                        "domain": domain,
                        "matched_keywords": matched_keywords,
                    }
                )
        if matches:
            results.append(
                {
                    "pattern": pattern_name,
                    "count": len(matches),
                    "domains": sorted({item["domain"] for item in matches}),
                    "examples": matches[:5],
                }
            )
    results.sort(key=lambda item: (-item["count"], item["pattern"]))
    return results


def _domain_strengths(domain_reports: list[dict[str, Any]]) -> dict[str, list[str]]:
    represented = []
    weak = []
    for report in domain_reports:
        domain = report["domain"]
        count = report["offer_count"]
        if count >= 40:
            represented.append(domain)
        elif count <= 15:
            weak.append(domain)
    return {"well_represented": represented, "weak": weak}


def _bi_absorption_analysis(rows: list[dict[str, Any]], domain_reports: list[dict[str, Any]]) -> dict[str, Any]:
    bi_report = next((item for item in domain_reports if item["domain"] == "data"), None)
    noisy = _generic_signal_report(rows)
    bi_related = [item for item in noisy if item["signal"] in {"reporting", "sql", "excel", "kpi", "analysis"}]
    return {
        "observation": "BI/data-oriented labels absorb cross-functional offers because generic analytics vocabulary is spread across finance, hr, operations, supply and sales.",
        "main_generic_drivers": bi_related,
        "why_context_matters": [
            "SQL becomes discriminant only when paired with warehouse/API/ETL/backend signals.",
            "Excel and reporting become discriminant only when paired with finance control, supply forecasting, HRIS, CRM or campaign context.",
            "KPI alone is cross-domain; it needs product, finance, sales, operations or marketing anchors.",
        ],
        "data_domain_snapshot": bi_report,
    }


def _recommendations_v1(domain_reports: list[dict[str, Any]], emerging_patterns: list[dict[str, Any]]) -> list[str]:
    pattern_names = {item["pattern"] for item in emerging_patterns}
    recommendations = [
        "Keep the current V0 clusters out of runtime until generic cross-domain analytics vocabulary is better contextualized.",
        "Introduce domain-context rules before adding new clusters: SQL, Excel, KPI, reporting and analysis should never be strong standalone anchors.",
        "Prioritize non-data cluster discovery from strongly represented domains first: finance, sales, supply, engineering, operations and HR if confirmed by corpus volume.",
        "Use representative title+tooling+skill triples to define future clusters instead of title-only labels.",
    ]
    if "Finance Ops" in pattern_names:
        recommendations.append("Finance Ops appears naturally enough to study as a future V1 cluster family, but not implement yet.")
    if "HR Operations" in pattern_names:
        recommendations.append("HR Operations appears as a better framing than generic BI for HR dashboard/reporting roles.")
    if "Backend Automation" in pattern_names:
        recommendations.append("Backend Automation can help separate engineering automation from data-centric pipeline logic.")
    return recommendations


def _data_centric_bias_risks(domain_reports: list[dict[str, Any]], generic_signal_report: list[dict[str, Any]]) -> list[str]:
    weak_domains = {item["domain"] for item in domain_reports if item["offer_count"] <= 15}
    risks = [
        "Cross-domain generic analytics signals can over-route offers toward data/BI interpretations.",
        "A data-heavy seed set would under-represent finance, HR, legal and admin nuances even if the DB contains them.",
        "If future calibration relies too much on SQL/Power BI/reporting frequency, BI will absorb finance control, HR digital, supply analytics and sales operations roles.",
    ]
    if "legal" in weak_domains or "admin" in weak_domains:
        risks.append("Lower-volume domains like legal/admin may be overshadowed unless calibrated with domain-specific title and context anchors.")
    if any(item["signal"] == "sql" and item["total_count"] > 20 for item in generic_signal_report):
        risks.append("SQL is widespread enough in the corpus that it must be treated as contextual, not domain-defining.")
    return risks


def build_payload(mode: str) -> dict[str, Any]:
    if mode == "quick":
        rows = load_quick_rows()
        tables = {
            "offer_domain_enrichment": False,
            "offer_skills": False,
            "fact_offer_skills": False,
        }
    else:
        rows, tables = load_postgres_rows()

    domain_distribution = _aggregate_domain_distribution(rows)
    domains = _domain_report(rows)
    generic_signals = _generic_signal_report(rows)
    emerging_patterns = _emerging_patterns(rows)
    volume_strength = _domain_strengths(domains)
    payload = {
        "generated_at": _utc_now(),
        "mode": mode,
        "scope": {
            "source": BUSINESS_FRANCE_SOURCE,
            "active_only": True,
            "read_only": True,
            "tables_detected": tables,
        },
        "methodology": {
            "approach": "SQL-first with light Python synthesis",
            "steps": [
                "Read active Business France offers from clean_offers",
                "Join offer_domain_enrichment read-only on (source, external_id)",
                "Join offer_skills if available, otherwise fact_offer_skills if available",
                "Aggregate volume, titles, skills, tools, contextual keywords and representative examples by domain",
                "Compute noisy generic signal spread and emerging pattern counts in Python",
            ],
        },
        "domain_distribution": domain_distribution,
        "domains": domains,
        "generic_signals": generic_signals,
        "emerging_patterns": emerging_patterns,
        "bi_absorption_analysis": _bi_absorption_analysis(rows, domains),
        "corpus_strength": volume_strength,
        "recommendations_v1": _recommendations_v1(domains, emerging_patterns),
        "data_centric_bias_risks": _data_centric_bias_risks(domains, generic_signals),
    }
    return payload


def write_markdown_report(payload: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Elevia PostgreSQL Multi-Domain Audit v1",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Scope: `clean_offers WHERE source='{payload['scope']['source']}' AND COALESCE(is_active, TRUE)=TRUE`",
        f"- Mode: `{payload['mode']}`",
        f"- Read-only: `{payload['scope']['read_only']}`",
        "",
        "## Methodology",
        "",
        f"- Approach: `{payload['methodology']['approach']}`",
    ]
    for step in payload["methodology"]["steps"]:
        lines.append(f"- {step}")

    lines.extend(["", "## Domain Distribution", ""])
    for item in payload["domain_distribution"]:
        lines.append(f"- `{item['domain']}`: {item['offer_count']} offers ({item['pct']}%)")

    lines.extend(["", "## Representation Strength", ""])
    lines.append(f"- Well represented: `{payload['corpus_strength']['well_represented']}`")
    lines.append(f"- Weak domains: `{payload['corpus_strength']['weak']}`")

    lines.extend(["", "## BI Absorption Risk", ""])
    lines.append(f"- {payload['bi_absorption_analysis']['observation']}")
    for point in payload["bi_absorption_analysis"]["why_context_matters"]:
        lines.append(f"- {point}")

    lines.extend(["", "## Generic Signals Problematiques", ""])
    for signal in payload["generic_signals"]:
        top_domains = ", ".join(f"{item['domain']}={item['count']}" for item in signal["domains"][:5])
        lines.append(f"- `{signal['signal']}` total={signal['total_count']} | {top_domains}")

    lines.extend(["", "## Emerging Patterns", ""])
    for pattern in payload["emerging_patterns"]:
        lines.append(f"- `{pattern['pattern']}`: {pattern['count']} offers | domains={pattern['domains']}")

    lines.extend(["", "## Domain Details", ""])
    for domain in payload["domains"]:
        lines.append(f"### {domain['domain']}")
        lines.append(f"- Volume: `{domain['offer_count']}`")
        lines.append(f"- Top titles: {[item['title'] for item in domain['top_titles'][:5]]}")
        lines.append(f"- Top skills: {[item['skill'] for item in domain['top_skills'][:7]]}")
        lines.append(f"- Top tools: {[item['tool'] for item in domain['top_tools'][:7]]}")
        lines.append(f"- Context keywords: {[item['keyword'] for item in domain['context_keywords'][:7]]}")
        lines.append(f"- Discriminant signals: {[item['signal'] for item in domain['discriminant_signals'][:7]]}")
        lines.append(f"- Generic/noisy signals: {[item['signal'] for item in domain['generic_or_noisy_signals'][:7]]}")
        if domain["representative_offers"]:
            lines.append("- Representative offers:")
            for offer in domain["representative_offers"][:3]:
                lines.append(f"  - `{offer['external_id']}` {offer['title']} ({offer['company']}, {offer['country']})")
        lines.append("")

    lines.extend(["## Recommendations V1", ""])
    for item in payload["recommendations_v1"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Data-Centric Bias Risks", ""])
    for item in payload["data_centric_bias_risks"]:
        lines.append(f"- {item}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only PostgreSQL multi-domain audit for Elevia metier")
    parser.add_argument("--mode", choices=["quick", "full"], default="full")
    parser.add_argument(
        "--output-json",
        default=str(REPO_ROOT / "baseline" / "elevia_metier_postgres_audit" / "latest.json"),
    )
    parser.add_argument(
        "--output-md",
        default=str(REPO_ROOT / "docs" / "ai" / "reports" / "elevia_metier_postgres_audit_v1.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.mode)
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown_report(payload, output_md)
    print(f"[elevia_metier_postgres_audit] wrote {output_json}")
    print(f"[elevia_metier_postgres_audit] wrote {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
