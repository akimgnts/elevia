from __future__ import annotations

from typing import Iterable

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key

CONFIDENCE_THRESHOLD = 0.6
MAX_ADDED_SKILLS = 5


def infer_skills_from_occupation(
    candidate_occupations: Iterable[dict],
    extracted_skills: Iterable[str],
    occupation_profiles: dict[str, dict[str, object]],
    *,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    max_added_skills: int = MAX_ADDED_SKILLS,
) -> list[dict[str, object]]:
    extracted_keys = {normalize_canonical_key(skill) for skill in (extracted_skills or []) if isinstance(skill, str)}
    store = get_canonical_store()
    inferred: list[dict[str, object]] = []

    for candidate in candidate_occupations or []:
        confidence = float(candidate.get("score") or 0.0)
        if confidence < confidence_threshold:
            continue
        code = candidate.get("onet_code")
        profile = occupation_profiles.get(code or "", {})
        for mapped in profile.get("mapped_skills") or []:
            label = mapped.get("canonical_label") or mapped.get("skill_name")
            key = normalize_canonical_key(label)
            cid = mapped.get("canonical_skill_id")
            if not key or key in extracted_keys:
                continue
            if cid and cid in extracted_keys:
                continue
            if any(item.get("canonical_skill_id") == cid for item in inferred if cid):
                continue
            display_label = label
            if cid and cid in store.id_to_skill:
                display_label = store.id_to_skill[cid].get("label", label)
            inferred.append(
                {
                    "canonical_skill_id": cid,
                    "label": display_label,
                    "source_onet_code": code,
                    "source_occupation_title": candidate.get("occupation_title"),
                    "source_table": mapped.get("source_table"),
                    "confidence": min(confidence, float(mapped.get("confidence_score") or confidence)),
                    "inferred": True,
                }
            )
            if len(inferred) >= max_added_skills:
                return inferred
    return inferred
