from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from psycopg.types.json import Json

from .offer_domain_enrichment import classify_and_persist_business_france_offer_domains_with_connection
from .offer_skills_uri_resolver import dump_json, resolve_offer_skill_rows_to_uris


@dataclass
class CoverageSnapshot:
    total_offers: int
    active_offers: int
    offer_skills_coverage: float
    canonical_skills_coverage: float
    skills_uri_coverage: float
    offers_without_skills_uri: int
    other_count: int
    needs_review_count: int


def detect_other_bucket_subfamily(*, title: str | None, labels: list[str] | None) -> str:
    text = " ".join([str(title or "")] + [str(label or "") for label in (labels or [])]).lower()
    if any(token in text for token in ("user acquisition", "performance marketing", "branding", "communication")):
        return "marketing"
    if any(token in text for token in ("buyer", "procurement", "supplier", "purchasing")):
        return "supply"
    if any(token in text for token in ("product owner", "backlog", "requirements gathering", "process optimization")):
        return "operations"
    if any(token in text for token in ("privacy", "compliance", "regulatory")):
        return "legal"
    if any(token in text for token in ("mechanical design", "quality engineering", "it support", "developer")):
        return "engineering"
    if any(token in text for token in ("assistant", "support", "office")):
        return "administration"
    return "other"


def assert_non_regression(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    check_other_bucket: bool = True,
    check_needs_review: bool = True,
) -> None:
    if float(after["skills_uri_coverage"]) < float(before["skills_uri_coverage"]):
        raise RuntimeError("skills_uri coverage decreased")
    if float(after["canonical_skills_coverage"]) < float(before["canonical_skills_coverage"]):
        raise RuntimeError("canonical_skills coverage decreased")
    if check_other_bucket and int(after["other_count"]) > int(before["other_count"]):
        raise RuntimeError("other bucket increased")
    if check_needs_review and int(after["needs_review_count"]) > int(before["needs_review_count"]):
        raise RuntimeError("needs_review increased")


def ensure_offer_skills_uri_columns(conn, *, table_name: str = "offer_skills") -> None:
    from psycopg import sql

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS normalized_label TEXT").format(
                table_name=sql.Identifier(table_name)
            )
        )
        cursor.execute(
            sql.SQL(
                "ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS resolved_esco_uris JSONB NOT NULL DEFAULT '[]'::jsonb"
            ).format(table_name=sql.Identifier(table_name))
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS uri_resolution_source TEXT").format(
                table_name=sql.Identifier(table_name)
            )
        )


def _pct(n: int, d: int) -> float:
    return round((n / d) * 100, 2) if d else 0.0


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return bool(cursor.fetchone())


