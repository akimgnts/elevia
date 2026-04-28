"""offer_skills_metier — v3 domain-aware extraction of CORE_METIER skills.

Sample-only path. Lives alongside `offer_skills_pg.py` (v2) and writes rows
under `enrichment_version = 'offer_skills_v3_metier'`. Does NOT alter scoring.

Contract per skill row:
    canonical_id, label, importance_level, skill_type,
    source_method, confidence, evidence, enrichment_version

Strict rules enforced here:
- skill_type is one of CORE_METIER / TOOL / CONTEXT / NOISE (or row is dropped)
- evidence MUST be a verbatim substring of (title + description); otherwise drop
- CORE_METIER without evidence is rejected outright (per user spec)
- 3 to 5 skills per offer, deduplicated by canonical_id
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

ENRICHMENT_VERSION_METIER = "offer_skills_v3_metier"
SOURCE_METHOD_METIER = "ai_metier_v3"

VALID_SKILL_TYPES = ("CORE_METIER", "TOOL", "CONTEXT", "NOISE")
SKILL_TYPES_SCORABLE = ("CORE_METIER", "TOOL")  # informational; scoring layer decides

MIN_SKILLS_PER_OFFER = 3
MAX_SKILLS_PER_OFFER = 5
DEFAULT_AI_TIMEOUT = 30
DEFAULT_AI_MODEL = "gpt-4o-mini"

FLAG_AI_MODEL = "ELEVIA_OFFER_SKILLS_METIER_AI_MODEL"
FLAG_AI_TIMEOUT = "ELEVIA_OFFER_SKILLS_METIER_AI_TIMEOUT"

# Reasons to drop a skill record. Used by tests + audit traces.
class DropReason:
    INVALID_TYPE = "invalid_skill_type"
    MISSING_EVIDENCE = "missing_evidence"
    EVIDENCE_NOT_IN_OFFER = "evidence_not_in_offer"
    CORE_METIER_WITHOUT_EVIDENCE = "core_metier_without_evidence"
    EMPTY_LABEL = "empty_label"
    DUPLICATE = "duplicate_canonical_id"
    EXCEEDS_LIMIT = "exceeds_max_skills"


# ---------- Prompt ---------------------------------------------------------

SYSTEM_PROMPT = """You are a senior recruiter auditing job offers in the {domain} domain.

TASK
Extract 3 to 5 skills that this specific role REQUIRES. Output strict JSON only.

CLASSIFY each skill into exactly one of:
- CORE_METIER : a domain-specific competence the role performs day-to-day.
                 Examples (data): "SQL querying", "dashboard development", "data modeling".
                 Examples (sales): "lead qualification", "B2B prospecting", "account management".
                 Examples (finance): "financial modeling", "budget control", "risk analysis".
                 Examples (hr): "candidate sourcing", "talent assessment", "onboarding programs".
                 Examples (engineering): "backend API development", "CI/CD pipelines", "embedded systems".
- TOOL        : a specific software, language, or platform the role uses.
                 Examples: "Salesforce", "SAP", "Excel macros", "Tableau", "Python", "Kubernetes".
- CONTEXT     : business framing that is NOT a skill itself.
                 Examples: "international environment", "B2B SaaS market", "regulated industry".
- NOISE       : generic filler with no operational meaning.
                 Examples: "communication", "teamwork", "motivation", "project management" (when used as filler), "compliance" (when used as filler).

STRICT RULES (violations => drop the entry):
1. Each skill MUST include "evidence": a VERBATIM quote (<=120 chars) from the title or description that justifies it. No paraphrasing. No invention.
2. CORE_METIER without clear evidence is INVALID. Return fewer skills rather than guess.
3. Reject generic terms ("compliance", "business intelligence", "process optimization", "project management", "communication", "teamwork") as CORE_METIER. They are NOISE unless the offer explicitly grounds them in a specific domain task — in which case classify as CORE_METIER and quote the grounding.
4. Prefer multi-word, domain-specific labels.
5. No duplicates. Maximum 5 skills.

OUTPUT JSON (strict):
{{
  "skills": [
    {{
      "label": "string (concise skill name, 2-6 words)",
      "skill_type": "CORE_METIER" | "TOOL" | "CONTEXT" | "NOISE",
      "evidence": "verbatim quote from offer text",
      "confidence": 0.0
    }}
  ]
}}

