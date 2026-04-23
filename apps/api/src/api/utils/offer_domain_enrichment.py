from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, Mapping


DOMAIN_TAXONOMY = (
    "data",
    "finance",
    "hr",
    "marketing",
    "sales",
    "supply",
    "engineering",
    "operations",
    "admin",
    "legal",
    "other",
)

DOMAIN_STRONG_PHRASES: dict[str, tuple[str, ...]] = {
    "sales": ("business development", "account manager", "key account", "sales manager", "client relationship"),
    "finance": ("contrôle de gestion", "controle de gestion", "contrôleur de gestion", "controleur de gestion", "financial controller", "business controller", "comptabilité", "accounting"),
    "data": ("data analyst", "data scientist", "business intelligence", "data engineer", "machine learning"),
    "hr": ("ressources humaines", "human resources", "talent acquisition", "chargé de recrutement", "recruitment specialist"),
    "supply": ("supply chain", "logistique", "procurement", "approvisionnement"),
    "engineering": ("software engineer", "backend developer", "frontend developer", "full stack", "devops"),
    "marketing": ("digital marketing", "marketing manager", "content marketing", "seo specialist"),
    "operations": ("project manager", "chef de projet", "operations manager"),
    "admin": ("office manager", "assistant administratif", "administrative assistant"),
    "legal": ("legal counsel", "compliance officer", "juriste"),
}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "data": ("sql", "python", "data", "analyst", "analyste", "bi", "tableau", "power bi", "reporting", "dashboard"),
    "finance": ("audit", "accounting", "controlling", "finance", "budget", "consolidation", "fiscal", "controller", "controle", "contrôle", "controleur", "contrôleur"),
    "hr": ("recruitment", "recrutement", "talent", "hr", "payroll", "onboarding", "ressources humaines"),
    "marketing": ("marketing", "seo", "content", "campaign", "branding", "communication"),
    "sales": ("sales", "business", "client", "commercial", "vente", "account", "revenue"),
    "supply": ("supply", "logistics", "logistique", "procurement", "warehouse", "transport", "buyer", "acheteur", "fournisseur"),
    "engineering": ("engineer", "ingenieur", "ingénieur", "developer", "developpeur", "développeur", "software", "backend", "frontend", "devops", "automation", "automatisation"),
    "operations": ("operations", "process", "project", "coordination", "manager"),
    "admin": ("assistant", "office", "support", "administratif", "administrator", "administration", "gestionnaire"),
    "legal": ("legal", "compliance", "law", "contract", "juridique"),
}

LOW_CONFIDENCE_THRESHOLD = 2
FLAG_DOMAIN_AI_FALLBACK = "ELEVIA_DOMAIN_AI_FALLBACK"
FLAG_DOMAIN_AI_MODEL = "ELEVIA_DOMAIN_AI_MODEL"
FLAG_DOMAIN_AI_TIMEOUT = "ELEVIA_DOMAIN_AI_TIMEOUT"

_SPACE_RE = re.compile(r"\s+")
_STRONG_DOMAINS = ("finance", "data", "sales")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def domain_ai_fallback_enabled() -> bool:
    return os.getenv(FLAG_DOMAIN_AI_FALLBACK, "0").strip() == "1"


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return _SPACE_RE.sub(" ", text)


def _contains_keyword(text: str, keyword: str) -> bool:
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return False
    if " " in normalized_keyword:
        return normalized_keyword in text
    return re.search(rf"\b{re.escape(normalized_keyword)}\b", text) is not None