def compute_coverage_snapshot(conn) -> CoverageSnapshot:
    has_resolved_esco_uris = _column_exists(conn, "offer_skills", "resolved_esco_uris")
    uri_filter = (
        "jsonb_array_length(COALESCE(os.resolved_esco_uris, '[]'::jsonb)) > 0"
        if has_resolved_esco_uris
        else "FALSE"
    )
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
              COUNT(DISTINCT c.id) FILTER (WHERE c.is_active = TRUE) AS active_offers,
              COUNT(DISTINCT c.id) AS total_offers,
              COUNT(DISTINCT c.id) FILTER (WHERE c.is_active = TRUE AND os.label IS NOT NULL) AS offers_with_skills,
              COUNT(DISTINCT c.id) FILTER (WHERE c.is_active = TRUE AND os.canonical_id IS NOT NULL) AS offers_with_canonical,
              COUNT(DISTINCT c.id) FILTER (
                  WHERE c.is_active = TRUE
                    AND {uri_filter}
              ) AS offers_with_uri,
              COUNT(DISTINCT c.id) FILTER (
                  WHERE c.is_active = TRUE AND ode.domain_tag = 'other'
              ) AS other_count,
              COUNT(DISTINCT c.id) FILTER (
                  WHERE c.is_active = TRUE AND COALESCE(ode.needs_ai_review, FALSE) = TRUE
              ) AS needs_review_count
            FROM clean_offers c
            LEFT JOIN offer_skills os
              ON os.offer_id = c.id AND os.source = c.source
            LEFT JOIN offer_domain_enrichment ode
              ON ode.source = c.source AND ode.external_id = c.external_id
            WHERE c.source = 'business_france'
            """
        )
        (
            active_offers,
            total_offers,
            offers_with_skills,
            offers_with_canonical,
            offers_with_uri,
            other_count,
            needs_review_count,
        ) = cursor.fetchone()

    active = int(active_offers or 0)
    offers_with_uri_int = int(offers_with_uri or 0)
    return CoverageSnapshot(
        total_offers=int(total_offers or 0),
        active_offers=active,
        offer_skills_coverage=_pct(int(offers_with_skills or 0), active),
        canonical_skills_coverage=_pct(int(offers_with_canonical or 0), active),
        skills_uri_coverage=_pct(offers_with_uri_int, active),
        offers_without_skills_uri=max(0, active - offers_with_uri_int),
        other_count=int(other_count or 0),
        needs_review_count=int(needs_review_count or 0),
    )


def _fetch_business_france_offer_rows(conn, *, external_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
    normalized_external_ids = sorted(
        {
            str(external_id).strip()
            for external_id in (external_ids or [])
            if str(external_id).strip()
        }
    )
    external_filter_sql = ""
    params: list[Any] = []
    if normalized_external_ids:
        external_filter_sql = " AND c.external_id = ANY(%s)"
        params.append(normalized_external_ids)
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
              c.id,
              c.external_id,
              c.title,
              c.company,
              c.is_active,
              COALESCE(c.payload_json, '{{}}'::jsonb),
              COALESCE(ode.domain_tag, 'other'),
              COALESCE(ode.job_family, 'Other'),
              COALESCE(ode.primary_function, 'Other'),
              COALESCE(ode.needs_ai_review, FALSE),
              COALESCE(ode.method, 'rules'),
              COALESCE(ode.evidence, '[]'::jsonb)
            FROM clean_offers c
            LEFT JOIN offer_domain_enrichment ode
              ON ode.source = c.source AND ode.external_id = c.external_id
            WHERE c.source = 'business_france'
            {external_filter_sql}
            ORDER BY c.id ASC
            """,
            tuple(params),
        )
        rows = cursor.fetchall()

    return [
        {
            "offer_id": int(row[0]),
            "external_id": str(row[1]),
            "title": str(row[2] or ""),
            "company": str(row[3] or ""),
            "is_active": bool(row[4]),
            "payload_json": row[5] if isinstance(row[5], dict) else {},
            "domain_tag": str(row[6] or "other"),
            "job_family": str(row[7] or "Other"),
            "primary_function": str(row[8] or "Other"),
            "needs_review": bool(row[9]),
            "method": str(row[10] or "rules"),
            "evidence": row[11] if isinstance(row[11], list) else [],
        }
        for row in rows
    ]