If the offer is too vague to extract evidence-backed skills, return {{"skills": []}}.
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify_to_canonical_id(label: str) -> str:
    """Build a stable, namespaced canonical_id from a label."""
    s = _SLUG_NON_ALNUM.sub("_", str(label or "").lower()).strip("_")
    return f"metier:{s}" if s else ""


def _evidence_in_offer(evidence: str, *, title: str, description: str) -> bool:
    if not evidence:
        return False
    haystack = f"{title or ''}\n{description or ''}".lower()
    return evidence.strip().lower() in haystack


def _normalize_label(label: str) -> str:
    return " ".join(str(label or "").strip().split())


def _coerce_confidence(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def _importance_for_type(skill_type: str) -> str:
    # Only CORE_METIER maps to CORE; TOOL is operationally important but not
    # a metier skill, so it stays SECONDARY. CONTEXT/NOISE are SECONDARY too
    # (importance_level is constrained to CORE/SECONDARY by the v2 schema).
    return "CORE" if skill_type == "CORE_METIER" else "SECONDARY"


# ---------- AI client ------------------------------------------------------


_OPENAI_CLIENT = None
_OPENAI_CLIENT_KEY = None


def _get_openai_client():
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None, None
    from openai import OpenAI

    global _OPENAI_CLIENT, _OPENAI_CLIENT_KEY
    if _OPENAI_CLIENT is None or _OPENAI_CLIENT_KEY != api_key:
        timeout = float(os.getenv(FLAG_AI_TIMEOUT, str(DEFAULT_AI_TIMEOUT)))
        _OPENAI_CLIENT = OpenAI(api_key=api_key, timeout=timeout)
        _OPENAI_CLIENT_KEY = api_key
    model = os.getenv(FLAG_AI_MODEL) or os.getenv("OPENAI_MODEL") or DEFAULT_AI_MODEL
    return _OPENAI_CLIENT, model


def call_metier_extraction(
    *,
    title: str,
    description: str,
    domain_tag: str,
) -> dict[str, Any]:
    """Default AI caller. Raises on transport/parse errors so the caller decides."""
    client, model = _get_openai_client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY not set")

    system_prompt = SYSTEM_PROMPT.format(domain=domain_tag or "general")
    user_payload = json.dumps(
        {"title": title or "", "description": description or "", "domain": domain_tag or ""},
        ensure_ascii=False,
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


# ---------- Validation + row build -----------------------------------------


def validate_skill_entries(
    entries: list[Mapping[str, Any]],
    *,
    title: str,
    description: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Filter raw AI entries against strict rules. Returns (kept, dropped)."""
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for raw in entries or []:
        if not isinstance(raw, Mapping):
            dropped.append({"raw": raw, "reason": DropReason.EMPTY_LABEL})
            continue

        label = _normalize_label(raw.get("label"))
        skill_type = str(raw.get("skill_type") or "").strip().upper()
        evidence = _normalize_label(raw.get("evidence"))
        confidence = _coerce_confidence(raw.get("confidence"))

        if not label:
            dropped.append({"label": label, "skill_type": skill_type, "reason": DropReason.EMPTY_LABEL})
            continue
        if skill_type not in VALID_SKILL_TYPES:
            dropped.append({"label": label, "skill_type": skill_type, "reason": DropReason.INVALID_TYPE})
            continue
        if not evidence:
            reason = (
                DropReason.CORE_METIER_WITHOUT_EVIDENCE
                if skill_type == "CORE_METIER"
                else DropReason.MISSING_EVIDENCE
            )
            # Per spec, missing evidence is a hard reject for ALL types — we want
            # an audit trail of what the offer actually says.
            dropped.append({"label": label, "skill_type": skill_type, "reason": reason})
            continue
        if not _evidence_in_offer(evidence, title=title, description=description):
            dropped.append(
                {"label": label, "skill_type": skill_type, "reason": DropReason.EVIDENCE_NOT_IN_OFFER, "evidence": evidence}
            )
            continue

        canonical_id = slugify_to_canonical_id(label)
        if not canonical_id:
            dropped.append({"label": label, "skill_type": skill_type, "reason": DropReason.EMPTY_LABEL})
            continue
        if canonical_id in seen_ids:
            dropped.append({"label": label, "skill_type": skill_type, "reason": DropReason.DUPLICATE})
            continue
        seen_ids.add(canonical_id)

        kept.append(
            {
                "canonical_id": canonical_id,
                "label": label,
                "skill_type": skill_type,
                "evidence": evidence[:120],
                "confidence": confidence,
                "importance_level": _importance_for_type(skill_type),
            }
        )

    if len(kept) > MAX_SKILLS_PER_OFFER:
        for extra in kept[MAX_SKILLS_PER_OFFER:]:
            dropped.append(
                {"label": extra["label"], "skill_type": extra["skill_type"], "reason": DropReason.EXCEEDS_LIMIT}
            )
        kept = kept[:MAX_SKILLS_PER_OFFER]

    return kept, dropped


def build_metier_rows(
    *,
    offer_id: int,
    source: str,
    external_id: str,
    title: str,
    description: str,
    domain_tag: str,
    ai_caller: Callable[..., Mapping[str, Any]] | None = None,
    enrichment_version: str = ENRICHMENT_VERSION_METIER,
    source_method: str = SOURCE_METHOD_METIER,
    content_hash: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the metier prompt for one offer, validate, and return persistable rows.

    Returns (rows, audit) where audit captures dropped entries + raw response.
    """
    caller = ai_caller or call_metier_extraction
    now = _utc_now_iso()

    raw_response: dict[str, Any] = {}
    error: str | None = None
    try:
        raw_response = caller(title=title or "", description=description or "", domain_tag=domain_tag or "") or {}
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    raw_skills = []
    if isinstance(raw_response, Mapping):
        candidates = raw_response.get("skills")
        if isinstance(candidates, list):
            raw_skills = candidates

    kept, dropped = validate_skill_entries(raw_skills, title=title or "", description=description or "")

    rows: list[dict[str, Any]] = []
    for entry in kept:
        rows.append(
            {
                "offer_id": int(offer_id),
                "source": str(source),
                "external_id": str(external_id),
                "canonical_id": entry["canonical_id"],
                "label": entry["label"],
                "importance_level": entry["importance_level"],
                "skill_type": entry["skill_type"],
                "source_method": source_method,
                "confidence": entry["confidence"],
                "evidence": entry["evidence"],
                "enrichment_version": enrichment_version,
                "content_hash": content_hash or "",
                "created_at": now,
            }
        )

    audit = {
        "offer_id": offer_id,
        "external_id": external_id,
        "domain_tag": domain_tag,
        "kept_count": len(rows),
        "dropped_count": len(dropped),
        "dropped": dropped,
        "raw_response": raw_response if not error else {"error": error},
        "error": error,
    }
    return rows, audit


# ---------- DB persistence -------------------------------------------------


METIER_INSERT_SQL = """
INSERT INTO offer_skills (
    offer_id, source, external_id, canonical_id, label, importance_level,
    skill_type, source_method, confidence, evidence,
    enrichment_version, content_hash, created_at
)
VALUES (
    %(offer_id)s, %(source)s, %(external_id)s, %(canonical_id)s, %(label)s, %(importance_level)s,
    %(skill_type)s, %(source_method)s, %(confidence)s, %(evidence)s,
    %(enrichment_version)s, %(content_hash)s, %(created_at)s
)
ON CONFLICT (offer_id, canonical_id, enrichment_version)
DO UPDATE SET
    source = EXCLUDED.source,
    external_id = EXCLUDED.external_id,
    label = EXCLUDED.label,
    importance_level = EXCLUDED.importance_level,
    skill_type = EXCLUDED.skill_type,
    source_method = EXCLUDED.source_method,
    confidence = EXCLUDED.confidence,
    evidence = EXCLUDED.evidence,
    content_hash = EXCLUDED.content_hash
"""


def persist_metier_rows(conn, rows: list[Mapping[str, Any]], *, dry_run: bool = False) -> int:
    """Insert/upsert v3 metier rows. Returns number of rows written."""
    if not rows:
        return 0
    written = 0
    with conn.cursor() as cursor:
        for row in rows:
            cursor.execute(METIER_INSERT_SQL, dict(row))
            written += 1
    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return written
