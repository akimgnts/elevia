"""
offer_skills_pg.py - Deterministic persistence for canonical offer skills.

Scope:
- additive PostgreSQL storage only
- no scoring / matching / skills_uri changes
- current enrichment pipeline reused as-is
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from compass.canonical.weighted_store import (
    get_weighted_store,
    map_offer_cluster_to_weighted,
    resolve_weighted_skill,
)
from compass.offer.offer_parse_pipeline import build_offer_canonical_representation


ENRICHMENT_VERSION = "offer_skills_v2"
FLAG_OFFER_SKILLS_AI_MODEL = "ELEVIA_OFFER_SKILLS_AI_MODEL"
FLAG_OFFER_SKILLS_AI_TIMEOUT = "ELEVIA_OFFER_SKILLS_AI_TIMEOUT"
AI_FALLBACK_MIN_SKILLS = 3
AI_FALLBACK_MAX_SKILLS = 5
AI_FALLBACK_CONFIDENCE = 0.6
DEFAULT_FALLBACK_BATCH_SIZE = 15
_AI_GENERIC_BLOCKLIST = {
    "communication",
    "motivation",
    "teamwork",
    "team spirit",
    "organisation",
    "management",
    "project",
    "support",
}
_OPENAI_CLIENT = None
_OPENAI_CLIENT_KEY = None
_AI_SKILL_NORMALIZATION_RULES: tuple[tuple[str, str], ...] = (
    ("talent acquisition", "recruitment"),
    ("candidate sourcing", "recruitment"),
    ("application screening", "recruitment"),
    ("job posting", "recruitment"),
    ("interview coordination", "recruitment"),
    ("candidate pipeline", "recruitment"),
    ("talent management", "recruitment"),
    ("human resources", "recruitment"),
    ("hr processes", "recruitment"),
    ("recruit", "recruitment"),
    ("onboarding", "onboarding"),
    ("crm", "crm management"),
    ("customer relationship", "crm management"),
    ("prospecting", "lead generation"),
    ("lead generation", "lead generation"),
    ("reporting", "business intelligence"),
    ("dashboard", "business intelligence"),
    ("business intelligence", "business intelligence"),
    ("data analysis", "data analysis"),
    ("data analytics", "data analysis"),
    ("project management", "project management"),
    ("coordination", "project management"),
    ("operations management", "operations management"),
    ("supply chain", "supply chain"),
    ("budget", "budgeting"),
    ("financial analysis", "financial analysis"),
    ("compliance", "compliance"),
    ("sql", "sql"),
    ("python", "python"),
    ("excel", "excel"),
    ("sap", "sap"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_database_url() -> str | None:
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None


def compute_offer_skills_content_hash(*, title: str | None, description: str | None) -> str:
    raw = f"{str(title or '').strip().lower()}||{str(description or '').strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def ensure_offer_skills_table(conn, *, table_name: str = "offer_skills", clean_table: str = "clean_offers") -> None:
    from psycopg import sql

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    offer_id BIGINT NOT NULL REFERENCES {clean_table}(id) ON DELETE CASCADE,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    canonical_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    importance_level TEXT NOT NULL CHECK (importance_level IN ('CORE', 'SECONDARY')),
                    source_method TEXT NOT NULL,
                    confidence DOUBLE PRECISION,
                    enrichment_version TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    CONSTRAINT {uq_name} UNIQUE (offer_id, canonical_id)
                )
                """
            ).format(
                table_name=sql.Identifier(table_name),
                clean_table=sql.Identifier(clean_table),
                uq_name=sql.Identifier(f"{table_name}_offer_id_canonical_id_key"),
            )
        )
        # Idempotent migration for legacy tables:
        # - legacy schema stored the enrichment method in a column literally named
        #   "source". We rename it to source_method, then introduce the business
        #   identity columns (source, external_id) populated from clean_offers.
        cursor.execute(
            """
            SELECT
                EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                      AND column_name = 'source_method'
                ) AS has_method,
                EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                      AND column_name = 'external_id'
                ) AS has_external_id
            """,
            (table_name, table_name),
        )
        has_method, has_external_id = cursor.fetchone()
        if not has_method and not has_external_id:
            # Pre-migration schema: the column named "source" actually stores the
            # enrichment method. Rename it before adding the business key.
            cursor.execute(
                sql.SQL("ALTER TABLE {table_name} RENAME COLUMN source TO source_method").format(
                    table_name=sql.Identifier(table_name),
                )
            )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS source TEXT").format(
                table_name=sql.Identifier(table_name),
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS external_id TEXT").format(
                table_name=sql.Identifier(table_name),
            )
        )
        cursor.execute(
            sql.SQL(
                """
                UPDATE {table_name} AS os
                SET source = co.source,
                    external_id = co.external_id
                FROM {clean_table} AS co
                WHERE os.offer_id = co.id
                  AND (os.source IS NULL OR os.external_id IS NULL)
                """
            ).format(
                table_name=sql.Identifier(table_name),
                clean_table=sql.Identifier(clean_table),
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ALTER COLUMN source SET NOT NULL").format(
                table_name=sql.Identifier(table_name),
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ALTER COLUMN external_id SET NOT NULL").format(
                table_name=sql.Identifier(table_name),
            )
        )
        cursor.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}(offer_id)").format(
                idx_name=sql.Identifier(f"idx_{table_name}_offer_id"),
                table_name=sql.Identifier(table_name),
            )
        )
        cursor.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}(canonical_id)").format(
                idx_name=sql.Identifier(f"idx_{table_name}_canonical_id"),
                table_name=sql.Identifier(table_name),
            )
        )
        cursor.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}(content_hash)").format(
                idx_name=sql.Identifier(f"idx_{table_name}_content_hash"),
                table_name=sql.Identifier(table_name),
            )
        )
        cursor.execute(
            sql.SQL("CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}(source, external_id)").format(
                idx_name=sql.Identifier(f"idx_{table_name}_source_external_id"),
                table_name=sql.Identifier(table_name),
            )
        )