def compute_offer_content_hash(*, title: str | None, description: str | None) -> str:
    payload = f"{_normalize_text(title)}||{_normalize_text(description)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def classify_offer_domain_rules(*, title: str | None, description: str | None, skills_text: str | None = None) -> dict[str, Any]:
    title_text = _normalize_text(title)
    description_text = _normalize_text(description)
    skills_text_normalized = _normalize_text(skills_text)
    text = " ".join(part for part in (title_text, description_text, skills_text_normalized) if part)

    for domain, phrases in DOMAIN_STRONG_PHRASES.items():
        for phrase in phrases:
            if _contains_keyword(text, phrase):
                return {
                    "domain_tag": domain,
                    "confidence": 0.9,
                    "method": "rules",
                    "evidence": [_normalize_text(phrase)],
                    "needs_ai_review": False,
                }

    if _contains_keyword(text, "business development"):
        return {
            "domain_tag": "sales",
            "confidence": 0.9,
            "method": "rules",
            "evidence": ["business development"],
            "needs_ai_review": False,
        }
    if _contains_keyword(text, "controller") or _contains_keyword(text, "controle") or _contains_keyword(text, "contrôle"):
        return {
            "domain_tag": "finance",
            "confidence": 0.9,
            "method": "rules",
            "evidence": ["controller" if _contains_keyword(text, "controller") else "controle"],
            "needs_ai_review": False,
        }

    domain_scores: dict[str, int] = {}
    domain_evidence: dict[str, list[str]] = {}

    for domain in DOMAIN_TAXONOMY:
        if domain == "other":
            continue
        score = 0
        matched: list[str] = []
        for keyword in DOMAIN_KEYWORDS.get(domain, ()):
            if _contains_keyword(title_text, keyword):
                score += 2
                matched.append(keyword)
            elif _contains_keyword(description_text, keyword) or _contains_keyword(skills_text_normalized, keyword):
                score += 1
                matched.append(keyword)
        domain_scores[domain] = score
        domain_evidence[domain] = matched

    data_evidence = domain_evidence.get("data", [])
    if data_evidence and set(data_evidence) <= {"data"}:
        domain_scores["data"] = 0
        domain_evidence["data"] = []

    sales_evidence = domain_evidence.get("sales", [])
    if sales_evidence and set(sales_evidence) <= {"business", "client", "account"}:
        domain_scores["sales"] = min(domain_scores["sales"], 1)

    if domain_scores.get("operations", 0) > 0 and any(domain_scores.get(domain, 0) > 0 for domain in _STRONG_DOMAINS):
        domain_scores["operations"] = 0
        domain_evidence["operations"] = []

    top_score = max(domain_scores.values(), default=0)
    if top_score <= 0:
        return {
            "domain_tag": "other",
            "confidence": 0.0,
            "method": "rules",
            "evidence": ["no_rule_match"],
            "needs_ai_review": True,
        }

    tied_domains = [domain for domain in DOMAIN_TAXONOMY if domain in domain_scores and domain_scores[domain] == top_score]
    selected_domain = tied_domains[0]
    total_hits = sum(domain_scores.values()) or 1
    confidence = round(top_score / total_hits, 4)
    needs_ai_review = len(tied_domains) > 1 or top_score < LOW_CONFIDENCE_THRESHOLD

    return {
        "domain_tag": selected_domain,
        "confidence": confidence,
        "method": "rules",
        "evidence": domain_evidence.get(selected_domain, []),
        "needs_ai_review": needs_ai_review,
    }


