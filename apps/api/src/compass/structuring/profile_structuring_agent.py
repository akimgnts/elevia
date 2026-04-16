from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from documents.career_profile import CareerExperience, CareerProfile, CareerSkillSelection

from .skill_link_builder import build_skill_links_for_experience


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = re.sub(r"\s+", " ", str(value or "").strip())
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _coerce_career_profile(data: dict[str, Any]) -> CareerProfile:
    return CareerProfile.model_validate(data or {})


def _normalize_responsibilities(exp: CareerExperience) -> CareerExperience:
    exp.responsibilities = _dedupe_strings(exp.responsibilities)
    exp.tools = _dedupe_strings(exp.tools)
    exp.skills = _dedupe_strings(exp.skills)
    return exp


def _experience_signal_blob(exp: CareerExperience) -> str:
    return " ".join(
        [
            *exp.responsibilities,
            *exp.tools,
            *exp.skills,
            exp.title,
            exp.company,
        ]
    ).strip().lower()


def _merge_canonical_skills(
    exp: CareerExperience,
    canonical_skills: list[dict[str, Any]],
) -> CareerExperience:
    seen = {_canon(skill.label) for skill in exp.canonical_skills_used if skill.label}
    signal_blob = _experience_signal_blob(exp)

    for item in canonical_skills:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        label_key = _canon(label)
        if label_key in seen:
            continue

        raw = str(item.get("raw") or "").strip().lower()
        raw_match = bool(raw and raw in signal_blob)
        label_match = label.lower() in signal_blob
        tool_match = any(label_key == _canon(tool) for tool in exp.tools)
        skill_match = any(label_key == _canon(skill) for skill in exp.skills)

        if raw_match or label_match or tool_match or skill_match:
            exp.canonical_skills_used.append(
                CareerSkillSelection(
                    label=label,
                    uri=str(item.get("uri") or item.get("canonical_id") or "").strip() or None,
                )
            )
            seen.add(label_key)
    return exp


def _build_canonical_candidates(unresolved: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in unresolved or []:
        raw = str(item.get("raw") or item.get("value") or "").strip() if isinstance(item, dict) else str(item or "").strip()
        if not raw:
            continue
        normalized = _canon(raw)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(
            {
                "raw_value": raw,
                "normalized_value": normalized,
                "type": "tool" if any(token in normalized for token in ("excel", "power bi", "powerbi", "sql", "python")) else "alias",
                "confidence": 0.6,
                "reason": "unresolved parsing signal kept for canonical review",
            }
        )
    return out


def _build_uncertain_links(exp: CareerExperience, experience_index: int) -> list[dict[str, Any]]:
    if len(exp.canonical_skills_used) <= 1:
        return []
    if exp.skill_links:
        return []
    if not exp.tools:
        return []
    return [
        {
            "experience_index": experience_index,
            "tool": tool,
            "candidate_skills": [skill.label for skill in exp.canonical_skills_used],
            "reason": "tool could not be attached with strong evidence",
        }
        for tool in exp.tools
    ]


def _build_questions(exp: CareerExperience, experience_index: int, uncertain_links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if uncertain_links:
        questions.append(
            {
                "type": "tool",
                "experience_index": experience_index,
                "question": "Quel outil principal utilisiez-vous pour cette expérience ?",
            }
        )
    if exp.canonical_skills_used and not exp.skill_links:
        questions.append(
            {
                "type": "context",
                "experience_index": experience_index,
                "question": "Quel était le contexte principal de cette expérience ?",
            }
        )
    if exp.autonomy_level is None:
        questions.append(
            {
                "type": "autonomy",
                "experience_index": experience_index,
                "question": "Quel niveau d'autonomie aviez-vous sur cette expérience ?",
            }
        )
    return questions[:5]


class ProfileStructuringAgent:
    def __init__(self, mode: str = "deterministic"):
        if mode != "deterministic":
            raise ValueError("Only deterministic mode is supported")
        self.mode = mode

    def run(self, profile_input: dict) -> dict:
        payload = deepcopy(profile_input or {})
        career_profile = _coerce_career_profile(payload.get("career_profile") or {})
        canonical_skills = [
            item
            for item in list(payload.get("canonical_skills") or [])
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        ]
        unresolved = list(payload.get("unresolved") or [])
        removed = list(payload.get("removed") or payload.get("generic_filter_removed") or [])

        used_signals: list[dict[str, Any]] = []
        uncertain_links: list[dict[str, Any]] = []
        questions_for_user: list[dict[str, Any]] = []

        for experience_index, exp in enumerate(career_profile.experiences):
            _normalize_responsibilities(exp)
            _merge_canonical_skills(exp, canonical_skills)
            exp.skill_links = build_skill_links_for_experience(exp)

            for link in exp.skill_links:
                used_signals.append(
                    {
                        "experience_index": experience_index,
                        "skill": link.skill.label,
                        "tools": [tool.label for tool in link.tools],
                        "context": link.context,
                    }
                )

            exp_uncertain_links = _build_uncertain_links(exp, experience_index)
            uncertain_links.extend(exp_uncertain_links)
            questions_for_user.extend(_build_questions(exp, experience_index, exp_uncertain_links))

        experiences_processed = len(career_profile.experiences)
        skill_links_created = sum(len(exp.skill_links) for exp in career_profile.experiences)
        experiences_with_links = sum(1 for exp in career_profile.experiences if exp.skill_links)
        canonical_candidates = _build_canonical_candidates(unresolved)
        unresolved_candidates = [
            {"raw_value": item.get("raw") or item.get("value") or str(item)}
            for item in unresolved
        ]

        structuring_report = {
            "used_signals": used_signals,
            "uncertain_links": uncertain_links,
            "questions_for_user": questions_for_user,
            "canonical_candidates": canonical_candidates,
            "rejected_noise": removed,
            "unresolved_candidates": unresolved_candidates,
            "stats": {
                "experiences_processed": experiences_processed,
                "skill_links_created": skill_links_created,
                "questions_generated": len(questions_for_user),
                "coverage_ratio": round((experiences_with_links / experiences_processed), 4) if experiences_processed else 0.0,
            },
        }

        return {
            "career_profile_enriched": career_profile.model_dump(),
            "structuring_report": structuring_report,
        }
