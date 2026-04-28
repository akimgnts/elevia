"""offer_skills_fallback — v3 fallback extraction for offers with 0 metier skills.

Lighter, more relaxed extraction for edge-case offers where v3_metier returned 0 skills.
Replaces strictness with breadth: accepts looser evidence, shorter extractions.

Constraints:
- max 3 skills (vs v3's 5)
- evidence mandatory (same as v3)
- skill_type simplified: CORE_METIER / TOOL / CONTEXT only (no NOISE)
- prefers TOOL/CONTEXT over CORE_METIER when confidence low
- enrichment_version = 'offer_skills_v3_fallback'

NEVER modifies v3_metier. Insert only if no v3_metier rows exist for the offer.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

ENRICHMENT_VERSION_FALLBACK = "offer_skills_v3_fallback"
SOURCE_METHOD_FALLBACK = "ai_metier_v3_fallback"

MIN_SKILLS_PER_OFFER = 1
MAX_SKILLS_PER_OFFER = 3
DEFAULT_AI_TIMEOUT = 30
DEFAULT_AI_MODEL = "gpt-4o-mini"

FLAG_AI_MODEL = "ELEVIA_OFFER_SKILLS_FALLBACK_AI_MODEL"
FLAG_AI_TIMEOUT = "ELEVIA_OFFER_SKILLS_FALLBACK_AI_TIMEOUT"

VALID_SKILL_TYPES = ("CORE_METIER", "TOOL", "CONTEXT")


class DropReason:
    INVALID_TYPE = "invalid_skill_type"
    MISSING_EVIDENCE = "missing_evidence"
    EVIDENCE_NOT_IN_OFFER = "evidence_not_in_offer"
    EMPTY_LABEL = "empty_label"
    DUPLICATE = "duplicate_canonical_id"
    EXCEEDS_LIMIT = "exceeds_max_skills"


# ---------- Prompt ---------------------------------------------------------

SYSTEM_PROMPT = """You are a recruiter extracting job requirements from offers where strict extraction failed.

TASK
Extract 1 to 3 skills from this role. Output strict JSON only.

CLASSIFY into exactly one of:
- CORE_METIER : a domain-specific competence or responsibility
- TOOL        : a software, language, or platform
- CONTEXT     : business framing or environment (if no core skills available)

RELAXED RULES (vs strict v3):
1. Accept evidence: explicit phrase OR strong contextual cue (not just verbatim substring, but still grounded).
2. Shorter extractions OK: 1-3 skills (vs strict 3-5).
3. Prefer TOOL/CONTEXT over weak CORE_METIER.
4. No NOISE classification (reject filler entirely).

OUTPUT JSON (strict):
{{
  "skills": [
    {{
      "label": "string (skill name)",
      "skill_type": "CORE_METIER" | "TOOL" | "CONTEXT",
      "evidence": "justification from offer text",
      "confidence": 0.0 to 1.0
    }}
  ]
}}

If extraction is still not possible, return {{"skills": []}}.
"""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify_to_canonical_id(label: str) -> str:
    """Build a stable, namespaced canonical_id from a label."""
    s = _SLUG_NON_ALNUM.sub("_", str(label or "").lower()).strip("_")
    return f"metier:{s}" if s else ""


def _evidence_in_offer(evidence: str, *, title: str, description: str) -> bool:
    """Relaxed evidence check: is the evidence grounded in offer text?"""
    if not evidence:
        return False
    haystack = f"{title or ''}\n{description or ''}".lower()
    # Accept if evidence is present (exact substring OR strong contextual match)
    evidence_lower = evidence.strip().lower()
    if evidence_lower in haystack:
        return True
    # Fallback: check if key words from evidence appear in text
    words = evidence_lower.split()
    if len(words) >= 2:
        # Accept if 70%+ of words are present
        found = sum(1 for w in words if w in haystack)
        return found / len(words) >= 0.7
    return False


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


def call_fallback_extraction(
    *,
    title: str,
    description: str,
    domain_tag: str,
) -> dict[str, Any]:
    """AI caller for fallback extraction."""
    client, model = _get_openai_client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY not set")

    system_prompt = SYSTEM_PROMPT
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
    """Filter fallback AI entries. Returns (kept, dropped)."""
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
            dropped.append({"label": label, "skill_type": skill_type, "reason": DropReason.MISSING_EVIDENCE})
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


def build_fallback_rows(
    *,
    offer_id: int,
    source: str,
    external_id: str,
    title: str,
    description: str,
    domain_tag: str,
    ai_caller: Callable[..., Mapping[str, Any]] | None = None,
    enrichment_version: str = ENRICHMENT_VERSION_FALLBACK,
    source_method: str = SOURCE_METHOD_FALLBACK,
    content_hash: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run fallback extraction for one offer. Returns (rows, audit)."""
    caller = ai_caller or call_fallback_extraction
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

FALLBACK_INSERT_SQL = """
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


def persist_fallback_rows(conn, rows: list[Mapping[str, Any]], *, dry_run: bool = False) -> int:
    """Insert/upsert fallback rows. Returns number of rows written."""
    if not rows:
        return 0
    written = 0
    with conn.cursor() as cursor:
        for row in rows:
            cursor.execute(FALLBACK_INSERT_SQL, dict(row))
            written += 1
    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    return written