def _fetch_offer_skill_rows(conn, *, external_ids: Sequence[str] | None = None) -> dict[int, list[dict[str, Any]]]:
    has_resolved_esco_uris = _column_exists(conn, "offer_skills", "resolved_esco_uris")
    resolved_expr = "COALESCE(resolved_esco_uris, '[]'::jsonb)" if has_resolved_esco_uris else "'[]'::jsonb"
    normalized_external_ids = sorted(
        {
            str(external_id).strip()
            for external_id in (external_ids or [])
            if str(external_id).strip()
        }
    )
    external_filter_sql = ""
    params: list[Any] = []
    if normalized_external_ids:
        external_filter_sql = " AND external_id = ANY(%s)"
        params.append(normalized_external_ids)
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT offer_id, label, canonical_id, {resolved_expr}
            FROM offer_skills
            WHERE source = 'business_france'
            {external_filter_sql}
            ORDER BY offer_id ASC, label ASC
            """,
            tuple(params),
        )
        rows = cursor.fetchall()

    mapping: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for offer_id, label, canonical_id, resolved_esco_uris in rows:
        mapping[int(offer_id)].append(
            {
                "label": str(label or ""),
                "canonical_id": str(canonical_id or ""),
                "resolved_esco_uris": resolved_esco_uris if isinstance(resolved_esco_uris, list) else [],
            }
        )
    return mapping


def _derive_review_reason(offer: dict[str, Any], unresolved_labels: list[str]) -> str:
    reasons: list[str] = []
    if offer.get("domain_tag") == "other":
        reasons.append("domain_tag=other")
    if offer.get("needs_review"):
        reasons.append("needs_ai_review=true")
    if unresolved_labels:
        reasons.append("unresolved_uri_labels")
    if not reasons:
        reasons.append("resolved")
    return ", ".join(reasons)


def generate_skills_uri_coverage_audit(conn, *, external_ids: Sequence[str] | None = None) -> dict[str, Any]:
    offers = _fetch_business_france_offer_rows(conn, external_ids=external_ids)
    offer_skill_rows = _fetch_offer_skill_rows(conn, external_ids=external_ids)
    affected: list[dict[str, Any]] = []
    unresolved_label_counter: Counter[str] = Counter()
    unresolved_family_counter: Counter[str] = Counter()
    unresolved_canonical_no_uri: Counter[str] = Counter()

    for offer in offers:
        rows = offer_skill_rows.get(offer["offer_id"], [])
        resolution = resolve_offer_skill_rows_to_uris(rows)
        if resolution["skills_uri"]:
            continue
        review_reason = _derive_review_reason(offer, resolution["unresolved_labels"])
        for row in resolution["unresolved_rows"]:
            unresolved_label_counter[str(row["label"])] += 1
            if row.get("canonical_id"):
                unresolved_canonical_no_uri[str(row["canonical_id"])] += 1
        unresolved_family_counter[str(offer["job_family"] or "Other")] += 1
        affected.append(
            {
                "offer_id": offer["external_id"],
                "title": offer["title"],
                "company": offer["company"],
                "job_family": offer["job_family"],
                "primary_function": offer["primary_function"],
                "canonical_skills": sorted({str(row.get("canonical_id") or "") for row in rows if str(row.get("canonical_id") or "").strip()}),
                "skills_raw": sorted({str(row.get("label") or "") for row in rows if str(row.get("label") or "").strip()}),
                "skills_uri": [],
                "needs_review": offer["needs_review"],
                "review_reason": review_reason,
            }
        )

    families = Counter(item["job_family"] for item in affected)
    report = {
        "affected_offers": affected,
        "families_most_affected": families.most_common(),
        "top_unresolved_skills": unresolved_label_counter.most_common(50),
        "top_unresolved_job_families": unresolved_family_counter.most_common(),
        "skills_already_canonicalized_but_without_uri": unresolved_canonical_no_uri.most_common(50),
    }
    likely_variants = [
        (label, count)
        for label, count in report["top_unresolved_skills"]
        if any(token in label.lower() for token in ("bi", "excel", "power", "sap", "crm", "salesforce"))
    ][:20]
    likely_tools = [
        (label, count)
        for label, count in report["top_unresolved_skills"]
        if any(token in label.lower() for token in ("sap", "excel", "salesforce", "power bi", "crm"))
    ][:20]
    likely_domain_gaps = [
        (canonical_id, count)
        for canonical_id, count in report["skills_already_canonicalized_but_without_uri"]
        if canonical_id.startswith("skill:")
    ][:20]

    lines = [
        "# SKILLS URI Coverage Audit",
        "",
        f"Offers without resolved `skills_uri`: **{len(affected)}**",
        "",
        "## Families most affected",
        "",
    ]
    for family, count in report["families_most_affected"]:
        lines.append(f"- `{family}`: {count}")
    lines.extend([
        "",
        "## Top unresolved skills",
        "",
    ])
    for label, count in report["top_unresolved_skills"][:30]:
        lines.append(f"- `{label}`: {count}")
    lines.extend([
        "",
        "## Canonical skills without URI",
        "",
    ])
    for canonical_id, count in report["skills_already_canonicalized_but_without_uri"][:30]:
        lines.append(f"- `{canonical_id}`: {count}")
    lines.extend([
        "",
        "## Likely obvious variants of existing skills",
        "",
    ])
    for label, count in likely_variants:
        lines.append(f"- `{label}`: {count}")
    lines.extend([
        "",
        "## Likely tools / platforms needing stable URI promotion",
        "",
    ])
    for label, count in likely_tools:
        lines.append(f"- `{label}`: {count}")
    lines.extend([
        "",
        "## Likely domain skills still lacking URI coverage",
        "",
    ])
    for canonical_id, count in likely_domain_gaps:
        lines.append(f"- `{canonical_id}`: {count}")
    lines.extend([
        "",
        "## Probable URI loss reasons",
        "",
        "- canonical skill exists but has no deterministic ESCO bridge yet",
        "- raw labels are tool variants or shorthand not yet collapsed to a stable canonical key",
        "- offer carries domain-specific canonicals with no exact ESCO promotion path",
        "- bucket families with low URI density still rely on labels only",
        "",
    ])
    lines.extend([
        "## Affected offers",
        "",
    ])
    for item in affected:
        lines.append(
            f"- `{item['offer_id']}` | {item['title']} | {item['company']} | "
            f"`{item['job_family']}` / `{item['primary_function']}` | "
            f"`needs_review={item['needs_review']}` | {item['review_reason']}"
        )
        lines.append(f"  canonical_skills: {dump_json(item['canonical_skills'])}")
        lines.append(f"  skills_raw: {dump_json(item['skills_raw'])}")
    return {
        "markdown": "\n".join(lines) + "\n",
        "report": report,
    }


def generate_other_bucket_audit(conn, *, external_ids: Sequence[str] | None = None) -> dict[str, Any]:
    offers = _fetch_business_france_offer_rows(conn, external_ids=external_ids)
    offer_skill_rows = _fetch_offer_skill_rows(conn, external_ids=external_ids)
    other_rows: list[dict[str, Any]] = []
    subfamily_counter: Counter[str] = Counter()

    for offer in offers:
        if not offer["is_active"] or offer["domain_tag"] != "other":
            continue
        labels = [row["label"] for row in offer_skill_rows.get(offer["offer_id"], []) if row.get("label")]
        subfamily = detect_other_bucket_subfamily(title=offer["title"], labels=labels)
        subfamily_counter[subfamily] += 1
        other_rows.append(
            {
                "offer_id": offer["external_id"],
                "title": offer["title"],
                "company": offer["company"],
                "subfamily": subfamily,
                "needs_review": offer["needs_review"],
                "labels": sorted(set(labels))[:8],
            }
        )

    lines = [
        "# Offer Other Bucket Audit",
        "",
        f"Active offers in `other`: **{len(other_rows)}**",
        "",
        "## Recurrent subfamilies",
        "",
    ]
    for name, count in subfamily_counter.most_common():
        lines.append(f"- `{name}`: {count}")
    lines.extend([
        "",
        "## Deterministic rule candidates",
        "",
    ])
    for name, count in subfamily_counter.most_common():
        if count < 3 or name == "other":
            continue
        lines.append(f"- `{name}`: recurring enough for rule-based reassignment ({count} offers)")
    lines.extend([
        "",
        "## Offers",
        "",
    ])
    for item in other_rows:
        lines.append(
            f"- `{item['offer_id']}` | {item['title']} | {item['company']} | "
            f"`{item['subfamily']}` | `needs_review={item['needs_review']}`"
        )
        lines.append(f"  labels: {dump_json(item['labels'])}")
    return {
        "markdown": "\n".join(lines) + "\n",
        "report": {
            "other_rows": other_rows,
            "subfamily_counts": subfamily_counter.most_common(),
        },
    }


def backfill_offer_skill_resolved_uris(conn, *, external_ids: Sequence[str] | None = None) -> dict[str, Any]:
    from psycopg import sql

    ensure_offer_skills_uri_columns(conn)
    offer_skill_rows = _fetch_offer_skill_rows(conn, external_ids=external_ids)
    offer_rows = _fetch_business_france_offer_rows(conn, external_ids=external_ids)
    family_by_offer_id = {
        int(offer["offer_id"]): str(offer["job_family"] or "Other")
        for offer in offer_rows
    }
    rows_updated = 0
    unresolved_counter: Counter[str] = Counter()
    unresolved_families: Counter[str] = Counter()

    update_sql = sql.SQL(
        """
        UPDATE offer_skills
        SET normalized_label = %(normalized_label)s,
            resolved_esco_uris = %(resolved_esco_uris)s::jsonb,
            uri_resolution_source = %(uri_resolution_source)s
        WHERE source = 'business_france'
          AND offer_id = %(offer_id)s
          AND canonical_id = %(canonical_id)s
          AND label = %(label)s
        """
    )

    with conn.cursor() as cursor:
        for offer_id, rows in offer_skill_rows.items():
            resolution = resolve_offer_skill_rows_to_uris(rows)
            resolved_by_pair = {
                (str(row["canonical_id"]), str(row["label"])): row
                for row in resolution["resolved_rows"]
            }
            for row in rows:
                canonical_id = str(row.get("canonical_id") or "")
                label = str(row.get("label") or "")
                resolved = resolved_by_pair.get((canonical_id, label))
                normalized_label = label.strip().lower()
                resolved_uris = resolved.get("resolved_esco_uris", []) if resolved else []
                if not resolved_uris:
                    unresolved_counter[label] += 1
                    unresolved_families[family_by_offer_id.get(int(offer_id), "Other")] += 1
                cursor.execute(
                    update_sql,
                    {
                        "offer_id": offer_id,
                        "canonical_id": canonical_id,
                        "label": label,
                        "normalized_label": normalized_label,
                        "resolved_esco_uris": Json(resolved_uris),
                        "uri_resolution_source": "deterministic_overlay" if resolved_uris else "unresolved",
                    },
                )
                rows_updated += 1
    conn.commit()
    return {
        "rows_updated": rows_updated,
        "top_unresolved_skills": unresolved_counter.most_common(50),
        "top_unresolved_job_families": unresolved_families.most_common(),
    }


def write_report(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def run_offer_skills_uri_backfill(
    *,
    database_url: str | None = None,
    external_ids: Sequence[str] | None = None,
    write_reports: bool = True,
    rerun_domain_enrichment: bool = True,
) -> dict[str, Any]:
    url = (database_url or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    import psycopg

    with psycopg.connect(url, connect_timeout=5) as conn:
        before = compute_coverage_snapshot(conn)
        if write_reports:
            uri_audit = generate_skills_uri_coverage_audit(conn, external_ids=external_ids)
            write_report("docs/ai/SKILLS_URI_COVERAGE_AUDIT.md", uri_audit["markdown"])

        backfill_result = backfill_offer_skill_resolved_uris(conn, external_ids=external_ids)
        if rerun_domain_enrichment:
            classify_and_persist_business_france_offer_domains_with_connection(
                conn,
                external_ids=external_ids,
                enable_ai_fallback=False,
            )
        if write_reports:
            other_audit = generate_other_bucket_audit(conn, external_ids=external_ids)
            write_report("docs/ai/OFFER_OTHER_BUCKET_AUDIT.md", other_audit["markdown"])
        after = compute_coverage_snapshot(conn)

    before_dict = before.__dict__
    after_dict = after.__dict__
    assert_non_regression(
        before_dict,
        after_dict,
        check_other_bucket=not bool(external_ids),
        check_needs_review=not bool(external_ids),
    )
    return {
        "before": before_dict,
        "after": after_dict,
        "rows_updated": int(backfill_result["rows_updated"]),
        "top_unresolved_skills": backfill_result["top_unresolved_skills"],
    }