def _normalize_importance(value: str | None) -> str:
    if str(value or "").upper() == "CORE":
        return "CORE"
    return "SECONDARY"


def _normalize_ai_skill_candidates(values: list[Any] | None, *, limit: int = AI_FALLBACK_MAX_SKILLS) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        label = " ".join(str(item or "").strip().split())
        key = label.lower()
        if (
            not label
            or key in seen
            or key in _AI_GENERIC_BLOCKLIST
            or len(label) > 80
            or any(mark in label for mark in (".", ";", ":", "\n"))
        ):
            continue
        seen.add(key)
        result.append(label)
        if len(result) >= max(1, limit):
            break
    return result


def _canonicalize_ai_skill_labels(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip().lower()
        candidate = value
        for marker, replacement in _AI_SKILL_NORMALIZATION_RULES:
            if marker in normalized:
                candidate = replacement
                break
        key = candidate.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def _get_openai_client():
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None, None
    from openai import OpenAI

    global _OPENAI_CLIENT, _OPENAI_CLIENT_KEY
    if _OPENAI_CLIENT is None or _OPENAI_CLIENT_KEY != api_key:
        _OPENAI_CLIENT = OpenAI(
            api_key=api_key,
            timeout=float(os.getenv(FLAG_OFFER_SKILLS_AI_TIMEOUT, "20")),
        )
        _OPENAI_CLIENT_KEY = api_key
    model = os.getenv(FLAG_OFFER_SKILLS_AI_MODEL) or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    return _OPENAI_CLIENT, model


def generate_ai_offer_skill_candidates(*, title: str | None, description: str | None) -> list[str]:
    client, model = _get_openai_client()
    if client is None:
        return []

    prompt = (
        "Extract 3 to 5 job-relevant skills from the offer.\n"
        "Rules:\n"
        "- Return JSON only\n"
        "- Use title and description only\n"
        "- Prefer normalized skill labels that could appear in a job skills taxonomy\n"
        "- Prefer multi-word business or technical concepts when possible\n"
        "- No sentences\n"
        "- No generic soft skills\n"
        "- No duplicates\n"
        "- Prefer labels similar to: recruitment, onboarding, project management, data analysis, business intelligence, "
        "CRM management, lead generation, supply chain, SQL, Python, Excel, SAP, compliance, budgeting\n"
        "- Output format: {\"skills\": [\"...\"]}\n"
    )
    user_content = json.dumps(
        {
            "title": title or "",
            "description": description or "",
        },
        ensure_ascii=False,
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
    )
    content = response.choices[0].message.content or "{}"
    payload = json.loads(content)
    return _normalize_ai_skill_candidates(payload.get("skills") or [])


def generate_ai_offer_skills_batch(items: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    """Batched fallback: one OpenAI call for multiple offers.

    Input shape: [{"offer_id": "...", "title": "...", "description": "..."}]
    Output shape: {"offer_id": ["skill A", "skill B", ...]}

    Rules baked into the prompt:
    - max 5 skills per offer
    - no sentences, no generic soft skills
    - prefer multi-word business concepts
    - empty list allowed when no reliable skill can be inferred
    """

    if not items:
        return {}
    client, model = _get_openai_client()
    if client is None:
        return {}

    prompt = (
        "You extract job-relevant skills from multiple job offers in a single call.\n"
        "Rules:\n"
        "- Return JSON only, no prose, no explanations.\n"
        "- Each key is an offer_id provided in the input, value is a list of skill labels.\n"
        "- Max 5 skills per offer.\n"
        "- No sentences. No generic soft skills (communication, motivation, teamwork, management, support).\n"
        "- Prefer multi-word business or technical concepts (recruitment, onboarding, project management, "
        "data analysis, business intelligence, CRM management, lead generation, supply chain, SQL, Python, "
        "Excel, SAP, compliance, budgeting).\n"
        "- Only use information present in the offer title and description.\n"
        "- Return an empty list for an offer when no reliable skill can be inferred.\n"
        "- Output format: {\"skills_by_offer\": {\"<offer_id>\": [\"...\"]}}\n"
    )
    payload_items = []
    for item in items:
        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id:
            continue
        payload_items.append(
            {
                "offer_id": offer_id,
                "title": str(item.get("title") or ""),
                "description": str(item.get("description") or ""),
            }
        )
    if not payload_items:
        return {}
    user_content = json.dumps({"offers": payload_items}, ensure_ascii=False)

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
    except Exception:
        return {}

    skills_by_offer = parsed.get("skills_by_offer")
    if not isinstance(skills_by_offer, dict):
        return {}
    out: dict[str, list[str]] = {}
    for raw_key, raw_values in skills_by_offer.items():
        key = str(raw_key).strip()
        if not key or not isinstance(raw_values, list):
            continue
        out[key] = [str(value) for value in raw_values if isinstance(value, (str, int, float))]
    return out


def _build_deterministic_rows_for_offer(
    *,
    offer_id: int,
    source: str,
    external_id: str,
    title: str | None,
    description: str | None,
    canonical_builder: Callable[[dict[str, Any]], dict[str, Any]] | None,
    enrichment_version: str,
    now: str,
    content_hash: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    builder = canonical_builder or build_offer_canonical_representation
    base_offer = {
        "id": str(offer_id),
        "title": title or "",
        "description": description or "",
        "skills": [],
        "skills_display": [],
    }
    parsed = builder(base_offer)
    offer_cluster = parsed.get("offer_cluster")
    weighted_cluster = map_offer_cluster_to_weighted(str(offer_cluster)) if offer_cluster else None
    store = get_weighted_store()

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in parsed.get("canonical_skills") or []:
        canonical_id = str(entry.get("canonical_id") or "").strip()
        label = str(entry.get("label") or "").strip()
        if not canonical_id or not label or canonical_id in seen:
            continue
        seen.add(canonical_id)
        resolved = resolve_weighted_skill(
            label,
            weighted_cluster,
            store=store,
            clamp_min=0.5,
            clamp_max=1.5,
        )
        rows.append(
            {
                "offer_id": int(offer_id),
                "source": source,
                "external_id": external_id,
                "canonical_id": canonical_id,
                "label": label,
                "importance_level": _normalize_importance(resolved.importance_level),
                "source_method": str(entry.get("strategy") or "canonical_mapping"),
                "confidence": float(entry.get("confidence") or 0.0),
                "enrichment_version": enrichment_version,
                "content_hash": content_hash,
                "created_at": now,
            }
        )
    return rows, base_offer


def _canonicalize_ai_labels_to_rows(
    *,
    offer_id: int,
    source: str,
    external_id: str,
    base_offer: dict[str, Any],
    ai_labels: Iterable[str],
    existing_canonical_ids: Iterable[str],
    content_hash: str,
    now: str,
    canonical_builder: Callable[[dict[str, Any]], dict[str, Any]] | None,
    enrichment_version: str,
) -> list[dict[str, Any]]:
    """Canonicalize AI-proposed labels for one offer. Discards unresolved."""

    builder = canonical_builder or build_offer_canonical_representation
    normalized = _canonicalize_ai_skill_labels(
        _normalize_ai_skill_candidates(list(ai_labels or []), limit=AI_FALLBACK_MAX_SKILLS)
    )
    if not normalized:
        return []
    parsed_ai = builder({**base_offer, "skills": normalized})
    rows: list[dict[str, Any]] = []
    seen = set(existing_canonical_ids)
    for entry in parsed_ai.get("canonical_skills") or []:
        canonical_id = str(entry.get("canonical_id") or "").strip()
        label = str(entry.get("label") or "").strip()
        if not canonical_id or not label or canonical_id in seen:
            continue
        seen.add(canonical_id)
        rows.append(
            {
                "offer_id": int(offer_id),
                "source": source,
                "external_id": external_id,
                "canonical_id": canonical_id,
                "label": label,
                "importance_level": "SECONDARY",
                "source_method": "ai_fallback",
                "confidence": AI_FALLBACK_CONFIDENCE,
                "enrichment_version": enrichment_version,
                "content_hash": content_hash,
                "created_at": now,
            }
        )
    return rows


def build_offer_skills_rows(
    *,
    offer_id: int,
    source: str,
    external_id: str,
    title: str | None,
    description: str | None,
    canonical_builder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ai_skill_generator: Callable[..., list[str]] | None = None,
    enrichment_version: str = ENRICHMENT_VERSION,
) -> tuple[list[dict[str, Any]], str, dict[str, int]]:
    """Per-offer convenience entry kept for backward compatibility.

    Runs deterministic enrichment, and if below the minimum threshold, calls
    the per-offer AI generator once and appends canonicalized fallback rows.
    """

    content_hash = compute_offer_skills_content_hash(title=title, description=description)
    now = _utc_now()
    det_rows, base_offer = _build_deterministic_rows_for_offer(
        offer_id=offer_id,
        source=source,
        external_id=external_id,
        title=title,
        description=description,
        canonical_builder=canonical_builder,
        enrichment_version=enrichment_version,
        now=now,
        content_hash=content_hash,
    )
    rows = list(det_rows)
    stats = {
        "deterministic_rows": len(det_rows),
        "ai_triggered": 0,
        "ai_added_rows": 0,
    }

    if len(rows) < AI_FALLBACK_MIN_SKILLS:
        generator = ai_skill_generator or generate_ai_offer_skill_candidates
        ai_labels = generator(title=title or "", description=description or "") or []
        stats["ai_triggered"] = 1
        ai_rows = _canonicalize_ai_labels_to_rows(
            offer_id=offer_id,
            source=source,
            external_id=external_id,
            base_offer=base_offer,
            ai_labels=ai_labels,
            existing_canonical_ids={row["canonical_id"] for row in det_rows},
            content_hash=content_hash,
            now=now,
            canonical_builder=canonical_builder,
            enrichment_version=enrichment_version,
        )
        rows.extend(ai_rows)
        stats["ai_added_rows"] = len(ai_rows)

    return rows, content_hash, stats


def _resolve_ai_labels_batched(
    candidates: list[dict[str, Any]],
    *,
    ai_batch_generator: Callable[[list[Mapping[str, Any]]], Mapping[str, list[str]]] | None,
    ai_skill_generator: Callable[..., list[str]] | None,
    batch_size: int,
) -> tuple[dict[str, list[str]], int]:
    """Resolve AI labels for a list of offers.

    When a batch generator is provided, groups of `batch_size` offers are sent
    in a single provider call. Otherwise falls back to the per-offer generator
    for backward compatibility with existing callers/tests.
    """

    labels_by_offer: dict[str, list[str]] = {}
    batches_sent = 0

    if not candidates:
        return labels_by_offer, batches_sent

    if ai_batch_generator is not None:
        size = max(1, int(batch_size or DEFAULT_FALLBACK_BATCH_SIZE))
        for start in range(0, len(candidates), size):
            chunk = candidates[start : start + size]
            try:
                response = ai_batch_generator(chunk) or {}
            except Exception:
                response = {}
            batches_sent += 1
            response_map = response if isinstance(response, Mapping) else {}
            for offer in chunk:
                key = str(offer.get("offer_id"))
                raw_labels = response_map.get(key)
                if not isinstance(raw_labels, list):
                    labels_by_offer[key] = []
                    continue
                labels_by_offer[key] = [str(value) for value in raw_labels][:AI_FALLBACK_MAX_SKILLS]
        return labels_by_offer, batches_sent

    generator = ai_skill_generator or generate_ai_offer_skill_candidates
    for offer in candidates:
        key = str(offer.get("offer_id"))
        raw_labels = generator(title=str(offer.get("title") or ""), description=str(offer.get("description") or "")) or []
        labels_by_offer[key] = [str(value) for value in raw_labels][:AI_FALLBACK_MAX_SKILLS]
        batches_sent += 1
    return labels_by_offer, batches_sent


def backfill_offer_skills_with_connection(
    conn,
    *,
    clean_table: str = "clean_offers",
    offer_skills_table: str = "offer_skills",
    enrichment_version: str = ENRICHMENT_VERSION,
    canonical_builder: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ai_skill_generator: Callable[..., list[str]] | None = None,
    ai_batch_generator: Callable[[list[Mapping[str, Any]]], Mapping[str, list[str]]] | None = None,
    source: str | None = None,
    fallback_batch_size: int = DEFAULT_FALLBACK_BATCH_SIZE,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    from psycopg import sql

    ensure_offer_skills_table(conn, table_name=offer_skills_table, clean_table=clean_table)

    where_clauses: list[sql.Composable] = []
    params: list[Any] = []
    if source:
        where_clauses.append(sql.SQL("source = %s"))
        params.append(source)
    where_sql = (
        sql.SQL("WHERE ") + sql.SQL(" AND ").join(where_clauses) if where_clauses else sql.SQL("")
    )
    limit_sql = sql.SQL(" LIMIT %s") if (limit is not None and int(limit) > 0) else sql.SQL("")
    select_sql = sql.SQL(
        """
        SELECT id, source, external_id, title, description
        FROM {clean_table}
        {where_clause}
        ORDER BY id ASC
        {limit_clause}
        """
    ).format(
        clean_table=sql.Identifier(clean_table),
        where_clause=where_sql,
        limit_clause=limit_sql,
    )
    if limit is not None and int(limit) > 0:
        params.append(int(limit))

    existing_sql = sql.SQL(
        """
        SELECT COUNT(*), MIN(content_hash), MAX(content_hash), MIN(enrichment_version), MAX(enrichment_version)
        FROM {offer_skills_table}
        WHERE offer_id = %s
        """
    ).format(offer_skills_table=sql.Identifier(offer_skills_table))
    delete_sql = sql.SQL("DELETE FROM {offer_skills_table} WHERE offer_id = %s").format(
        offer_skills_table=sql.Identifier(offer_skills_table)
    )
    insert_sql = sql.SQL(
        """
        INSERT INTO {offer_skills_table} (
            offer_id, source, external_id, canonical_id, label, importance_level,
            source_method, confidence, enrichment_version, content_hash, created_at
        )
        VALUES (
            %(offer_id)s, %(source)s, %(external_id)s, %(canonical_id)s, %(label)s, %(importance_level)s,
            %(source_method)s, %(confidence)s, %(enrichment_version)s, %(content_hash)s, %(created_at)s
        )
        ON CONFLICT (offer_id, canonical_id)
        DO UPDATE SET
            source = EXCLUDED.source,
            external_id = EXCLUDED.external_id,
            label = EXCLUDED.label,
            importance_level = EXCLUDED.importance_level,
            source_method = EXCLUDED.source_method,
            confidence = EXCLUDED.confidence,
            enrichment_version = EXCLUDED.enrichment_version,
            content_hash = EXCLUDED.content_hash
        """
    ).format(offer_skills_table=sql.Identifier(offer_skills_table))

    offers_scanned = 0
    skipped_offers = 0
    now = _utc_now()

    pending: list[dict[str, Any]] = []
    ai_candidates: list[dict[str, Any]] = []

    # Pass 1: scan + deterministic + idempotency gate
    with conn.cursor() as cursor:
        cursor.execute(select_sql, tuple(params))
        rows_db = cursor.fetchall()
        for offer_id_raw, row_source, row_external_id, title, description in rows_db:
            offers_scanned += 1
            offer_id = int(offer_id_raw)
            content_hash = compute_offer_skills_content_hash(title=title, description=description)
            row_source_str = str(row_source)
            row_external_id_str = str(row_external_id)

            cursor.execute(existing_sql, (offer_id,))
            existing_count, min_hash, max_hash, min_version, max_version = cursor.fetchone()
            if (
                int(existing_count or 0) > 0
                and min_hash == content_hash
                and max_hash == content_hash
                and min_version == enrichment_version
                and max_version == enrichment_version
            ):
                skipped_offers += 1
                continue

            det_rows, base_offer = _build_deterministic_rows_for_offer(
                offer_id=offer_id,
                source=row_source_str,
                external_id=row_external_id_str,
                title=title,
                description=description,
                canonical_builder=canonical_builder,
                enrichment_version=enrichment_version,
                now=now,
                content_hash=content_hash,
            )
            needs_ai = len(det_rows) < AI_FALLBACK_MIN_SKILLS
            pending.append(
                {
                    "offer_id": offer_id,
                    "source": row_source_str,
                    "external_id": row_external_id_str,
                    "title": title or "",
                    "description": description or "",
                    "det_rows": det_rows,
                    "base_offer": base_offer,
                    "content_hash": content_hash,
                    "needs_ai": needs_ai,
                }
            )
            if needs_ai:
                ai_candidates.append(
                    {
                        "offer_id": str(offer_id),
                        "title": title or "",
                        "description": description or "",
                    }
                )

    # Pass 2: batched AI fallback (one provider call per batch when ai_batch_generator is used)
    ai_labels_by_offer, ai_batches_sent = _resolve_ai_labels_batched(
        ai_candidates,
        ai_batch_generator=ai_batch_generator,
        ai_skill_generator=ai_skill_generator,
        batch_size=fallback_batch_size,
    )

    # Pass 3: persist (delete + insert per offer that needs processing)
    offers_processed = 0
    rows_written = 0
    ai_triggered_offers = 0
    ai_added_rows = 0
    fixed_offers = 0

    with conn.cursor() as cursor:
        for item in pending:
            offer_id = int(item["offer_id"])
            content_hash = item["content_hash"]
            final_rows: list[dict[str, Any]] = list(item["det_rows"])

            if item["needs_ai"]:
                ai_triggered_offers += 1
                ai_labels = ai_labels_by_offer.get(str(offer_id)) or []
                if ai_labels:
                    ai_rows = _canonicalize_ai_labels_to_rows(
                        offer_id=offer_id,
                        source=item["source"],
                        external_id=item["external_id"],
                        base_offer=item["base_offer"],
                        ai_labels=ai_labels,
                        existing_canonical_ids={row["canonical_id"] for row in item["det_rows"]},
                        content_hash=content_hash,
                        now=now,
                        canonical_builder=canonical_builder,
                        enrichment_version=enrichment_version,
                    )
                    if ai_rows:
                        final_rows.extend(ai_rows)
                        ai_added_rows += len(ai_rows)
                        fixed_offers += 1

            offers_processed += 1
            if dry_run:
                rows_written += len(final_rows)
                continue

            cursor.execute(delete_sql, (offer_id,))
            for row in final_rows:
                cursor.execute(insert_sql, row)
                rows_written += 1

    if dry_run:
        conn.rollback()
    else:
        conn.commit()

    return {
        "offers_scanned": offers_scanned,
        "offers_processed": offers_processed,
        "skipped_offers": skipped_offers,
        "rows_written": rows_written,
        "ai_triggered_offers": ai_triggered_offers,
        "ai_batches_sent": ai_batches_sent,
        "ai_added_rows": ai_added_rows,
        "fixed_offers": fixed_offers,
        "dry_run": bool(dry_run),
    }


def backfill_offer_skills(
    *,
    database_url: str | None = None,
    clean_table: str = "clean_offers",
    offer_skills_table: str = "offer_skills",
    enrichment_version: str = ENRICHMENT_VERSION,
    source: str | None = None,
    fallback_batch_size: int = DEFAULT_FALLBACK_BATCH_SIZE,
    limit: int | None = None,
    dry_run: bool = False,
    ai_batch_generator: Callable[[list[Mapping[str, Any]]], Mapping[str, list[str]]] | None = None,
    ai_skill_generator: Callable[..., list[str]] | None = None,
) -> dict[str, Any]:
    url = (database_url or get_database_url() or "").strip()
    if not url:
        return {
            "offers_scanned": 0,
            "offers_processed": 0,
            "skipped_offers": 0,
            "rows_written": 0,
            "error": "DATABASE_URL is not set",
        }

    import psycopg

    # By default, use the batched AI generator for real backfill runs unless the
    # caller overrides with a specific generator (eg. tests).
    effective_batch_generator = ai_batch_generator
    effective_skill_generator = ai_skill_generator
    if effective_batch_generator is None and effective_skill_generator is None:
        effective_batch_generator = generate_ai_offer_skills_batch

    with psycopg.connect(url, connect_timeout=5) as conn:
        result = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=offer_skills_table,
            enrichment_version=enrichment_version,
            source=source,
            fallback_batch_size=fallback_batch_size,
            limit=limit,
            dry_run=dry_run,
            ai_batch_generator=effective_batch_generator,
            ai_skill_generator=effective_skill_generator,
        )
    result["error"] = None
    return result