def classify_offer_domain_with_ai(*, title: str | None, description: str | None, skills_text: str | None = None) -> dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=float(os.getenv(FLAG_DOMAIN_AI_TIMEOUT, "20")))
    model = os.getenv(FLAG_DOMAIN_AI_MODEL) or "gpt-4o-mini"
    prompt = (
        "Classify the job offer into exactly one domain from: "
        + ", ".join(DOMAIN_TAXONOMY)
        + ".\n\nRules:\n"
          "- Choose ONLY one domain\n"
          "- Do NOT invent categories\n"
          "- Use only information present in the text\n"
          "- Prefer dominant business function over generic terms\n\n"
          "Return JSON only:\n"
          '{\n  "domain_tag": "<one domain>",\n  "confidence": 0.0,\n  "evidence": ["word or phrase from input"]\n}'
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
    domain_tag = str(payload.get("domain_tag") or "").strip().lower()
    if domain_tag not in DOMAIN_TAXONOMY:
        raise RuntimeError(f"invalid domain_tag from ai: {domain_tag}")
    confidence = float(payload.get("confidence") or 0.0)
    evidence = payload.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = []
    return {
        "domain_tag": domain_tag,
        "confidence": max(0.0, min(1.0, confidence)),
        "method": "ai_fallback",
        "evidence": [str(item).strip() for item in evidence if str(item).strip()],
        "needs_ai_review": False,
    }


def normalize_ai_domain_result(result: Mapping[str, Any]) -> dict[str, Any]:
    domain_tag = str(result.get("domain_tag") or "").strip().lower()
    if domain_tag not in DOMAIN_TAXONOMY:
        raise RuntimeError(f"invalid domain_tag from ai: {domain_tag}")
    if "confidence" not in result:
        raise RuntimeError("missing confidence from ai")
    if "evidence" not in result:
        raise RuntimeError("missing evidence from ai")
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        raise RuntimeError("invalid evidence from ai")
    normalized_evidence = [str(item).strip() for item in evidence if str(item).strip()]
    if not normalized_evidence:
        raise RuntimeError("empty evidence from ai")
    return {
        "domain_tag": domain_tag,
        "confidence": max(0.0, min(1.0, float(result["confidence"] or 0.0))),
        "method": "ai_fallback",
        "evidence": normalized_evidence,
        "needs_ai_review": False,
    }


def ensure_offer_domain_enrichment_table(conn, *, table_name: str = "offer_domain_enrichment") -> None:
    from psycopg import sql

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    domain_tag TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                    method TEXT NOT NULL,
                    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
                    needs_ai_review BOOLEAN NOT NULL DEFAULT FALSE,
                    content_hash TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT {uq_name} UNIQUE (source, external_id)
                )
                """
            ).format(
                table_name=sql.Identifier(table_name),
                uq_name=sql.Identifier(f"{table_name}_source_external_id_key"),
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS content_hash TEXT").format(
                table_name=sql.Identifier(table_name)
            )
        )


def classify_and_persist_business_france_offer_domains_with_connection(
    conn,
    *,
    clean_table: str = "clean_offers",
    enrichment_table: str = "offer_domain_enrichment",
    enable_ai_fallback: bool | None = None,
    ai_classifier: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, int]:
    from psycopg import sql
    from psycopg.types.json import Json

    ensure_offer_domain_enrichment_table(conn, table_name=enrichment_table)
    use_ai = domain_ai_fallback_enabled() if enable_ai_fallback is None else enable_ai_fallback
    classifier = ai_classifier or classify_offer_domain_with_ai
    processed_count = 0
    classified_count = 0
    skipped_count = 0
    reclassified_count = 0
    ai_fallback_count = 0
    ai_processed_count = 0
    ai_success_count = 0
    ai_failed_count = 0
    needs_review_count = 0

    select_sql = sql.SQL(
        """
        SELECT
            c.external_id,
            c.title,
            c.description,
            e.domain_tag,
            e.method,
            e.needs_ai_review,
            e.content_hash
        FROM {clean_table} c
        LEFT JOIN {enrichment_table} e
          ON e.source = c.source AND e.external_id = c.external_id
        WHERE c.source = %s
        ORDER BY c.external_id
        """
    ).format(
        clean_table=sql.Identifier(clean_table),
        enrichment_table=sql.Identifier(enrichment_table),
    )

    upsert_sql = sql.SQL(
        """
        INSERT INTO {enrichment_table} (
            source, external_id, domain_tag, confidence, method, evidence, needs_ai_review, content_hash, created_at, updated_at
        )
        VALUES (
            %(source)s, %(external_id)s, %(domain_tag)s, %(confidence)s, %(method)s, %(evidence)s::jsonb, %(needs_ai_review)s, %(content_hash)s, %(created_at)s, %(updated_at)s
        )
        ON CONFLICT (source, external_id)
        DO UPDATE SET
            domain_tag = EXCLUDED.domain_tag,
            confidence = EXCLUDED.confidence,
            method = EXCLUDED.method,
            evidence = EXCLUDED.evidence,
            needs_ai_review = EXCLUDED.needs_ai_review,
            content_hash = EXCLUDED.content_hash,
            updated_at = EXCLUDED.updated_at
        """
    ).format(enrichment_table=sql.Identifier(enrichment_table))

    now = _utc_now()
    with conn.cursor() as cursor:
        cursor.execute(select_sql, ("business_france",))
        rows = cursor.fetchall()
        for external_id, title, description, existing_domain_tag, existing_method, existing_needs_ai_review, existing_content_hash in rows:
            processed_count += 1
            content_hash = compute_offer_content_hash(title=title, description=description)
            existing_valid = existing_domain_tag in DOMAIN_TAXONOMY
            existing_is_ai_final = existing_method == "ai_fallback" and existing_valid
            existing_is_rules_final = existing_method == "rules" and existing_valid and existing_needs_ai_review is False
            if existing_content_hash == content_hash and (existing_is_ai_final or existing_is_rules_final):
                skipped_count += 1
                continue
            result = classify_offer_domain_rules(title=title, description=description)
            if result["needs_ai_review"] is True and use_ai:
                ai_processed_count += 1
                try:
                    result = normalize_ai_domain_result(
                        classifier(title=title, description=description)
                    )
                    ai_fallback_count += 1
                    ai_success_count += 1
                except Exception:
                    ai_failed_count += 1
                    pass
            if result["needs_ai_review"]:
                needs_review_count += 1
            classified_count += 1
            if existing_content_hash is not None and existing_content_hash != content_hash:
                reclassified_count += 1
            cursor.execute(
                upsert_sql,
                {
                    "source": "business_france",
                    "external_id": str(external_id),
                    "domain_tag": result["domain_tag"],
                    "confidence": float(result["confidence"]),
                    "method": result["method"],
                    "evidence": Json(result.get("evidence") or []),
                    "needs_ai_review": bool(result["needs_ai_review"]),
                    "content_hash": content_hash,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            conn.commit()
        cursor.execute(
            sql.SQL(
                "SELECT COUNT(*) FROM {enrichment_table} WHERE source = %s AND needs_ai_review = TRUE"
            ).format(enrichment_table=sql.Identifier(enrichment_table)),
            ("business_france",),
        )
        remaining_needs_review = int(cursor.fetchone()[0])
    conn.commit()
    return {
        "processed_count": processed_count,
        "classified_count": classified_count,
        "skipped_count": skipped_count,
        "reclassified_count": reclassified_count,
        "ai_processed_count": ai_processed_count,
        "ai_success_count": ai_success_count,
        "ai_failed_count": ai_failed_count,
        "ai_fallback_count": ai_fallback_count,
        "needs_review_count": needs_review_count,
        "remaining_needs_review": remaining_needs_review,
    }


def classify_and_persist_business_france_offer_domains(
    *,
    database_url: str | None = None,
    enable_ai_fallback: bool | None = None,
) -> dict[str, Any]:
    url = (database_url or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return {
            "processed_count": 0,
            "classified_count": 0,
            "skipped_count": 0,
            "reclassified_count": 0,
            "ai_processed_count": 0,
            "ai_success_count": 0,
            "ai_failed_count": 0,
            "ai_fallback_count": 0,
            "needs_review_count": 0,
            "remaining_needs_review": 0,
            "error": "DATABASE_URL is not set",
        }

    import psycopg

    with psycopg.connect(url) as conn:
        result = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            enable_ai_fallback=enable_ai_fallback,
        )
    result["error"] = None
    return result
